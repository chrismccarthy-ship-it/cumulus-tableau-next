import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, buildQuery, normalizeRows, formatValue } from 'c/cumulusSdkUtils';

/**
 * Cumulus Chart Headline — the centred title block that sits above a chart: a short, impactful
 * headline, a one-line subtitle and (optionally) a live summary statistic bound to a measure
 * ("Avg handle time · 18.4 min"), which re-queries when dashboard filters change.
 */
export default class CumulusChartHeadline extends LightningElement {
    @api sdk;
    @api sdmName; // SemanticModel (only needed when a stat measure is bound)
    @api measureField; // optional SemanticMeasure for the stat chip
    @api title;
    @api subtitle;
    @api statLabel; // e.g. "Avg handle time"
    @api statSuffix = ''; // e.g. " min"
    @api format = 'number';
    @api accentColor = '#0B5CAB';

    @track value = null;
    _unsubscribe;
    _lastKey;

    get hasStat() {
        return Boolean(this.sdmName && this.sdmName.apiName && this.measureField && this.measureField.name);
    }
    get statText() {
        if (!this.hasStat) return '';
        return `${this.statLabel || this.measureField.label} · ${formatValue(this.value, this.format)}${this.statSuffix || ''}`;
    }
    get style() {
        return `--accent:${/^#[0-9a-fA-F]{6}$/.test(this.accentColor || '') ? this.accentColor : '#0B5CAB'}`;
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
        const key = this.hasStat ? `${this.sdmName.apiName}|${this.measureField.name}|${this.measureField.aggregation}` : '';
        if (key !== this._lastKey) {
            this._lastKey = key;
            this.load();
        }
    }
    async load() {
        if (!this.hasStat) {
            notify(this.sdk, 'LOADED');
            return;
        }
        if (!this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        try {
            const r = await this.sdk.fetchDataUsingQueryAndSource(buildQuery({ measureField: this.measureField, limit: 1 }), this.sdmName.apiName);
            const rows = normalizeRows(r);
            this.value = rows.length ? rows[0].val : null;
        } catch (e) {
            this.value = null; // the headline still renders; the stat shows "–"
        }
        notify(this.sdk, 'LOADED');
    }
}
