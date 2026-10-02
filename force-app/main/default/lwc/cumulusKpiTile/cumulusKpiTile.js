import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, buildQuery, normalizeRows, formatValue } from 'c/cumulusSdkUtils';

/**
 * Cumulus KPI Tile — a dynamically bound call-out card: centred big number, monthly trend
 * sparkline, change vs the prior period, optional target, and *significance colouring*:
 *   |change| >= 10%  -> strong tint + coloured number (green improving / red worsening)
 *   |change| >=  3%  -> coloured outline
 *   otherwise        -> neutral (the tile's accent colour)
 * "Improving" respects the metric's direction (sentiment UpIsGood / UpIsBad).
 * The author picks the semantic model, the measure, the trend dimension and (optionally) a
 * different measure for the sparkline in the widget panel; this code never names a field.
 */
const GOOD = '#15803D';
const BAD = '#DC2626';

export default class CumulusKpiTile extends LightningElement {
    @api sdk; // injected by the dashboard runtime
    @api sdmName; // SemanticModel  {apiName, id, label}
    @api measureField; // SemanticMeasure {name, aggregation, label}
    @api trendDimension; // SemanticDimension — a month-grain field for the sparkline + period delta
    @api trendMeasureField; // optional SemanticMeasure drawn in the sparkline instead of measureField (e.g. monthly flows under an AUM total)
    @api trendLabel; // optional caption for the sparkline ("monthly net flows")
    @api title;
    @api target; // optional numeric target
    @api sentiment = 'UpIsGood'; // UpIsGood | UpIsBad
    @api format = 'number'; // number | currency | percent
    @api accentColor = '#0B5CAB'; // neutral colour for this tile
    @api strongThreshold = 10; // % change that counts as significant
    @api moderateThreshold = 3;

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
    get trendMeasure() {
        return this.trendMeasureField && this.trendMeasureField.name ? this.trendMeasureField : this.measureField;
    }
    get trendIsOtherMeasure() {
        return this.trendMeasure !== this.measureField;
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
    get onTrack() {
        if (!this.hasTarget || this.value === null) return null;
        const d = Number(this.value) - Number(this.target);
        return this.sentiment === 'UpIsBad' ? d <= 0 : d >= 0;
    }
    get targetText() {
        if (!this.hasTarget) return '';
        return `target ${formatValue(this.target, this.format)} · ${this.onTrack ? 'on track' : 'off track'}`;
    }
    /** last point vs the one before it — "vs prior month" */
    get periodDelta() {
        const s = this.series;
        if (s.length < 2) return null;
        const a = Number(s[s.length - 1].val), b = Number(s[s.length - 2].val);
        if (Number.isNaN(a) || Number.isNaN(b)) return null;
        return { abs: a - b, pct: b ? ((a - b) / Math.abs(b)) * 100 : null };
    }
    get periodText() {
        const p = this.periodDelta;
        if (!p) return this.hasTarget ? '' : 'no prior period';
        const fmt = this.trendIsOtherMeasure ? (this.trendMeasureField.format || this.format) : this.format;
        const absTxt = fmt === 'percent' ? `${(Math.abs(p.abs) * 100).toFixed(1)} pts` : formatValue(Math.abs(p.abs), fmt);
        const pct = p.pct === null ? '' : ` (${Math.abs(p.pct).toFixed(1)}%)`;
        return `${p.abs >= 0 ? '▲' : '▼'} ${absTxt}${pct} vs prior month`;
    }
    get periodGood() {
        const p = this.periodDelta;
        if (!p) return null;
        return this.sentiment === 'UpIsBad' ? p.abs <= 0 : p.abs >= 0;
    }
    /** significance: strong / moderate / flat, from the period change (or the target gap when there is no trend) */
    get magnitude() {
        const p = this.periodDelta;
        if (p && p.pct !== null) return Math.abs(p.pct);
        if (this.hasTarget && this.value !== null && Number(this.target)) return Math.abs((Number(this.value) - Number(this.target)) / Number(this.target)) * 100;
        return 0;
    }
    get tier() {
        const m = this.magnitude;
        if (m >= Number(this.strongThreshold)) return 'strong';
        if (m >= Number(this.moderateThreshold)) return 'moderate';
        return 'flat';
    }
    get isGood() {
        const g = this.periodGood;
        return g === null ? this.onTrack : g;
    }
    get toneColor() {
        if (this.tier === 'flat' || this.isGood === null) return this.safeColor;
        return this.isGood ? GOOD : BAD;
    }
    get tileClass() {
        return `tile tier-${this.tier}`;
    }
    get tileStyle() {
        return `--accent:${this.safeColor};--tone:${this.toneColor}`;
    }
    get safeColor() {
        return /^#[0-9a-fA-F]{6}$/.test(this.accentColor || '') ? this.accentColor : '#0B5CAB';
    }
    get pillClass() {
        const g = this.periodGood;
        return `pill ${g === null ? 'pill-flat' : g ? 'pill-good' : 'pill-bad'}`;
    }
    get sparkCaption() {
        if (this.trendLabel) return this.trendLabel;
        return this.trendIsOtherMeasure ? (this.trendMeasureField.label || '').toLowerCase() : '';
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
        const tm = this.trendMeasure;
        const key = this.isConfigured
            ? `${this.sdmName.apiName}|${this.measureField.name}|${this.measureField.aggregation}|${this.hasTrend ? this.trendDimension.name : ''}|${tm.name}|${tm.aggregation}`
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
                    const q = buildQuery({ dimensionField: this.trendDimension, measureField: this.trendMeasure, limit: 60, sortByDim: true });
                    const trend = await this.sdk.fetchDataUsingQueryAndSource(q, this.sdmName.apiName);
                    // drop null / blank months (e.g. households that never churned have no Churn Month)
                    this.series = normalizeRows(trend).filter((r) => r.dim !== null && r.dim !== undefined && String(r.dim).trim() !== '' && !/^null$/i.test(String(r.dim)));
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
