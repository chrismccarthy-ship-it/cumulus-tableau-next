import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, buildQuery, normalizeRows, formatValue } from 'c/cumulusSdkUtils';

/**
 * Cumulus KPI Tile — a dynamically bound big-number widget with an optional target, sentiment,
 * accent colour and a sparkline over a time dimension. The dashboard author picks the semantic
 * model, the measure and (optionally) the trend dimension in the widget panel; this code never
 * hard-codes a field name.
 */
export default class CumulusKpiTile extends LightningElement {
    @api sdk; // injected by the dashboard runtime
    @api sdmName; // SemanticModel  {apiName, id, label}
    @api measureField; // SemanticMeasure {name, aggregation, label}
    @api trendDimension; // optional SemanticDimension (a month / date field) for the sparkline + period delta
    @api title;
    @api target; // optional numeric target
    @api sentiment = 'UpIsGood'; // UpIsGood | UpIsBad
    @api format = 'number'; // number | currency | percent
    @api accentColor = '#0B5CAB'; // hex; lets each tile on a row carry its own colour

    @track value = null;
    @track series = []; // [{dim, val}] ascending by dim
    @track error;
    loading = false;
    _unsubscribe;
    _lastKey;

    get isConfigured() {
        return Boolean(this.sdmName && this.sdmName.apiName && this.measureField && this.measureField.name);
    }
    get hasTrend() {
        return Boolean(this.trendDimension && this.trendDimension.name);
    }
    get heading() {
        return this.title || (this.measureField && this.measureField.label) || 'KPI';
    }
    get display() {
        return formatValue(this.value, this.format);
    }
    get hasTarget() {
        return this.target !== undefined && this.target !== null && this.target !== '' && !Number.isNaN(Number(this.target));
    }
    get delta() {
        if (!this.hasTarget || this.value === null) return null;
        return Number(this.value) - Number(this.target);
    }
    get deltaText() {
        const d = this.delta;
        if (d === null) return '';
        return `${d >= 0 ? '+' : ''}${formatValue(d, this.format)} vs target ${formatValue(this.target, this.format)}`;
    }
    /** last point vs the one before it — "vs prior period" */
    get periodDelta() {
        const s = this.series;
        if (s.length < 2) return null;
        const a = Number(s[s.length - 1].val), b = Number(s[s.length - 2].val);
        if (Number.isNaN(a) || Number.isNaN(b)) return null;
        return { abs: a - b, pct: b ? ((a - b) / Math.abs(b)) * 100 : null };
    }
    get periodText() {
        const p = this.periodDelta;
        if (!p) return '';
        const pct = p.pct === null ? '' : ` (${p.pct >= 0 ? '+' : ''}${p.pct.toFixed(1)}%)`;
        return `${p.abs >= 0 ? '▲' : '▼'} ${formatValue(Math.abs(p.abs), this.format)}${pct} vs prior period`;
    }
    get periodGood() {
        const p = this.periodDelta;
        if (!p) return null;
        return this.sentiment === 'UpIsBad' ? p.abs <= 0 : p.abs >= 0;
    }
    get good() {
        const d = this.delta;
        if (d === null) return this.periodGood;
        return this.sentiment === 'UpIsBad' ? d <= 0 : d >= 0;
    }
    get tileClass() {
        const g = this.good;
        return `tile ${g === null ? '' : g ? 'good' : 'bad'}`;
    }
    get tileStyle() {
        return `--accent:${this.safeColor}`;
    }
    get safeColor() {
        return /^#[0-9a-fA-F]{6}$/.test(this.accentColor || '') ? this.accentColor : '#0B5CAB';
    }
    get pillClass() {
        const g = this.periodGood;
        return `pill ${g === null ? '' : g ? 'pill-good' : 'pill-bad'}`;
    }
    /** SVG sparkline geometry (viewBox 200×40) */
    get sparkPath() {
        const pts = this.sparkPoints;
        return pts.length ? 'M' + pts.map((p) => `${p[0]},${p[1]}`).join('L') : '';
    }
    get sparkArea() {
        const pts = this.sparkPoints;
        if (!pts.length) return '';
        return `${this.sparkPath}L${pts[pts.length - 1][0]},40L${pts[0][0]},40Z`;
    }
    get sparkEnd() {
        const pts = this.sparkPoints;
        return pts.length ? { cx: pts[pts.length - 1][0], cy: pts[pts.length - 1][1] } : null;
    }
    get sparkPoints() {
        const vals = this.series.map((r) => Number(r.val)).filter((v) => !Number.isNaN(v));
        if (vals.length < 2) return [];
        const max = Math.max(...vals), min = Math.min(...vals), span = max - min || 1;
        return vals.map((v, i) => [2 + (i * 196) / (vals.length - 1), 36 - ((v - min) / span) * 30]);
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
        // re-query when the author changes a binding in the widget panel
        const key = this.isConfigured
            ? `${this.sdmName.apiName}|${this.measureField.name}|${this.measureField.aggregation}|${this.hasTrend ? this.trendDimension.name : ''}`
            : '';
        if (key !== this._lastKey) {
            this._lastKey = key;
            this.load();
        }
    }

    async load() {
        if (!this.isConfigured) {
            notify(this.sdk, 'ERROR', { message: 'Select a semantic model and a measure in the widget panel.' });
            return;
        }
        if (!this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.loading = true;
        this.error = undefined;
        try {
            const total = await this.sdk.fetchDataUsingQueryAndSource(buildQuery({ measureField: this.measureField, limit: 1 }), this.sdmName.apiName);
            const rows = normalizeRows(total);
            this.value = rows.length ? rows[0].val : null;
            this.series = [];
            if (this.hasTrend) {
                // the sparkline is decoration: a trend-query failure must never take the whole tile down
                try {
                    const q = buildQuery({ dimensionField: this.trendDimension, measureField: this.measureField, limit: 60, sortByDim: true });
                    const trend = await this.sdk.fetchDataUsingQueryAndSource(q, this.sdmName.apiName);
                    this.series = normalizeRows(trend).filter((r) => r.dim !== null && r.dim !== undefined);
                } catch (e) {
                    this.series = [];
                }
            }
            notify(this.sdk, rows.length ? 'LOADED' : 'NODATA');
        } catch (e) {
            // show the message inside the tile; an ERROR lifecycle event makes the host replace the widget with "Something Went Wrong"
            this.error = (e && (e.message || (e.body && e.body.message))) || (typeof e === 'string' ? e : 'Query failed');
            this.value = null;
            notify(this.sdk, 'NODATA');
        } finally {
            this.loading = false;
        }
    }
}
