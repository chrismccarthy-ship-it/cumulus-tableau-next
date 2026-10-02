import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify } from 'c/cumulusSdkUtils';
import { query, clearQueryCache, num, sum, pct, money, intfmt, signedPct, lastMonths, prevMonths, sparkPath, rank, loadEdits, saveEdits } from 'c/cumulusConsoleData';

/**
 * Cumulus LOB Console — the generic version of the Retail RVP console, driven by a JSON `config` so the same
 * extension serves Asset Management, Insurance, Commercial, Advisors and Lending (Retail and Wealth have their
 * own tailored consoles). Headless-insight banner, KPI trend cards, editable AI-driven insight cards with
 * actions, and an entity table (clients / states / RMs / advisors / loan officers) with Analyze · Create Case ·
 * Schedule Review · Launch Flow · Report on every row.
 *
 * config = {
 *   entity:   { field: 'AM_Service_Requests.ClientName', label: 'Client', short: /regex to strip/ },
 *   month:    'Request_Month' | 'INS_Claims.LossMonth',
 *   region:   { field: 'AM_Service_Requests.Region', label: 'Region' },           // optional filter dimension
 *   kpis:     [{ name: 'Request_Count', label: 'Service requests', format: 'number', upGood: false, weight: true, agg: 'Sum' }, …]  (max 6; the one with weight:true weights rate averages)
 *   extra:    { dims: ['AM_Mandates.RelationshipManagerName'], kpis: [{ name: 'Total_AUM', label: 'AUM', format: 'currency', upGood: true }] }  // optional entity-level (no month) measures
 *   persona:  'Client service lead', domain: 'Service Insights', modelLabel: '…', slack: 'am-leadership',
 *   target:   { kpi: 'SLA_Breach_Rate', value: 0.2 }   // optional target used in narratives
 * }
 */
export default class CumulusLobConsole extends LightningElement {
    @api sdk;
    @api sdmName;
    @api title = 'Command Center';
    @api config = '';
    @api accentColor = '#0B5CAB';
    @api headerFrom = '#0B2A4A';
    @api headerTo = '#2563EB';

    @track tab = 'insights';
    @track period = '3';
    @track regionSel = '';
    @track months = [];
    @track rowsM = []; // entity × region × month
    @track rowsE = []; // entity-level extras
    @track insights = [];
    @track editing = null;
    @track modal = null;
    @track lastReport = null;
    @track error;
    _unsub;
    _cache = {};
    memo(key, fn) { if (!(key in this._cache)) this._cache[key] = fn(); return this._cache[key]; }
    invalidate() { this._cache = {}; }

    get cfg() { return this.memo('cfg', () => { try { return typeof this.config === 'string' ? JSON.parse(this.config || '{}') : (this.config || {}); } catch (e) { return {}; } }); }
    get isConfigured() { return Boolean(this.sdmName && this.sdmName.apiName && this.cfg.entity && this.cfg.month && Array.isArray(this.cfg.kpis) && this.cfg.kpis.length); }
    get model() { return this.sdmName.apiName; }
    get accent() { return /^#[0-9a-fA-F]{6}$/.test(this.accentColor || '') ? this.accentColor : '#0B5CAB'; }
    get rootStyle() { return `--accent:${this.accent};--hfrom:${this.headerFrom};--hto:${this.headerTo}`; }
    get kpiDefs() { return (this.cfg.kpis || []).slice(0, 6).map((k, i) => ({ ...k, alias: `k${i}`, format: k.format || 'number', upGood: k.upGood !== false })); }
    get weightAlias() { const w = this.kpiDefs.find((k) => k.weight); return w ? w.alias : null; }
    get entityLabel() { return (this.cfg.entity && this.cfg.entity.label) || 'Entity'; }
    get shortRe() { try { return this.cfg.entity && this.cfg.entity.short ? new RegExp(this.cfg.entity.short) : null; } catch (e) { return null; } }
    shortName(v) { return this.shortRe ? String(v).replace(this.shortRe, '').trim() || String(v) : String(v); }
    get hasRegion() { return Boolean(this.cfg.region && this.cfg.region.field); }
    get regionLabel() { return this.hasRegion ? this.cfg.region.label || 'Region' : ''; }

    connectedCallback() {
        notify(this.sdk, 'INIT');
        if (this.sdk && typeof this.sdk.on === 'function') this._unsub = this.sdk.on(SDK_EVENTS.FILTER_CHANGE, () => this.load());
        this.load();
    }
    disconnectedCallback() { if (typeof this._unsub === 'function') this._unsub(); }

    async load() {
        if (!this.isConfigured || !this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        const c = this.cfg;
        const dims = [{ name: c.entity.field, alias: 'entity' }];
        if (this.hasRegion) dims.push({ name: c.region.field, alias: 'region' });
        dims.push({ name: c.month, alias: 'month' });
        const Q = [query(this.sdk, this.model, { dims, measures: this.kpiDefs.map((k) => ({ name: k.name, alias: k.alias, agg: k.agg })) })];
        if (c.extra && Array.isArray(c.extra.kpis) && c.extra.kpis.length) {
            Q.push(query(this.sdk, this.model, { dims: [{ name: (c.extra.dims && c.extra.dims[0]) || c.entity.field, alias: 'entity' }], measures: c.extra.kpis.map((k, i) => ({ name: k.name, alias: `x${i}`, agg: k.agg })) }));
        }
        const res = await Promise.allSettled(Q);
        const val = (i) => (res[i] && res[i].status === 'fulfilled' ? res[i].value : []);
        const failed = res.map((r, i) => (r.status === 'rejected' ? `${i === 0 ? 'trend query' : 'entity query'}: ${(r.reason && (r.reason.message || (r.reason.body && r.reason.body.message))) || 'failed'}` : null)).filter(Boolean);
        this.rowsM = val(0).filter((r) => r.entity && r.month).map((r) => ({ ...r, month: String(r.month).slice(0, 7) }));
        this.rowsE = val(1).filter((r) => r.entity);
        this.months = [...new Set(this.rowsM.map((r) => r.month))].sort();
        this.error = failed.length ? failed.join(' · ') : undefined;
        this.invalidate(); this.buildInsights();
        notify(this.sdk, this.rowsM.length ? 'LOADED' : 'NODATA');
    }

    // ---------- filters ----------
    get periodOptions() { return [['1', 'Last month'], ['3', 'Last 3 months'], ['6', 'Last 6 months'], ['12', 'Last 12 months'], ['24', 'All months']].map(([v, l]) => ({ value: v, label: l, selected: v === this.period })); }
    get regions() { return [...new Set(this.rowsM.map((r) => r.region).filter(Boolean))].sort(); }
    get regionOptions() { return [{ value: '', label: `All ${this.regionLabel.toLowerCase()}s`, selected: !this.regionSel }].concat(this.regions.map((r) => ({ value: r, label: r, selected: r === this.regionSel }))); }
    onPeriod(e) { this.period = e.target.value; this.invalidate(); this.buildInsights(); }
    onRegion(e) { this.regionSel = e.target.value; this.invalidate(); this.buildInsights(); }
    get curMonths() { return lastMonths(this.months, Number(this.period)); }
    get prevMonthsList() { return prevMonths(this.months, Number(this.period)); }
    get periodLabel() { const m = this.curMonths; return m.length ? `${m[0]} → ${m[m.length - 1]}` : ''; }
    inRegion(r) { return !this.regionSel || r.region === this.regionSel; }

    // ---------- aggregates ----------
    /** per-entity aggregate over a month window; additive KPIs are summed, rates/averages are weight-averaged */
    agg(monthsSet) {
        return this.memo('agg:' + [...monthsSet].join(','), () => {
            const by = {}; const wA = this.weightAlias; const defs = this.kpiDefs;
            this.rowsM.forEach((r) => {
                if (!monthsSet.has(r.month) || !this.inRegion(r)) return;
                const b = by[r.entity] || (by[r.entity] = { entity: r.entity, region: r.region, w: 0, n: 0, acc: {} });
                const w = wA ? num(r[wA]) : 1; b.w += w; b.n += 1;
                defs.forEach((k) => { const v = num(r[k.alias]); b.acc[k.alias] = (b.acc[k.alias] || 0) + (this.isAdditive(k) ? v : v * w); });
            });
            const ex = Object.fromEntries(this.rowsE.map((r) => [r.entity, r]));
            return Object.values(by).map((b) => { const o = { entity: b.entity, region: b.region, short: this.shortName(b.entity) };
                defs.forEach((k) => { o[k.alias] = this.isAdditive(k) ? b.acc[k.alias] : (b.w ? b.acc[k.alias] / b.w : 0); });
                ((this.cfg.extra && this.cfg.extra.kpis) || []).forEach((k, i) => { o[`x${i}`] = num(ex[b.entity] && ex[b.entity][`x${i}`]); });
                return o; });
        });
    }
    isAdditive(k) { return k.format !== 'percent' && !/^Avg_|Rate|Ratio|Cycle|Time|Days|CSAT|NPS|Utilization/i.test(k.name) && !(k.agg && /avg/i.test(k.agg)); }
    totals(monthsSet) {
        return this.memo('tot:' + [...monthsSet].join(','), () => {
            const rows = this.agg(monthsSet); const wA = this.weightAlias; const t = {};
            const W = wA ? sum(rows, (r) => r[wA]) : rows.length;
            this.kpiDefs.forEach((k) => { t[k.alias] = this.isAdditive(k) ? sum(rows, (r) => r[k.alias]) : (W ? sum(rows, (r) => r[k.alias] * (wA ? r[wA] : 1)) / W : 0); });
            ((this.cfg.extra && this.cfg.extra.kpis) || []).forEach((k, i) => { t[`x${i}`] = this.isAdditiveExtra(k) ? sum(rows, (r) => r[`x${i}`]) : (rows.length ? sum(rows, (r) => r[`x${i}`]) / rows.length : 0); });
            return t;
        });
    }
    isAdditiveExtra(k) { return k.format !== 'percent' && !/^Avg_|Rate|Ratio|Utilization/i.test(k.name); }
    fmt(k, v) { return k.format === 'currency' ? money(v) : k.format === 'percent' ? pct(v) : (Math.abs(num(v)) < 100 && num(v) % 1 ? num(v).toFixed(1) : intfmt(v)); }
    get primary() { return this.kpiDefs.find((k) => k.primary) || this.kpiDefs[1] || this.kpiDefs[0]; }
    get entities() {
        return this.memo('entities', () => {
            const rows = this.agg(new Set(this.curMonths)); const defs = this.kpiDefs; if (!rows.length) return [];
            // composite score: normalised rank of each KPI, direction-aware
            defs.forEach((k) => { const vals = rows.map((r) => r[k.alias]); const mn = Math.min(...vals), mx = Math.max(...vals); rows.forEach((r) => { const t = mx > mn ? (r[k.alias] - mn) / (mx - mn) : 0.5; r.score = (r.score || 0) + (k.upGood ? t : 1 - t) / defs.length; }); });
            const sorted = rank(rows, 'score'); const n = sorted.length;
            return sorted.map((r, i) => ({ ...r, idx: i + 1, badge: i < 3 ? 'TOP' : i >= n - 3 ? 'SLIP' : 'TARGET', badgeClass: `badge ${i < 3 ? 'top' : i >= n - 3 ? 'slip' : 'target'}`,
                cells: defs.map((k) => ({ key: k.alias, text: this.fmt(k, r[k.alias]) })).concat(((this.cfg.extra && this.cfg.extra.kpis) || []).map((k, j) => ({ key: `x${j}`, text: this.fmt(k, r[`x${j}`]) }))) }));
        });
    }
    get columns() { return this.kpiDefs.map((k) => k.label).concat(((this.cfg.extra && this.cfg.extra.kpis) || []).map((k) => k.label)); }
    monthly(alias) { return this.months.map((m) => this.totals(new Set([m]))[alias]); }
    get kpis() {
        return this.memo('kpis', () => {
            const cur = this.totals(new Set(this.curMonths)), prev = this.totals(new Set(this.prevMonthsList));
            return this.kpiDefs.map((k) => { const sp = sparkPath(this.monthly(k.alias)); const d = signedPct(cur[k.alias], prev[k.alias]); const good = d ? (k.upGood ? d.good : !d.good) : null;
                return { key: k.alias, label: k.label, text: this.fmt(k, cur[k.alias]), sub: d ? `${d.text} (${this.fmt(k, Math.abs(d.abs))}) vs. prior ${this.curMonths.length} mo` : 'no prior period', cls: `kpi ${good === null ? '' : good ? 'up' : 'down'}`, line: sp.line, area: sp.area, endx: sp.end ? sp.end[0] : 0, endy: sp.end ? sp.end[1] : 0, hasSpark: Boolean(sp.line) }; });
        });
    }
    get kpiGridStyle() { return `grid-template-columns:repeat(${Math.max(3, this.kpiDefs.length)},1fr)`; }

    // ---------- insights ----------
    get storeKey() { return `cumulusLobConsole:${this.model}:${this.period}:${this.regionSel}`; }
    buildInsights() {
        const e = this.entities; if (!e.length) { this.insights = []; return; }
        const P = this.primary; const top = e[0], bottom = e[e.length - 1]; const tot = this.totals(new Set(this.curMonths)); const L = this.entityLabel.toLowerCase();
        const byP = rank(e, P.alias, !P.upGood); const worstP = byP[0]; const bestP = rank(e, P.alias, P.upGood)[0];
        const addK = this.kpiDefs.find((k) => this.isAdditive(k) && !k.upGood) || this.kpiDefs.find((k) => this.isAdditive(k)); const byAdd = addK ? rank(e, addK.alias) : []; const a0 = byAdd[0]; const share = addK && tot[addK.alias] ? a0[addK.alias] / tot[addK.alias] : 0;
        const secK = this.kpiDefs.find((k) => k !== P && k !== addK) || P; const lag = rank(e, secK.alias, !secK.upGood).slice(0, 2);
        const gen = [
            { sev: 'warn', title: `${P.label} gap between ${bestP.short} (${this.fmt(P, bestP[P.alias])}) and ${worstP.short} (${this.fmt(P, worstP[P.alias])}) sets the spread`,
              body: `There is a distinct performance gap between top-tier ${L}s like ${bestP.short} and bottom-tier ones like ${worstP.short}: ${P.label.toLowerCase()} of ${this.fmt(P, bestP[P.alias])} against ${this.fmt(P, worstP[P.alias])}, with the network at ${this.fmt(P, tot[P.alias])}. The spread indicates the operating practice is not being executed consistently; ${top.short} leads the composite score and ${bottom.short} trails it.`,
              scope: `${e.length} ${L}s`, actions: ['schedule', 'task', 'flow'] },
            addK ? (addK.upGood
                ? { sev: 'info', title: `${a0.short} drives ${pct(share, 0)} of all ${addK.label.toLowerCase()} this period`,
                    body: `${a0.short} accounts for ${this.fmt(addK, a0[addK.alias])} of ${this.fmt(addK, tot[addK.alias])} — ${(share / (1 / e.length)).toFixed(1)}× the average ${L}. That dependence is a key-person risk for the book; capture what is working and spread the practice to the rest of the team.`,
                    scope: a0.entity, actions: ['schedule', 'task', 'flow'] }
                : { sev: 'alert', title: `${a0.short} carries ${pct(share, 0)} of all ${addK.label.toLowerCase()} this period`,
                    body: `${a0.short} accounts for ${this.fmt(addK, a0[addK.alias])} of ${this.fmt(addK, tot[addK.alias])} — ${(share / (1 / e.length)).toFixed(1)}× its fair share across ${e.length} ${L}s. Concentration this high warrants a review of root cause before it spreads to the rest of the book.`,
                    scope: a0.entity, actions: ['case', 'task', 'flow'] }) : null,
            { sev: 'info', title: `${lag.map((x) => x.short).join(' and ')} trail on ${secK.label.toLowerCase()}`,
              body: `${lag.map((x) => `${x.short} posts ${this.fmt(secK, x[secK.alias])}`).join('; ')}, against ${this.fmt(secK, tot[secK.alias])} for the network. ${secK.upGood ? 'Lifting' : 'Lowering'} ${secK.label.toLowerCase()} in these two ${L}s is the quickest route to moving the aggregate.`,
              scope: lag.map((x) => x.entity).join(', '), actions: ['schedule', 'task', 'flow'] }
        ].filter(Boolean);
        const edits = loadEdits(this.storeKey);
        this.insights = gen.map((g, i) => ({ ...g, ...(edits[i] || {}), id: i, cls: `insight ${g.sev}`, icon: g.sev === 'alert' ? '⊘' : g.sev === 'warn' ? '⚠' : 'ⓘ', btnSchedule: g.actions.includes('schedule'), btnCase: g.actions.includes('case'), taskLabel: g.actions.includes('case') ? 'Create Action Item' : 'Assign Owner' }));
    }
    get banner() {
        return this.memo('banner', () => { const e = this.entities; if (!e.length) return { title: 'Loading insights…', sub: '' }; const P = this.primary; const tot = this.totals(new Set(this.curMonths)); const tgt = this.cfg.target;
            const good = tgt && tgt.kpi ? e.filter((r) => { const k = this.kpiDefs.find((d) => d.name === tgt.kpi); return k && (k.upGood ? r[k.alias] >= tgt.value : r[k.alias] <= tgt.value); }).length : null;
            return { title: good !== null ? `${good} of ${e.length} ${this.entityLabel.toLowerCase()}s meet the ${this.kpiDefs.find((d) => d.name === tgt.kpi).label.toLowerCase()} target — the rest trail on the composite too` : `${e[0].short} leads and ${e[e.length - 1].short} trails across ${this.kpiDefs.length} measures this period`,
                     sub: this.kpiDefs.slice(0, 4).map((k) => `${k.label} ${this.fmt(k, tot[k.alias])}`).join(' · ') + ` · ${this.periodLabel}` }; });
    }
    editInsight(e) { const id = Number(e.currentTarget.dataset.id); const i = this.insights.find((x) => x.id === id); this.editing = { id, title: i.title, body: i.body }; }
    onEditTitle(e) { this.editing = { ...this.editing, title: e.target.value }; } onEditBody(e) { this.editing = { ...this.editing, body: e.target.value }; }
    saveInsight() { const ed = loadEdits(this.storeKey); ed[this.editing.id] = { title: this.editing.title, body: this.editing.body }; saveEdits(this.storeKey, ed); this.editing = null; this.buildInsights(); }
    cancelEdit() { this.editing = null; }
    renderedCallback() { if (!this.editing) return; this.template.querySelectorAll('[data-bind]').forEach((el) => { const v = this.editing[el.dataset.bind]; if (v !== undefined && el.value !== v) el.value = v; }); }
    regenerate() { saveEdits(this.storeKey, {}); clearQueryCache(); this.load(); }
    get insightCards() { return this.insights.map((i) => ({ ...i, isEditing: Boolean(this.editing && this.editing.id === i.id) })); }

    // ---------- tabs ----------
    get tabInsights() { return this.tab === 'insights'; } get tabTable() { return this.tab === 'table'; } get tabReport() { return this.tab === 'report'; }
    get tabInsightsClass() { return `tabbtn ${this.tab === 'insights' ? 'on' : ''}`; } get tabTableClass() { return `tabbtn ${this.tab === 'table' ? 'on' : ''}`; } get tabReportClass() { return `tabbtn ${this.tab === 'report' ? 'on' : ''}`; }
    setTab(e) { this.tab = e.currentTarget.dataset.tab; }
    get hasReport() { return Boolean(this.lastReport); }

    // ---------- analysis (simulated) ----------
    analysisFor(entity) {
        const e = this.entities; const me = e.find((x) => x.entity === entity); if (!me) return null; const P = this.primary; const top = e[0], worst = e[e.length - 1]; const tot = this.totals(new Set(this.curMonths));
        const best = rank(e, P.alias, P.upGood)[0]; const worstP = rank(e, P.alias, !P.upGood)[0]; const risk = me.badge === 'SLIP'; const tag = risk ? 'Risk' : me.badge === 'TOP' ? 'Top' : 'Target';
        const scale = Math.max(...e.map((x) => Math.abs(x[P.alias])), 1e-9); const bars = [];
        if (me !== best) bars.push({ label: `${best.short} (Best)`, value: this.fmt(P, best[P.alias]), pct: Math.abs(best[P.alias]) / scale * 100, color: '#0F766E' });
        bars.push({ label: 'Network', value: this.fmt(P, tot[P.alias]), pct: Math.abs(tot[P.alias]) / scale * 100, color: '#F59E0B' });
        bars.push({ label: `${me.short} (${tag})`, value: this.fmt(P, me[P.alias]), pct: Math.abs(me[P.alias]) / scale * 100, color: risk ? '#DC2626' : me === best ? '#0F766E' : '#2563EB' });
        if (me !== worstP) bars.push({ label: `${worstP.short} (Risk)`, value: this.fmt(P, worstP[P.alias]), pct: Math.abs(worstP[P.alias]) / scale * 100, color: '#DC2626' });
        const L = this.entityLabel.toLowerCase();
        return { summary: risk ? `${me.short} ranks #${me.idx} of ${e.length} ${L}s and sits in the risk group: ${P.label.toLowerCase()} is ${this.fmt(P, me[P.alias])} against ${this.fmt(P, tot[P.alias])} for the network.`
                               : `${me.short} ranks #${me.idx} of ${e.length} ${L}s on the composite score, with ${P.label.toLowerCase()} of ${this.fmt(P, me[P.alias])} (network ${this.fmt(P, tot[P.alias])}).`,
                 findings: this.kpiDefs.map((k) => `${k.label}: ${this.fmt(k, me[k.alias])} vs ${this.fmt(k, tot[k.alias])} network — ${(k.upGood ? me[k.alias] >= tot[k.alias] : me[k.alias] <= tot[k.alias]) ? 'ahead' : 'behind'}.`).concat([`Composite position: ${tag.toLowerCase()} group${risk ? ` alongside ${e.slice(-3).filter((x) => x !== me).map((x) => x.short).join(' and ')}` : ''}; ${top.short} leads, ${worst.short} trails.`]),
                 bars,
                 actions: [{ title: 'Diagnostic', body: `Review the last ${this.curMonths.length} months of ${me.short}'s records to isolate where ${P.label.toLowerCase()} diverges from ${best.short}.` }, { title: 'Peer shadowing', body: `Pair ${me.short} with ${best.short} for two days to transfer the practices behind the gap.` }, { title: 'Two-week sprint', body: `Set a measurable ${P.label.toLowerCase()} goal for ${me.short} with daily check-ins.` }, { title: 'Manager coaching', body: 'A 15-minute daily huddle on the top three drivers of the gap.' }],
                 caveat: `Figures cover ${this.periodLabel} from the ${this.cfg.modelLabel || 'Cumulus'} semantic model; rate measures are ${this.weightAlias ? 'volume-weighted' : 'simple'} averages.` };
    }
    defaultQuestion(short) { return `Give me an in-depth analysis of ${short}. What are the root causes of its performance, how does it compare to the best and worst performers, and what specific actions should the ${(this.cfg.persona || 'manager').toLowerCase()} take this week?`; }
    rowAction(e) {
        const { action, entity } = e.currentTarget.dataset; const me = this.entities.find((x) => x.entity === entity); if (!me) return; const q = this.defaultQuestion(me.short); const analysis = this.analysisFor(entity);
        const base = { subjectName: me.short, domain: this.cfg.domain || 'Insights', modelLabel: this.cfg.modelLabel || 'Tableau Next Semantic Model', slackChannel: this.cfg.slack || 'cumulus-leadership', insights: this.insights };
        if (action === 'analyze') this.modal = { mode: 'analyze', context: { ...base, question: q, analysis } };
        else if (action === 'report') { this.lastReport = { question: q, analysis, subject: me.short }; this.modal = { mode: 'report', context: { ...base, question: q, analysis } }; }
        else if (action === 'case') this.modal = { mode: 'case', context: { ...base, title: `${me.short}: performance follow-up`, background: analysis.summary } };
        else if (action === 'schedule') this.modal = { mode: 'schedule', context: { ...base, title: `Review: ${me.short} — ${this.primary.label.toLowerCase()}`, background: analysis.summary + ' ' + analysis.findings[0], scope: me.entity, attendees: `${this.cfg.persona || 'Manager'}, ${me.short} owner` } };
        else if (action === 'flow') this.modal = { mode: 'flow', context: { ...base, title: me.short, background: analysis.summary } };
    }
    insightAction(e) {
        const { action, id } = e.currentTarget.dataset; const i = this.insights.find((x) => x.id === Number(id)); if (!i) return;
        this.modal = { mode: { schedule: 'schedule', case: 'case', task: 'task', flow: 'flow' }[action] || 'task', context: { title: i.title, background: i.body, scope: i.scope, attendees: `${this.cfg.persona || 'Manager'}, team leads`, insights: this.insights, subjectName: i.scope, slackChannel: this.cfg.slack || 'cumulus-leadership' } };
    }
    onReask(e) { if (!this.modal) return; const c = this.modal.context; const me = this.entities.find((x) => x.short === c.subjectName); this.modal = { ...this.modal, context: { ...c, question: e.detail.question, analysis: me ? this.analysisFor(me.entity) : c.analysis } }; }
    closeModal() { if (this.modal && this.modal.mode === 'analyze' && this.modal.context.analysis) this.lastReport = { question: this.modal.context.question, analysis: this.modal.context.analysis, subject: this.modal.context.subjectName }; this.modal = null; }
    get modalOpen() { return Boolean(this.modal); } get modalMode() { return this.modal ? this.modal.mode : 'task'; } get modalContext() { return this.modal ? this.modal.context : {}; }
    get reportBars() { return this.lastReport ? (this.lastReport.analysis.bars || []).map((b) => ({ ...b, style: `width:${b.pct}%;background:${b.color}` })) : []; }
    get reportLine() { return `Generated by Agentforce · ${new Date().toLocaleString()}`; }
    openReportModal() { if (this.lastReport) this.modal = { mode: 'report', context: { question: this.lastReport.question, analysis: this.lastReport.analysis, subjectName: this.lastReport.subject, slackChannel: this.cfg.slack || 'cumulus-leadership' } }; }
    closeReport() { this.lastReport = null; this.tab = 'insights'; }
    get persona() { return this.cfg.persona || ''; }
    get footnote() { return `Data 360 · ${this.cfg.modelLabel || 'Cumulus'} Tableau Next semantic model · insights are generated from the live model (headless-insight simulation) and can be edited at any time`; }
}
