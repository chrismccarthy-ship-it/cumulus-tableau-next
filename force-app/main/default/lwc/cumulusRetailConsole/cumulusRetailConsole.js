import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify } from 'c/cumulusSdkUtils';
import { query, clearQueryCache, num, sum, pct, money, intfmt, signedPct, lastMonths, prevMonths, sparkPath, rank, loadEdits, saveEdits } from 'c/cumulusConsoleData';

/**
 * Cumulus Retail Console — "RVP · Retail Sales Performance": a full-page Tableau Next extension bound to the
 * Cumulus Retail Banking semantic model. Headless-insight banner, KPI cards with trend, three editable
 * AI-driven insight cards (Escalate / Create Action Item / Schedule Review / Assign Owner / Launch Flow),
 * and a branch table whose rows carry Analyze · Create Case · Schedule Coaching · Launch Flow · Branch Report.
 * Insights are generated from the live data (simulated "Tableau Agent headless insight") and can be edited
 * at any time; edits persist in the browser until "Regenerate" is pressed.
 */
const ACCENT = '#0F766E';
const GOLD = '#B7791F';

export default class CumulusRetailConsole extends LightningElement {
    @api sdk;
    @api sdmName; // SemanticModel
    @api title = 'RVP – Retail Sales Performance';
    @api region = ''; // optional default region filter
    @api accentColor = ACCENT;

    @track tab = 'insights';
    @track period = '3';
    @track regionSel = '';
    @track months = [];
    @track caseRows = []; // branch × month
    @track hhRows = []; // branch
    @track acctRows = []; // branch × open month
    @track insights = [];
    @track editing = null;
    @track modal = null; // {mode, context}
    @track lastReport = null;
    @track loading = true;
    @track error;
    _unsub;
    _cache = {};
    memo(key, fn) { if (!(key in this._cache)) this._cache[key] = fn(); return this._cache[key]; }
    invalidate() { this._cache = {}; }

    get isConfigured() { return Boolean(this.sdmName && this.sdmName.apiName); }
    get model() { return this.sdmName.apiName; }
    get accent() { return /^#[0-9a-fA-F]{6}$/.test(this.accentColor || '') ? this.accentColor : ACCENT; }
    get rootStyle() { return `--accent:${this.accent};--gold:${GOLD}`; }

    connectedCallback() {
        notify(this.sdk, 'INIT');
        this.regionSel = this.region || '';
        if (this.sdk && typeof this.sdk.on === 'function') this._unsub = this.sdk.on(SDK_EVENTS.FILTER_CHANGE, () => this.load());
        this.load();
    }
    disconnectedCallback() { if (typeof this._unsub === 'function') this._unsub(); }

    async load() {
        if (!this.isConfigured || !this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.loading = true; this.error = undefined;
        const Q = [
            query(this.sdk, this.model, { dims: [{ name: 'RB_Service_Cases.BranchName', alias: 'branch' }, { name: 'RB_Service_Cases.Region', alias: 'region' }, { name: 'RB_Service_Cases.CreatedMonth', alias: 'month' }],
                measures: [{ name: 'Case_Count', alias: 'cases' }, { name: 'FCR_Rate', alias: 'fcr' }, { name: 'Avg_CSAT', alias: 'csat' }, { name: 'Avg_Handle_Time', alias: 'aht' }, { name: 'Card_Dispute_Cases', alias: 'disputes' }] }),
            query(this.sdk, this.model, { dims: [{ name: 'RB_Households.BranchName', alias: 'branch' }],
                measures: [{ name: 'RB_Households.HouseholdId', agg: 'Count', alias: 'households' }, { name: 'RB_Households.ProductCount', agg: 'Avg', alias: 'products' }, { name: 'RB_Households.NPS', agg: 'Avg', alias: 'nps' }] }),
            query(this.sdk, this.model, { dims: [{ name: 'RB_Financial_Accounts.BranchName', alias: 'branch' }, { name: 'Account_Open_Month', alias: 'month' }],
                measures: [{ name: 'RB_Financial_Accounts.FinancialAccountId', agg: 'Count', alias: 'accounts' }] })
        ];
        const res = await Promise.allSettled(Q);
        const val = (i) => (res[i].status === 'fulfilled' ? res[i].value : []);
        const failed = res.map((r, i) => (r.status === 'rejected' ? `${['cases', 'households', 'accounts'][i]}: ${(r.reason && (r.reason.message || (r.reason.body && r.reason.body.message))) || 'query failed'}` : null)).filter(Boolean);
        this.caseRows = val(0).filter((r) => r.branch && r.month).map((r) => ({ ...r, month: String(r.month).slice(0, 7) }));
        this.hhRows = val(1).filter((r) => r.branch);
        this.acctRows = val(2).filter((r) => r.branch && r.month).map((r) => ({ ...r, month: String(r.month).slice(0, 7) }));
        this.months = [...new Set(this.caseRows.map((r) => r.month))].sort();
        this.error = failed.length ? failed.join(' · ') : undefined;
        this.invalidate();
        this.buildInsights();
        notify(this.sdk, this.caseRows.length ? 'LOADED' : 'NODATA');
        this.loading = false;
    }

    // ---------- filters ----------
    get periodOptions() { return [['1', 'Last month'], ['3', 'Last 3 months'], ['6', 'Last 6 months'], ['12', 'Last 12 months'], ['24', 'All 24 months']].map(([v, l]) => ({ value: v, label: l, selected: v === this.period })); }
    get regions() { return [...new Set(this.caseRows.map((r) => r.region).filter(Boolean))].sort(); }
    get regionOptions() { return [{ value: '', label: 'All regions', selected: !this.regionSel }].concat(this.regions.map((r) => ({ value: r, label: r, selected: r === this.regionSel }))); }
    onPeriod(e) { this.period = e.target.value; this.invalidate(); this.buildInsights(); }
    onRegion(e) { this.regionSel = e.target.value; this.invalidate(); this.buildInsights(); }
    get curMonths() { return lastMonths(this.months, Number(this.period)); }
    get prevMonthsList() { return prevMonths(this.months, Number(this.period)); }
    get periodLabel() { const m = this.curMonths; return m.length ? `${m[0]} → ${m[m.length - 1]}` : ''; }
    inRegion(r) { return !this.regionSel || r.region === this.regionSel; }

    // ---------- aggregates ----------
    /** per-branch aggregate over a month window (weighted by cases) */
    branchAgg(monthsSet) {
        return this.memo('agg:' + [...monthsSet].join(','), () => this.branchAggRaw(monthsSet));
    }
    branchAggRaw(monthsSet) {
        const by = {};
        this.caseRows.filter((r) => monthsSet.has(r.month) && this.inRegion(r)).forEach((r) => {
            const b = by[r.branch] || (by[r.branch] = { branch: r.branch, region: r.region, cases: 0, fcrW: 0, csatW: 0, ahtW: 0, disputes: 0 });
            const c = num(r.cases); b.cases += c; b.fcrW += num(r.fcr) * c; b.csatW += num(r.csat) * c; b.ahtW += num(r.aht) * c; b.disputes += num(r.disputes);
        });
        const hh = Object.fromEntries(this.hhRows.map((r) => [r.branch, r]));
        const accts = {};
        this.acctRows.forEach((r) => { if (monthsSet.has(r.month)) accts[r.branch] = (accts[r.branch] || 0) + num(r.accounts); });
        return Object.values(by).map((b) => ({ ...b, fcr: b.cases ? b.fcrW / b.cases : 0, csat: b.cases ? b.csatW / b.cases : 0, aht: b.cases ? b.ahtW / b.cases : 0,
            households: num(hh[b.branch] && hh[b.branch].households), products: num(hh[b.branch] && hh[b.branch].products), nps: num(hh[b.branch] && hh[b.branch].nps), accounts: num(accts[b.branch]) }));
    }
    get branches() { return this.memo('branches', () => this.branchesRaw()); }
    branchesRaw() {
        const rows = this.branchAgg(new Set(this.curMonths));
        rows.forEach((b) => { b.score = b.fcr * 0.45 + (b.csat / 5) * 0.35 + Math.min(1, b.products / 4) * 0.2; });
        const sorted = rank(rows, 'score');
        const n = sorted.length;
        return sorted.map((b, i) => ({ ...b, badge: i < 3 ? 'TOP' : i >= n - 3 ? 'SLIP' : 'TARGET', badgeClass: `badge ${i < 3 ? 'top' : i >= n - 3 ? 'slip' : 'target'}`,
            fcrText: pct(b.fcr, 0), csatText: b.csat.toFixed(2), ahtText: `${b.aht.toFixed(1)} min`, casesText: intfmt(b.cases), disputesText: intfmt(b.disputes), hhText: intfmt(b.households), productsText: b.products.toFixed(1), npsText: b.nps.toFixed(0), acctText: intfmt(b.accounts),
            fcrClass: b.fcr >= 0.67 ? 'good' : 'bad', csatClass: b.csat >= 3.5 ? 'good' : 'bad', short: b.branch.replace('Cumulus ', ''), region: b.region }));
    }
    totals(monthsSet) {
        return this.memo('tot:' + [...monthsSet].join(','), () => this.totalsRaw(monthsSet));
    }
    totalsRaw(monthsSet) {
        const rows = this.branchAgg(monthsSet);
        const cases = sum(rows, (r) => r.cases);
        return { cases, fcr: cases ? sum(rows, (r) => r.fcr * r.cases) / cases : 0, csat: cases ? sum(rows, (r) => r.csat * r.cases) / cases : 0, aht: cases ? sum(rows, (r) => r.aht * r.cases) / cases : 0,
            disputes: sum(rows, (r) => r.disputes), accounts: sum(rows, (r) => r.accounts), nps: rows.length ? sum(rows, (r) => r.nps) / rows.length : 0, households: sum(rows, (r) => r.households) };
    }
    monthly(key) {
        return this.months.map((m) => { const rows = this.branchAgg(new Set([m])); const t = this.totals(new Set([m])); return key === 'accounts' ? t.accounts : key === 'cases' ? t.cases : key === 'fcr' ? t.fcr : key === 'csat' ? t.csat : key === 'disputes' ? t.disputes : rows.length; });
    }
    get kpis() { return this.memo('kpis', () => this.kpisRaw()); }
    kpisRaw() {
        const cur = this.totals(new Set(this.curMonths)), prev = this.totals(new Set(this.prevMonthsList));
        const mk = (label, key, value, text, fmt, upGood) => {
            const series = this.monthly(key); const sp = sparkPath(series); const d = signedPct(value, prev[key]);
            const good = d ? (upGood ? d.good : !d.good) : null;
            return { key, label, text, sub: d ? `${d.text} (${fmt(Math.abs(d.abs))}) vs. prior ${this.curMonths.length} mo` : 'no prior period', cls: `kpi ${good === null ? '' : good ? 'up' : 'down'}`, line: sp.line, area: sp.area, endx: sp.end ? sp.end[0] : 0, endy: sp.end ? sp.end[1] : 0, hasSpark: Boolean(sp.line) };
        };
        return [mk('New accounts opened', 'accounts', cur.accounts, intfmt(cur.accounts), intfmt, true), mk('Service cases', 'cases', cur.cases, intfmt(cur.cases), intfmt, false),
            mk('First-contact resolution', 'fcr', cur.fcr, pct(cur.fcr), (v) => pct(v), true), mk('Avg CSAT', 'csat', cur.csat, cur.csat.toFixed(2), (v) => v.toFixed(2), true),
            mk('Card disputes', 'disputes', cur.disputes, intfmt(cur.disputes), intfmt, false)];
    }

    // ---------- insights (simulated headless insight) ----------
    get storeKey() { return `cumulusRetailConsole:${this.model}:${this.period}:${this.regionSel}`; }
    buildInsights() {
        const b = this.branches; if (!b.length) { this.insights = []; return; }
        const top = b[0], bottom = b[b.length - 1]; const tot = this.totals(new Set(this.curMonths));
        const byDisp = rank(b, 'disputes'); const d0 = byDisp[0]; const dispShare = tot.disputes ? d0.disputes / tot.disputes : 0;
        const byProd = rank(b, 'products', false); const lowProd = byProd.slice(0, 2);
        const gen = [
            { sev: 'warn', title: `First-contact resolution gap between ${top.short} (${pct(top.fcr, 0)}) and ${bottom.short} (${pct(bottom.fcr, 0)}) drives the CSAT spread`,
              body: `There is a distinct performance gap between top-tier branches like ${top.short} (${pct(top.fcr, 1)} FCR, CSAT ${top.csat.toFixed(2)}) and bottom-tier locations like ${bottom.short} (${pct(bottom.fcr, 1)}, CSAT ${bottom.csat.toFixed(2)}). The spread indicates case-handling practices are not consistently executed, lowering satisfaction per case in under-performing branches.`,
              scope: `${b.length} branches`, actions: ['schedule', 'task', 'flow'] },
            { sev: 'alert', title: `${d0.short} carries ${pct(dispShare, 0)} of all card disputes this period`,
              body: `${d0.short} logged ${intfmt(d0.disputes)} Card Dispute cases against a network total of ${intfmt(tot.disputes)} — ${(dispShare / (1 / b.length)).toFixed(1)}× its fair share. Disputes score the lowest CSAT of any case type, so this concentration is dragging the region's satisfaction and handle time.`,
              scope: d0.branch, actions: ['case', 'task', 'flow'] },
            { sev: 'info', title: `${lowProd.map((x) => x.short).join(' and ')} trail the network on products per household`,
              body: `${lowProd.map((x) => `${x.short} averages ${x.products.toFixed(1)} products per household`).join('; ')}, against a network average of ${(sum(b, (x) => x.products) / b.length).toFixed(1)}. Both sit in the bottom tier on new accounts opened (${lowProd.map((x) => intfmt(x.accounts)).join(' / ')} this period), pointing to a cross-sell rather than a service problem.`,
              scope: lowProd.map((x) => x.branch).join(', '), actions: ['schedule', 'task', 'flow'] }
        ];
        const edits = loadEdits(this.storeKey);
        this.insights = gen.map((g, i) => ({ ...g, ...(edits[i] || {}), id: i, cls: `insight ${g.sev}`, icon: g.sev === 'alert' ? '⊘' : g.sev === 'warn' ? '⚠' : 'ⓘ',
            btnSchedule: g.actions.includes('schedule'), btnCase: g.actions.includes('case'), btnTask: g.actions.includes('task'), btnFlow: true, taskLabel: g.actions.includes('case') ? 'Create Action Item' : 'Assign Owner' }));
    }
    get banner() { return this.memo('banner', () => this.bannerRaw()); }
    bannerRaw() {
        const b = this.branches; if (!b.length) return { title: 'Loading insights…', sub: '' };
        const tot = this.totals(new Set(this.curMonths)); const good = b.filter((x) => x.fcr >= 0.67).length;
        return { title: `${good} of ${b.length} branches clear the 67% first-contact-resolution bar — the rest trail on CSAT too`,
                 sub: `Network FCR ${pct(tot.fcr, 1)} · CSAT ${tot.csat.toFixed(2)} · ${intfmt(tot.accounts)} new accounts across ${intfmt(tot.households)} households · ${this.periodLabel}` };
    }
    editInsight(e) { const id = Number(e.currentTarget.dataset.id); const i = this.insights.find((x) => x.id === id); this.editing = { id, title: i.title, body: i.body }; }
    onEditTitle(e) { this.editing = { ...this.editing, title: e.target.value }; }
    onEditBody(e) { this.editing = { ...this.editing, body: e.target.value }; }
    saveInsight() { const edits = loadEdits(this.storeKey); edits[this.editing.id] = { title: this.editing.title, body: this.editing.body }; saveEdits(this.storeKey, edits); this.editing = null; this.buildInsights(); }
    cancelEdit() { this.editing = null; }
    renderedCallback() { if (!this.editing) return; this.template.querySelectorAll('[data-bind]').forEach((el) => { const v = this.editing[el.dataset.bind]; if (v !== undefined && el.value !== v) el.value = v; }); }
    regenerate() { saveEdits(this.storeKey, {}); clearQueryCache(); this.load(); }
    get isEditing() { return Boolean(this.editing); }
    editingFor(id) { return this.editing && this.editing.id === id; }
    get insightCards() { return this.insights.map((i) => ({ ...i, isEditing: this.editingFor(i.id) })); }

    // ---------- tabs ----------
    get tabInsights() { return this.tab === 'insights'; } get tabTable() { return this.tab === 'table'; } get tabReport() { return this.tab === 'report'; }
    get tabInsightsClass() { return `tabbtn ${this.tab === 'insights' ? 'on' : ''}`; } get tabTableClass() { return `tabbtn ${this.tab === 'table' ? 'on' : ''}`; } get tabReportClass() { return `tabbtn ${this.tab === 'report' ? 'on' : ''}`; }
    setTab(e) { this.tab = e.currentTarget.dataset.tab; }
    get hasReport() { return Boolean(this.lastReport); }

    // ---------- analysis (simulated Agentforce) ----------
    analysisFor(branchName, question) {
        const b = this.branches; const me = b.find((x) => x.branch === branchName); if (!me) return null;
        const top = b[0], worst = b[b.length - 1]; const avgF = sum(b, (x) => x.fcr) / b.length; const avgC = sum(b, (x) => x.csat) / b.length;
        const idx = b.indexOf(me) + 1; const risk = me.badge === 'SLIP'; const tag = risk ? 'Risk' : me.badge === 'TOP' ? 'Top' : 'Target';
        const bars = [];
        if (me !== top) bars.push({ label: `${top.short} (Top)`, value: pct(top.fcr, 1), pct: top.fcr * 100, color: '#0F766E' });
        bars.push({ label: 'Network average', value: pct(avgF, 1), pct: avgF * 100, color: '#F59E0B' });
        bars.push({ label: `${me.short} (${tag})`, value: pct(me.fcr, 1), pct: me.fcr * 100, color: risk ? '#DC2626' : me === top ? '#0F766E' : '#2563EB' });
        if (me !== worst) bars.push({ label: `${worst.short} (Risk)`, value: pct(worst.fcr, 1), pct: worst.fcr * 100, color: '#DC2626' });
        return {
            summary: risk ? `${me.short} is suffering from a disconnect between case volume and resolution capability, ranking #${idx} of ${b.length} branches because cases are not being closed on first contact.`
                          : `${me.short} ranks #${idx} of ${b.length} branches: resolution and satisfaction are ${me.fcr >= avgF ? 'above' : 'below'} the network average, with ${me.accounts ? intfmt(me.accounts) : 'no'} new accounts opened this period.`,
            findings: [
                me === top ? `First-contact resolution of ${pct(me.fcr, 1)} leads the network; the runner-up, ${b[1].short}, is ${((me.fcr - b[1].fcr) * 100).toFixed(1)} points behind and the network average is ${pct(avgF, 1)}.` : `First-contact resolution is ${pct(me.fcr, 1)} versus ${pct(top.fcr, 1)} at ${top.short}, a gap of ${((top.fcr - me.fcr) * 100).toFixed(1)} points; the network average is ${pct(avgF, 1)}.`,
                `CSAT averages ${me.csat.toFixed(2)} (network ${avgC.toFixed(2)}) across ${intfmt(me.cases)} cases, with ${intfmt(me.disputes)} card disputes — the case type that scores lowest.`,
                `Average handle time is ${me.aht.toFixed(1)} minutes; ${me.products.toFixed(1)} products per household and an NPS of ${me.nps.toFixed(0)} across ${intfmt(me.households)} households.`,
                `Compared with peers, ${me.short} sits in the ${tag.toLowerCase()} group${risk ? ` alongside ${b.slice(-3).filter((x) => x !== me).map((x) => x.short).join(' and ')}` : ''}.`
            ],
            bars,
            actions: [
                { title: 'Case diagnostic', body: `Review the last ${this.curMonths.length} months of reopened and dispute cases to find the stage where first-contact resolution breaks down.` },
                { title: 'High-touch shadowing', body: `Pair the ${me.short} team lead with ${top.short} for two days to observe first-contact closing practices.` },
                { title: 'Incentivised activity sprint', body: `Launch a two-week sprint targeting a ${Math.max(5, Math.round((avgF - me.fcr) * 100) + 3)}-point FCR lift, with daily stand-ups on dispute handling.` },
                { title: 'Manager coaching', body: 'Add a 15-minute daily huddle on the top three objection types driving repeat contacts.' }
            ],
            caveat: `Data assumes the ${this.curMonths.length}-month reporting window (${this.periodLabel}); FCR and CSAT are case-weighted averages from the Cumulus Retail Banking semantic model.`
        };
    }
    defaultQuestion(short) { return `Give me an in-depth analysis of ${short}. What are the root causes of its service performance, how does it compare to the best and worst performers, and what specific actions should the manager take this week?`; }

    // ---------- row & insight actions ----------
    rowAction(e) {
        const { action, branch } = e.currentTarget.dataset; const me = this.branches.find((x) => x.branch === branch); if (!me) return;
        const q = this.defaultQuestion(me.short); const analysis = this.analysisFor(branch, q);
        const base = { subjectName: me.short, domain: 'Sales Insights', modelLabel: 'Cumulus Retail Banking · Tableau Next Semantic Model', slackChannel: 'retail-rvp', insights: this.insights };
        if (action === 'analyze') this.modal = { mode: 'analyze', context: { ...base, question: q, analysis } };
        else if (action === 'report') { this.lastReport = { question: q, analysis, subject: me.short }; this.modal = { mode: 'report', context: { ...base, question: q, analysis } }; }
        else if (action === 'case') this.modal = { mode: 'case', context: { ...base, title: `${me.short}: service performance follow-up`, background: analysis.summary } };
        else if (action === 'coach') this.modal = { mode: 'schedule', context: { ...base, title: `Coaching: ${me.short} — first-contact resolution`, background: analysis.summary + ' ' + analysis.findings[0], scope: me.branch, attendees: `Branch Manager (${me.short}), Regional Sales Lead` } };
        else if (action === 'flow') this.modal = { mode: 'flow', context: { ...base, title: me.short, background: analysis.summary } };
    }
    insightAction(e) {
        const { action, id } = e.currentTarget.dataset; const i = this.insights.find((x) => x.id === Number(id)); if (!i) return;
        const base = { title: i.title, background: i.body, scope: i.scope, attendees: 'Regional Sales Lead, Branch Managers', insights: this.insights, subjectName: i.scope, slackChannel: 'retail-rvp' };
        this.modal = { mode: { schedule: 'schedule', case: 'case', task: 'task', flow: 'flow' }[action] || 'task', context: base };
    }
    onReask(e) {
        // re-run the (simulated) analysis for an edited question — keeps the branch, refreshes the wording
        if (!this.modal) return; const c = this.modal.context; const me = this.branches.find((x) => x.short === c.subjectName);
        this.modal = { ...this.modal, context: { ...c, question: e.detail.question, analysis: me ? this.analysisFor(me.branch, e.detail.question) : c.analysis } };
    }
    onModalDone(e) { if (e.detail.kind === 'report') this.tab = 'report'; }
    closeModal() { if (this.modal && this.modal.mode === 'analyze' && this.modal.context.analysis) this.lastReport = { question: this.modal.context.question, analysis: this.modal.context.analysis, subject: this.modal.context.subjectName }; this.modal = null; }
    get modalOpen() { return Boolean(this.modal); }
    get modalMode() { return this.modal ? this.modal.mode : 'task'; }
    get modalContext() { return this.modal ? this.modal.context : {}; }
    // report tab
    get reportBars() { return this.lastReport ? (this.lastReport.analysis.bars || []).map((b) => ({ ...b, style: `width:${b.pct}%;background:${b.color}` })) : []; }
    get reportLine() { return `Generated by Agentforce · ${new Date().toLocaleString()}`; }
    openReportModal() { if (this.lastReport) this.modal = { mode: 'report', context: { question: this.lastReport.question, analysis: this.lastReport.analysis, subjectName: this.lastReport.subject, slackChannel: 'retail-rvp' } }; }
    closeReport() { this.lastReport = null; this.tab = 'insights'; }
}
