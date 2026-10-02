import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, buildQuery, normalizeRows, formatValue, fieldExpression, aggregationMethod } from 'c/cumulusSdkUtils';
import { VIEWBOX, PATHS, CENTROIDS, NAMES, REGIONS, toStateCode } from 'c/cumulusUsStates';

/**
 * Cumulus State Map — a US choropleth (shade = measure) with optional proportional bubbles
 * (bubble = second measure), bound to any semantic model. The geography dimension may hold
 * state codes, state names, "Cumulus GA Branch 1" style names, or Cumulus region names
 * (Midwest, Pacific, …), which are painted onto their member states.
 * Clicking a state publishes a dashboard filter on the bound dimension; click again to clear.
 */
export default class CumulusStateMap extends LightningElement {
    @api sdk;
    @api sdmName; // SemanticModel
    @api dimensionField; // SemanticDimension: state / region
    @api measureField; // SemanticMeasure: shade
    @api bubbleMeasureField; // optional SemanticMeasure: bubble size
    @api title;
    @api subtitle;
    @api format = 'number';
    @api bubbleFormat = 'number';
    @api lowColor = '#DBEAFE';
    @api highColor = '#1D4ED8';
    @api bubbleColor = '#F59E0B';
    @api showLabels = false;

    @track rows = []; // [{code|region, val, bub}]
    @track error;
    selected = null;
    _unsubscribe;
    _lastKey;
    viewBox = VIEWBOX;

    get isConfigured() {
        return Boolean(this.sdmName && this.sdmName.apiName && this.dimensionField && this.dimensionField.name && this.measureField && this.measureField.name);
    }
    get hasBubble() {
        return Boolean(this.bubbleMeasureField && this.bubbleMeasureField.name);
    }
    get heading() {
        return this.title || (this.isConfigured ? `${this.measureField.label} by ${this.dimensionField.label}` : 'State Map');
    }
    get regionMode() {
        return this.rows.some((r) => REGIONS[r.key]);
    }
    /** value lookup per state code (region rows fan out to member states) */
    get byState() {
        const out = {};
        this.rows.forEach((r) => {
            if (REGIONS[r.key]) REGIONS[r.key].forEach((c) => { out[c] = { ...r, label: r.key }; });
            else if (PATHS[r.key]) out[r.key] = { ...r, label: NAMES[r.key] || r.key };
        });
        return out;
    }
    get states() {
        const data = this.byState;
        const vals = Object.values(data).map((d) => Number(d.val)).filter((v) => !Number.isNaN(v));
        const mn = Math.min(...vals), mx = Math.max(...vals);
        const bubs = Object.values(data).map((d) => Number(d.bub)).filter((v) => !Number.isNaN(v) && v > 0);
        const bm = bubs.length ? Math.max(...bubs) : 0;
        return Object.keys(PATHS).map((code) => {
            const d = data[code];
            const has = Boolean(d) && !Number.isNaN(Number(d.val));
            const t = has && mx > mn ? (Number(d.val) - mn) / (mx - mn) : has ? 0.6 : 0;
            const c = CENTROIDS[code] || [0, 0];
            const bub = has && this.hasBubble && Number(d.bub) > 0 && bm ? 6 + 30 * Math.sqrt(Number(d.bub) / bm) : 0;
            const key = d ? d.key : null;
            const tip = has
                ? `${d.label}: ${this.measureField.label} ${formatValue(d.val, this.format)}${this.hasBubble && d.bub !== undefined ? ` · ${this.bubbleMeasureField.label} ${formatValue(d.bub, this.bubbleFormat)}` : ''}`
                : NAMES[code] || code;
            return {
                code, d: PATHS[code], tip, key,
                fill: has ? this.mix(this.safe(this.lowColor, '#DBEAFE'), this.safe(this.highColor, '#1D4ED8'), t) : '#EEF2F7',
                cls: `state ${has ? 'has' : ''} ${this.selected !== null && this.selected === key ? 'selected' : ''} ${this.selected !== null && this.selected !== key ? 'dim' : ''}`,
                cx: c[0], cy: c[1], r: bub, hasBubble: bub > 0,
                showLabel: has && (this.showLabels === true || this.showLabels === 'true') && !this.regionMode
            };
        });
    }
    get regionLabels() {
        if (!this.regionMode) return [];
        return this.rows.filter((r) => REGIONS[r.key]).map((r) => {
            const cs = REGIONS[r.key].map((c) => CENTROIDS[c]).filter(Boolean);
            return { key: r.key, x: cs.reduce((a, c) => a + c[0], 0) / cs.length, y: cs.reduce((a, c) => a + c[1], 0) / cs.length + 5 };
        });
    }
    get legend() {
        const vals = Object.values(this.byState).map((d) => Number(d.val)).filter((v) => !Number.isNaN(v));
        if (!vals.length) return null;
        return { lo: formatValue(Math.min(...vals), this.format), hi: formatValue(Math.max(...vals), this.format),
                 style: `background:linear-gradient(90deg,${this.safe(this.lowColor, '#DBEAFE')},${this.safe(this.highColor, '#1D4ED8')})`,
                 bubbleStyle: `background:${this.safe(this.bubbleColor, '#F59E0B')}`, bubbleLabel: this.hasBubble ? `bubble = ${this.bubbleMeasureField.label}` : '' };
    }
    get bubbleFill() {
        return this.safe(this.bubbleColor, '#F59E0B');
    }
    safe(c, fb) {
        return /^#[0-9a-fA-F]{6}$/.test(c || '') ? c : fb;
    }
    mix(a, b, t) {
        const h = (x) => [1, 3, 5].map((i) => parseInt(x.slice(i, i + 2), 16));
        const A = h(a), B = h(b);
        return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
    }

    connectedCallback() {
        notify(this.sdk, 'INIT');
        if (this.sdk && typeof this.sdk.on === 'function') {
            this._unsubscribe = this.sdk.on(SDK_EVENTS.FILTER_CHANGE, () => this.load());
        }
        this.load();
    }
    disconnectedCallback() {
        if (typeof this._unsubscribe === 'function') this._unsubscribe();
    }
    renderedCallback() {
        const key = this.isConfigured
            ? `${this.sdmName.apiName}|${this.dimensionField.name}|${this.measureField.name}|${this.measureField.aggregation}|${this.hasBubble ? this.bubbleMeasureField.name + this.bubbleMeasureField.aggregation : ''}`
            : '';
        if (key !== this._lastKey) {
            this._lastKey = key;
            this.load();
        }
    }

    buildMapQuery() {
        const q = buildQuery({ dimensionField: this.dimensionField, measureField: this.measureField, limit: 200, sortDesc: true });
        if (this.hasBubble) {
            const b = { expression: fieldExpression(this.bubbleMeasureField.name), alias: 'bub', rowGrouping: false };
            if (String(this.bubbleMeasureField.name).includes('.')) b.semanticAggregationMethod = aggregationMethod(this.bubbleMeasureField);
            q.fields.push(b);
        }
        return q;
    }

    async load() {
        if (!this.isConfigured) {
            notify(this.sdk, 'ERROR', { message: 'Map a semantic model, a state/region dimension and a measure in the widget panel.' });
            return;
        }
        if (!this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.error = undefined;
        try {
            const result = await this.sdk.fetchDataUsingQueryAndSource(this.buildMapQuery(), this.sdmName.apiName);
            // rows come back as [dim, val(, bub)]; normalizeRows keeps first and last, so read the raw shape when a bubble is present
            const raw = this.hasBubble ? this.rawRows(result) : normalizeRows(result).map((r) => ({ dim: r.dim, val: r.val, bub: undefined }));
            const rows = [];
            raw.forEach((r) => {
                if (r.dim === null || r.dim === undefined || r.dim === '') return;
                const dimStr = String(r.dim).trim();
                const key = REGIONS[dimStr] ? dimStr : toStateCode(dimStr);
                if (!key) return;
                const prev = rows.find((x) => x.key === key);
                if (prev) { prev.val = Number(prev.val) + Number(r.val || 0); if (r.bub !== undefined) prev.bub = Number(prev.bub || 0) + Number(r.bub || 0); }
                else rows.push({ key, dimValue: r.dim, val: r.val, bub: r.bub });
            });
            this.rows = rows;
            notify(this.sdk, rows.length ? 'LOADED' : 'NODATA');
        } catch (e) {
            this.error = (e && (e.message || (e.body && e.body.message))) || 'Query failed';
            this.rows = [];
            notify(this.sdk, 'NODATA');
        }
    }
    rawRows(result) {
        let rows = result;
        if (result && result.queryResults && result.queryResults.queryData) rows = result.queryResults.queryData.rows;
        else if (result && result.queryData) rows = result.queryData.rows;
        else if (result && result.rows) rows = result.rows;
        if (!Array.isArray(rows)) return [];
        return rows.map((r) => {
            const v = Array.isArray(r) ? r : r && Array.isArray(r.values) ? r.values : [r.dim, r.val, r.bub];
            return { dim: v[0], val: v[1], bub: v[2] };
        });
    }

    handleSelect(event) {
        const key = event.currentTarget.dataset.key;
        if (!key || key === 'null') return;
        const row = this.rows.find((r) => r.key === key);
        if (!row || !this.sdk || !this.sdk.actions) return;
        const next = this.selected === key ? null : key;
        this.selected = next;
        this.sdk.actions.applyFilter({
            fieldOrFields: this.dimensionField.name,
            values: next === null ? [] : [row.dimValue],
            operator: 'In',
            dataSourceName: this.sdmName.apiName
        });
    }
    handleKey(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            this.handleSelect(event);
        }
    }
}
