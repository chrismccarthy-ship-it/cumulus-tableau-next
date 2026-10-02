import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify } from 'c/cumulusSdkUtils';
import { query, clearQueryCache, num, sum, pct, money, intfmt, signedPct, lastMonths, prevMonths, sparkPath, rank, loadEdits, saveEdits } from 'c/cumulusConsoleData';

/**
 * Cumulus Wealth Console — "Wealth Performance" team view with an Advisor filter that drills into a single
 * advisor's console (Kim-Johnson style). Tabs: Assets & Revenue · Opportunity & Pipeline · Compliance & Risk ·
 * Client Engagement. Left: editable AI-driven insights with Escalate / Create Action Item / Schedule Review /
 * Assign Owner / Launch Flow. Right: advisor (team view) or client (advisor view) table with Analyze and actions.
 */
const ACCENT = '#1D4ED8';
const pct1 = (v) => pct(v, 1);

export default class CumulusWealthConsole extends LightningElement {
    @api sdk;
    @api sdmName;
    @api title = 'Wealth Performance';
    @api advisor = '';
    @api accentColor = ACCENT;

    @track tab = 'assets';
    @track period = '3';
    @track advisorSel = '';
    @track months = [];
    @track hh = []; @track flows = []; @track clientFlows = []; @track goals = []; @track inter = [];
    @track insights = []; @track editing = null; @track modal = null; @track lastReport = null;
    @track loading = true; @track error;
    _unsub;
    _cache = {};
    /** memoise derived views — getters re-run on every render, and the aggregations are O(rows × months) */
    memo(key, fn) { if (!(key in this._cache)) this._cache[key] = fn(); return this._cache[key]; }
    invalidate() { this._cache = {}; }

    get isConfigured() { return Boolean(this.sdmName && this.sdmName.apiName); }
    get model() { return this.sdmName.apiName; }
    get accent() { return /^#[0-9a-fA-F]{6}$/.test(this.accentColor || '') ? this.accentColor : ACCENT; }
    get rootStyle() { return `--accent:${this.accent}`; }

    connectedCallback() {
        notify(this.sdk, 'INIT'); this.advisorSel = this.advisor || '';
        if (this.sdk && typeof this.sdk.on === 'function') this._unsub = this.sdk.on(SDK_EVENTS.FILTER_CHANGE, () => this.load());
        this.load();
    }
    disconnectedCallback() { if (typeof this._unsub === 'function') this._unsub(); }

    async load() {
        if (!this.isConfigured || !this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.loading = true; this.error = undefined;
        // The Semantic Query API caps a result at 5,000 rows, so flows are fetched at advisor × month (for trends) and at
        // household level with windowed measures (Net_Flow_L1M/L3M/L6M/L12M) instead of household × month.
        const Q = [
            query(this.sdk, this.model, { dims: [{ name: 'WM_Households.AdvisorName', alias: 'advisor' }, { name: 'WM_Households.HouseholdName', alias: 'client' }, { name: 'WM_Households.ServiceTier', alias: 'tier' }, { name: 'WM_Households.Region', alias: 'region' }, { name: 'WM_Households.RiskProfile', alias: 'risk' }, { name: 'WM_Households.Churned', alias: 'churned' }],
                measures: [{ name: 'WM_Households.AUM', alias: 'aum' }, { name: 'WM_Households.InteractionCount', alias: 'inter' }, { name: 'WM_Households.AnnualRevenue', alias: 'rev' }] }),
            query(this.sdk, this.model, { dims: [{ name: 'WM_Net_Flows.AdvisorName', alias: 'advisor' }, { name: 'WM_Net_Flows.FlowMonth', alias: 'month' }],
                measures: [{ name: 'WM_Net_Flows.NetFlow', alias: 'net' }, { name: 'WM_Net_Flows.Inflow', alias: 'inflow' }, { name: 'WM_Net_Flows.Outflow', alias: 'outflow' }] }),
            query(this.sdk, this.model, { dims: [{ name: 'WM_Net_Flows.AdvisorName', alias: 'advisor' }, { name: 'WM_Net_Flows.HouseholdName', alias: 'client' }],
                measures: [{ name: 'Net_Flow_L1M', alias: 'l1' }, { name: 'Net_Flow_L3M', alias: 'l3' }, { name: 'Net_Flow_L6M', alias: 'l6' }, { name: 'Net_Flow_L12M', alias: 'l12' }, { name: 'WM_Net_Flows.NetFlow', alias: 'all' }] }),
            query(this.sdk, this.model, { dims: [{ name: 'WM_Goals.HouseholdName', alias: 'client' }, { name: 'WM_Goals.Status', alias: 'status' }], measures: [{ name: 'WM_Goals.GoalId', agg: 'Count', alias: 'n' }] }),
            query(this.sdk, this.model, { dims: [{ name: 'WM_Interactions.AdvisorName', alias: 'advisor' }, { name: 'Interaction_Month', alias: 'month' }], measures: [{ name: 'Interaction_Count', alias: 'n' }] })
        ];
        const res = await Promise.allSettled(Q);
        const val = (i) => (res[i].status === 'fulfilled' ? res[i].value : []);
        const failed = res.map((r, i) => (r.status === 'rejected' ? `${['households', 'flows', 'client flows', 'goals', 'interactions'][i]}: ${(r.reason && (r.reason.message || (r.reason.body && r.reason.body.message))) || 'query failed'}` : null)).filter(Boolean);
        this.hh = val(0).filter((r) => r.client);
        this.flows = val(1).filter((r) => r.month).map((r) => ({ ...r, m: String(r.month).slice(0, 7) }));
        this.clientFlows = val(2).filter((r) => r.client);
        this.goals = val(3).filter((r) => r.client);
        this.inter = val(4).filter((r) => r.month);
        this.months = [...new Set(this.flows.map((r) => r.m))].sort();
        this.error = failed.length ? failed.join(' · ') : undefined;
        this.invalidate();
        this.buildInsights();
        notify(this.sdk, this.hh.length ? 'LOADED' : 'NODATA');
        this.loading = false;
    }

    // ---------- filters & drill-down ----------
    get advisors() { return [...new Set(this.hh.map((r) => r.advisor).filter(Boolean))].sort(); }
    get advisorOptions() { return [{ value: '', label: 'All advisors (team view)', selected: !this.advisorSel }].concat(this.advisors.map((a) => ({ value: a, label: a, selected: a === this.advisorSel }))); }
    get periodOptions() { return [['1', 'Last month'], ['3', 'Last 3 months'], ['6', 'Last 6 months'], ['12', 'Last 12 months'], ['24', 'All 24 months']].map(([v, l]) => ({ value: v, label: l, selected: v === this.period })); }
    onAdvisor(e) { this.advisorSel = e.target.value; this.invalidate(); this.buildInsights(); }
    onPeriod(e) { this.period = e.target.value; this.invalidate(); this.buildInsights(); }
    drill(e) { this.advisorSel = e.currentTarget.dataset.advisor; this.invalidate(); this.buildInsights(); }
    backToTeam() { this.advisorSel = ''; this.invalidate(); this.buildInsights(); }
    get isAdvisorView() { return Boolean(this.advisorSel); }
    get headerTitle() { return this.isAdvisorView ? `Wealth Advisor Console · ${this.advisorSel}` : this.title; }
    get curMonths() { return lastMonths(this.months, Number(this.period)); }
    get prevList() { return prevMonths(this.months, Number(this.period)); }
    get periodLabel() { const m = this.curMonths; return m.length ? `${m[0]} → ${m[m.length - 1]}${this.advisorSel ? ' · ' + this.advisorSel : ''}` : ''; }
    inScope(r) { return !this.advisorSel || r.advisor === this.advisorSel; }

    // ---------- aggregates ----------
    get hhScoped() { return this.memo('hhScoped', () => this.hh.filter((r) => this.inScope(r))); }
    flowsIn(monthsSet) { return this.flows.filter((r) => this.inScope(r) && monthsSet.has(r.m)); }
    get goalIndex() { return this.memo('goalIndex', () => { const idx = {}; this.goals.forEach((r) => { const g = idx[r.client] || (idx[r.client] = { on: 0, all: 0 }); g.all += num(r.n); if (r.status === 'On Track') g.on += num(r.n); }); return idx; }); }
    goalsFor(clients) { const idx = this.goalIndex; let on = 0, all = 0; clients.forEach((c) => { const g = idx[c]; if (g) { on += g.on; all += g.all; } }); return { on, all, rate: all ? on / all : 0 }; }
    totals(monthsSet) {
        return this.memo('totals:' + [...monthsSet].join(','), () => this.totalsRaw(monthsSet));
    }
    totalsRaw(monthsSet) {
        const h = this.hhScoped; const f = this.flowsIn(monthsSet); const g = this.goalsFor(h.map((r) => r.client));
        const churned = h.filter((r) => String(r.churned).toLowerCase() === 'true').length;
        return { aum: sum(h, (r) => r.aum), nna: sum(f, (r) => r.net), inflow: sum(f, (r) => r.inflow), outflow: sum(f, (r) => r.outflow), rev: sum(h, (r) => r.rev), households: h.length, churn: h.length ? churned / h.length : 0,
                 interHH: h.length ? sum(h, (r) => r.inter) / h.length : 0, goals: g.rate, interactions: sum(this.inter.filter((r) => this.inScope(r) && monthsSet.has(String(r.month).slice(0, 7))), (r) => r.n) };
    }
    monthlySeries(key) { return this.months.map((m) => { const t = this.totals(new Set([m])); return key === 'nna' ? t.nna : key === 'inflow' ? t.inflow : key === 'interactions' ? t.interactions : key === 'aum' ? t.nna : 0; }); }
    get kpis() { return this.memo('kpis', () => this.kpisRaw()); }
    kpisRaw() {
        const cur = this.totals(new Set(this.curMonths)), prev = this.totals(new Set(this.prevList));
        const card = (key, label, value, text, prevValue, fmt, upGood, seriesKey, seriesLabel) => {
            const d = signedPct(value, prevValue); const good = d ? (upGood ? d.good : !d.good) : null; const sp = sparkPath(this.monthlySeries(seriesKey));
            return { key, label, text, sub: d ? `${d.text} (${fmt(Math.abs(d.abs))}) vs. prior ${this.curMonths.length} mo` : seriesLabel, cls: `kpi ${good === null ? '' : good ? 'up' : 'down'}`, line: sp.line, area: sp.area, endx: sp.end ? sp.end[0] : 0, endy: sp.end ? sp.end[1] : 0, hasSpark: Boolean(sp.line), spark: seriesLabel };
        };
        return [card('aum', 'Total AUM', cur.aum, money(cur.aum), null, money, true, 'nna', 'monthly net flows'), card('nna', 'Net new assets', cur.nna, money(cur.nna), prev.nna, money, true, 'nna', ''),
                card('rev', 'Annual revenue', cur.rev, money(cur.rev), null, money, true, 'inflow', 'monthly inflows'), card('inter', 'Interactions', cur.interactions, intfmt(cur.interactions), prev.interactions, intfmt, true, 'interactions', ''),
                card('churn', 'Household churn', cur.churn, pct(cur.churn), null, (v) => pct(v), false, 'nna', `${intfmt(cur.households)} households`), card('goals', 'Goals on track', cur.goals, pct(cur.goals, 0), null, (v) => pct(v), true, 'inflow', 'client goals')];
    }
    /** rows for the right-hand table: advisors (team view) or clients (advisor view) */
    get rows() { return this.memo('rows', () => this.rowsRaw()); }
    rowsRaw() {
        const ms = new Set(this.curMonths);
        const key = this.isAdvisorView ? 'client' : 'advisor';
        const win = { '1': 'l1', '3': 'l3', '6': 'l6', '12': 'l12', '24': 'all' }[this.period] || 'l3';
        const by = {};
        this.hhScoped.forEach((r) => { const k = r[key]; const b = by[k] || (by[k] = { key: k, aum: 0, rev: 0, inter: 0, n: 0, churned: 0, tier: r.tier, region: r.region, risk: r.risk, clients: [] }); b.aum += num(r.aum); b.rev += num(r.rev); b.inter += num(r.inter); b.n += 1; if (String(r.churned).toLowerCase() === 'true') b.churned += 1; b.clients.push(r.client); });
        if (this.isAdvisorView) this.clientFlows.filter((r) => this.inScope(r)).forEach((r) => { const b = by[r.client]; if (b) b.net = (b.net || 0) + num(r[win]); });
        else this.flowsIn(ms).forEach((r) => { const b = by[r.advisor]; if (b) b.net = (b.net || 0) + num(r.net); });
        const rows = Object.values(by).map((b) => { const g = this.goalsFor(b.clients); return { ...b, net: b.net || 0, goals: g.rate, goalsOn: g.on, goalsAll: g.all, churnRate: b.n ? b.churned / b.n : 0 }; });
        const sorted = rank(rows, 'aum'); const n = sorted.length; const medAum = sorted[Math.floor(n / 2)] ? sorted[Math.floor(n / 2)].aum : 0;
        return sorted.map((b, i) => {
            const lowEng = b.inter / Math.max(1, b.n) < 12; const risk = this.isAdvisorView ? (String(b.churnRate) !== '0' || (lowEng && b.aum > medAum)) : b.churnRate > 0.06;
            const badge = risk ? 'AT RISK' : i < 3 ? 'TOP' : 'STEADY';
            return { ...b, idx: i + 1, badge, badgeClass: `badge ${risk ? 'slip' : i < 3 ? 'top' : 'target'}`, aumText: money(b.aum), netText: money(b.net), netClass: b.net >= 0 ? 'good' : 'bad', revText: money(b.rev), interText: intfmt(b.inter),
                     goalsText: b.goalsAll ? pct(b.goals, 0) : '–', goalsClass: b.goals >= 0.6 ? 'good' : 'bad', churnText: this.isAdvisorView ? (b.churned ? 'Churned' : 'Active') : pct(b.churnRate, 1), nText: intfmt(b.n), tierText: this.isAdvisorView ? b.tier : `${b.n} households`, canDrill: !this.isAdvisorView };
        });
    }
    get tableTitle() { return this.isAdvisorView ? 'Client Wealth Performance' : 'Advisor Performance'; }
    get colLabel() { return this.isAdvisorView ? 'Client' : 'Advisor'; }
    get colTier() { return this.isAdvisorView ? 'Tier' : 'Book'; }
    get colChurn() { return this.isAdvisorView ? 'Status' : 'Churn'; }

    // ---------- tabs → chart panel ----------
    get tabs() { return [['assets', 'Assets and Revenue'], ['pipeline', 'Opportunity & Pipeline'], ['risk', 'Compliance & Risk'], ['engage', 'Client Engagement']].map(([k, l]) => ({ key: k, label: l, cls: `tabbtn ${this.tab === k ? 'on' : ''}` })); }
    setTab(e) { this.tab = e.currentTarget.dataset.tab; }
    get chart() { return this.memo('chart:' + this.tab, () => this.chartRaw()); }
    chartRaw() {
        const rows = this.rows; const top = (key, n = 10) => rank(rows, key).slice(0, n);
        const mk = (title, sub, items, fmt, color) => { const mx = Math.max(...items.map((r) => Math.abs(num(r.v))), 1); return { title, sub, items: items.map((r) => ({ label: r.label, value: fmt(r.v), style: `width:${Math.max(2, Math.abs(num(r.v)) / mx * 100)}%;background:${r.c || color}` })) }; };
        if (this.tab === 'assets') return mk(`Today's AUM by ${this.colLabel.toLowerCase()}`, 'Period-to-date AUM, largest first', top('aum').map((r) => ({ label: r.key, v: r.aum })), money, '#1d4ed8');
        if (this.tab === 'pipeline') return mk('Net new assets by ' + this.colLabel.toLowerCase(), `Net flows ${this.periodLabel}`, rank(rows, 'net').slice(0, 10).map((r) => ({ label: r.key, v: r.net, c: r.net >= 0 ? '#0ea5e9' : '#e11d48' })), money, '#0ea5e9');
        if (this.tab === 'risk') {
            const riskItems = this.isAdvisorView
                ? rank(rows, 'inter', false).slice(0, 10).map((r) => ({ label: r.key, v: r.inter, c: r.inter < 12 ? '#e11d48' : '#7c3aed' }))
                : rank(rows, 'churnRate').slice(0, 10).map((r) => ({ label: r.key, v: r.churnRate, c: r.churnRate > 0.06 ? '#e11d48' : '#7c3aed' }));
            const riskFmt = this.isAdvisorView ? intfmt : pct1;
            return mk(this.isAdvisorView ? 'Engagement per household' : 'Household churn rate by advisor', 'Lower engagement and higher churn flag retention risk', riskItems, riskFmt, '#7c3aed');
        }
        return mk('Interactions by ' + this.colLabel.toLowerCase(), 'All interaction types, period to date', top('inter').map((r) => ({ label: r.key, v: r.inter })), intfmt, '#db2777');
    }

    // ---------- insights ----------
    get storeKey() { return `cumulusWealthConsole:${this.model}:${this.period}:${this.advisorSel}`; }
    buildInsights() {
        const rows = this.rows; if (!rows.length) { this.insights = []; return; }
        const t = this.totals(new Set(this.curMonths)); const risky = rows.filter((r) => r.badge === 'AT RISK'); const byNet = rank(rows, 'net'); const topNet = byNet[0]; const share = t.nna ? topNet.net / t.nna : 0;
        const lowGoals = rank(rows.filter((r) => r.goalsAll), 'goals', false).slice(0, 2);
        const who = this.isAdvisorView ? 'households' : 'advisors';
        const gen = [
            { sev: 'alert', title: risky.length ? `Retention exposure concentrates in ${risky.slice(0, 2).map((r) => r.key).join(' and ')} — ${risky.length} ${who} flagged at risk` : `No ${who} are flagged at risk this period`,
              body: risky.length ? `${risky.slice(0, 2).map((r) => `${r.key} (${money(r.aum)} AUM, ${intfmt(r.inter)} interactions${this.isAdvisorView ? '' : `, ${pct(r.churnRate, 1)} churn`})`).join('; ')}. Engagement below the book norm on high-value relationships is the strongest churn signal in this model — immediate outreach is warranted before the next review cycle.` : `Churn is ${pct(t.churn, 1)} across ${intfmt(t.households)} households.`,
              scope: risky.map((r) => r.key).join(', ') || 'book', actions: ['case', 'task', 'flow'] },
            { sev: 'warn', title: share > 1 || share < 0 ? `${topNet.key} alone outweighs the whole book's net new assets this period` : `${topNet.key} drives ${pct(Math.abs(share), 0)} of net new assets this period`,
              body: `${topNet.key} contributed ${money(topNet.net)} of ${money(t.nna)} net flows — ${byNet[1] ? `${(Math.abs(topNet.net) / Math.max(1, Math.abs(byNet[1].net))).toFixed(1)}× the next ${this.isAdvisorView ? 'household' : 'advisor'} (${byNet[1].key}, ${money(byNet[1].net)})` : 'the only material contributor'}. Growth this concentrated warrants a review of pipeline coverage so the result does not depend on one relationship.`,
              scope: topNet.key, actions: ['schedule', 'task', 'flow'] },
            { sev: 'info', title: lowGoals.length ? `Goal health is weakest for ${lowGoals.map((r) => r.key).join(' and ')}` : 'Goal health is even across the book',
              body: lowGoals.length ? `${lowGoals.map((r) => `${r.key}: ${r.goalsOn} of ${r.goalsAll} goals on track (${pct(r.goals, 0)})`).join('; ')}, against ${pct(t.goals, 0)} for the book. Off-track goals are the natural agenda for the next annual review and a cross-sell opening for protection and income products.` : `${pct(t.goals, 0)} of client goals are on track.`,
              scope: lowGoals.map((r) => r.key).join(', ') || 'book', actions: ['schedule', 'task', 'flow'] }
        ];
        const edits = loadEdits(this.storeKey);
        this.insights = gen.map((g, i) => ({ ...g, ...(edits[i] || {}), id: i, cls: `insight ${g.sev}`, icon: g.sev === 'alert' ? '⊘' : g.sev === 'warn' ? '⚠' : 'ⓘ', btnSchedule: g.actions.includes('schedule'), btnCase: g.actions.includes('case'), btnTask: true, taskLabel: g.actions.includes('case') ? 'Create Action Item' : 'Assign Owner' }));
    }
    get banner() { return this.memo('banner', () => this.bannerRaw()); }
    bannerRaw() {
        const rows = this.rows; if (!rows.length) return { title: 'Loading insights…', sub: '' }; const t = this.totals(new Set(this.curMonths)); const risky = rows.filter((r) => r.badge === 'AT RISK').length;
        return { title: this.isAdvisorView ? `${this.advisorSel}: ${money(t.aum)} book, ${money(t.nna)} net new assets, ${risky} household${risky === 1 ? '' : 's'} at risk` : `Portfolio growth of ${money(t.nna)} rests on a few relationships while ${risky} advisor${risky === 1 ? '' : 's'} carry elevated churn`,
                 sub: `AUM ${money(t.aum)} · churn ${pct(t.churn, 1)} · ${pct(t.goals, 0)} of goals on track · ${intfmt(t.interactions)} interactions · ${this.periodLabel}` };
    }
    editInsight(e) { const id = Number(e.currentTarget.dataset.id); const i = this.insights.find((x) => x.id === id); this.editing = { id, title: i.title, body: i.body }; }
    onEditTitle(e) { this.editing = { ...this.editing, title: e.target.value }; } onEditBody(e) { this.editing = { ...this.editing, body: e.target.value }; }
    saveInsight() { const edits = loadEdits(this.storeKey); edits[this.editing.id] = { title: this.editing.title, body: this.editing.body }; saveEdits(this.storeKey, edits); this.editing = null; this.buildInsights(); }
    cancelEdit() { this.editing = null; }
    renderedCallback() { if (!this.editing) return; this.template.querySelectorAll('[data-bind]').forEach((el) => { const v = this.editing[el.dataset.bind]; if (v !== undefined && el.value !== v) el.value = v; }); } regenerate() { saveEdits(this.storeKey, {}); clearQueryCache(); this.load(); }
    get insightCards() { return this.insights.map((i) => ({ ...i, isEditing: this.editing && this.editing.id === i.id })); }

    // ---------- analysis ----------
    analysisFor(key, question) {
        const rows = this.rows; const me = rows.find((r) => r.key === key); if (!me) return null; const top = rows[0]; const avgAum = sum(rows, (r) => r.aum) / rows.length; const avgInt = sum(rows, (r) => r.inter) / rows.length; const worst = rank(rows, 'net', false)[0];
        const risk = me.badge === 'AT RISK'; const scale = Math.max(top.aum, 1);
        const bars = [];
        if (me !== top) bars.push({ label: `${top.key} (Top)`, value: money(top.aum), pct: 100, color: '#1d4ed8' });
        bars.push({ label: 'Average', value: money(avgAum), pct: avgAum / scale * 100, color: '#f59e0b' });
        bars.push({ label: `${me.key} (${risk ? 'Risk' : me === top ? 'Top' : 'Selected'})`, value: money(me.aum), pct: me.aum / scale * 100, color: risk ? '#e11d48' : me === top ? '#1d4ed8' : '#0ea5e9' });
        return { summary: risk ? `${me.key} is a retention risk: ${money(me.aum)} of assets with ${intfmt(me.inter)} interactions this period and ${me.goalsAll ? pct(me.goals, 0) : 'no'} goals on track — engagement is not keeping pace with the size of the relationship.`
                               : `${me.key} ranks #${me.idx} of ${rows.length} by assets (${money(me.aum)}), with ${money(me.net)} net new assets and ${intfmt(me.inter)} interactions this period.`,
                 findings: [`Net new assets of ${money(me.net)} compare with ${money(top.net)} for ${top.key} and ${money(worst.net)} for ${worst.key}, the weakest in this view.`,
                            `${intfmt(me.inter)} interactions against an average of ${intfmt(avgInt)}; ${me.goalsAll ? `${me.goalsOn} of ${me.goalsAll} goals are on track (${pct(me.goals, 0)})` : 'no goals recorded'}.`,
                            `Annual revenue of ${money(me.rev)}; ${this.isAdvisorView ? `${me.tier} tier, ${me.risk} risk profile` : `${intfmt(me.n)} households, churn ${pct(me.churnRate, 1)}`}.`],
                 bars,
                 actions: [{ title: 'Engagement plan', body: `Book a review within two weeks and set a quarterly touchpoint cadence${this.isAdvisorView ? '' : ' for the flagged households'}.` }, { title: 'Goal reset', body: 'Re-baseline off-track goals and attach the protection / income products that close the gap.' }, { title: 'Pipeline coverage', body: 'Qualify two new prospects to reduce dependence on the single largest relationship.' }, { title: 'Compliance check', body: 'Confirm KYC and suitability records are current before the review.' }],
                 caveat: `Figures are period-to-date for ${this.periodLabel} from the Cumulus Wealth Management semantic model; AUM is the current household balance.` };
    }
    defaultQuestion(key) { return `Give me an in-depth analysis of ${key}. What is driving the book's performance, how does it compare to the best and worst performers, and what specific actions should ${this.isAdvisorView ? 'the advisor' : 'the team lead'} take this week?`; }
    rowAction(e) {
        const { action, key } = e.currentTarget.dataset; const me = this.rows.find((r) => r.key === key); if (!me) return; const q = this.defaultQuestion(key); const analysis = this.analysisFor(key, q);
        const base = { subjectName: key, domain: 'Wealth Insights', modelLabel: 'Cumulus Wealth Management · Tableau Next Semantic Model', slackChannel: 'wealth-leadership', insights: this.insights };
        if (action === 'analyze') this.modal = { mode: 'analyze', context: { ...base, question: q, analysis } };
        else if (action === 'report') { this.lastReport = { question: q, analysis, subject: key }; this.modal = { mode: 'report', context: { ...base, question: q, analysis } }; }
        else if (action === 'case') this.modal = { mode: 'case', context: { ...base, title: `${key}: retention follow-up`, background: analysis.summary } };
        else if (action === 'schedule') this.modal = { mode: 'schedule', context: { ...base, title: `Review: ${key}`, background: analysis.summary + ' ' + analysis.findings[0], scope: key, attendees: this.isAdvisorView ? `${this.advisorSel}, Client Service Associate` : `${key}, Wealth Team Lead` } };
        else if (action === 'flow') this.modal = { mode: 'flow', context: { ...base, title: key, background: analysis.summary } };
    }
    insightAction(e) {
        const { action, id } = e.currentTarget.dataset; const i = this.insights.find((x) => x.id === Number(id)); if (!i) return;
        this.modal = { mode: { schedule: 'schedule', case: 'case', task: 'task', flow: 'flow' }[action] || 'task', context: { title: i.title, background: i.body, scope: i.scope, attendees: this.isAdvisorView ? `${this.advisorSel}, Wealth Team Lead` : 'Wealth Team Lead, Advisors', insights: this.insights, subjectName: i.scope, slackChannel: 'wealth-leadership' } };
    }
    onReask(e) { if (!this.modal) return; const c = this.modal.context; this.modal = { ...this.modal, context: { ...c, question: e.detail.question, analysis: this.analysisFor(c.subjectName, e.detail.question) || c.analysis } }; }
    closeModal() { if (this.modal && this.modal.mode === 'analyze' && this.modal.context.analysis) this.lastReport = { question: this.modal.context.question, analysis: this.modal.context.analysis, subject: this.modal.context.subjectName }; this.modal = null; }
    get modalOpen() { return Boolean(this.modal); } get modalMode() { return this.modal ? this.modal.mode : 'task'; } get modalContext() { return this.modal ? this.modal.context : {}; }
    get hasReport() { return Boolean(this.lastReport); }
    openReportModal() { if (this.lastReport) this.modal = { mode: 'report', context: { question: this.lastReport.question, analysis: this.lastReport.analysis, subjectName: this.lastReport.subject, slackChannel: 'wealth-leadership' } }; }
}
