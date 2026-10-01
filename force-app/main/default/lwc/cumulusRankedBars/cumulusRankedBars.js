import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, buildQuery, normalizeRows, formatValue } from 'c/cumulusSdkUtils';

/**
 * Cumulus Ranked Bars — Top-N horizontal bars for any dimension/measure pair.
 * Clicking (or pressing Enter/Space on) a bar publishes a dashboard filter on the bound
 * dimension; clicking it again clears the selection.
 */
export default class CumulusRankedBars extends LightningElement {
    @api sdk;
    @api sdmName; // SemanticModel
    @api dimensionField; // SemanticDimension
    @api measureField; // SemanticMeasure
    @api title;
    @api topN = 10;
    @api format = 'number';

    @track rows = [];
    @track error;
    selected = null;
    _unsubscribe;
    _lastKey;

    get isConfigured() {
        return Boolean(this.sdmName && this.sdmName.apiName && this.dimensionField && this.dimensionField.name && this.measureField && this.measureField.name);
    }
    get heading() {
        return this.title || (this.isConfigured ? `${this.measureField.label} by ${this.dimensionField.label}` : 'Ranked Bars');
    }
    get bars() {
        const max = Math.max(...this.rows.map((r) => Math.abs(Number(r.val)) || 0), 1);
        return this.rows.map((r, i) => ({
            key: `${i}-${r.dim}`,
            label: r.dim === null || r.dim === undefined ? '(blank)' : String(r.dim),
            value: r.dim,
            display: formatValue(r.val, this.format),
            style: `width:${Math.max(2, (Math.abs(Number(r.val)) / max) * 100)}%`,
            cls: `bar ${this.selected === r.dim ? 'selected' : ''}`,
            pressed: this.selected === r.dim ? 'true' : 'false'
        }));
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
        const key = this.isConfigured ? `${this.sdmName.apiName}|${this.dimensionField.name}|${this.measureField.name}|${this.measureField.aggregation}|${this.topN}` : '';
        if (key !== this._lastKey) {
            this._lastKey = key;
            this.load();
        }
    }

    async load() {
        if (!this.isConfigured) {
            notify(this.sdk, 'ERROR', { message: 'Map a semantic model, a dimension and a measure in the widget panel.' });
            return;
        }
        if (!this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.error = undefined;
        try {
            const limit = Math.max(1, Math.min(50, Number(this.topN) || 10));
            const query = buildQuery({ dimensionField: this.dimensionField, measureField: this.measureField, limit: limit + 1 });
            const result = await this.sdk.fetchDataUsingQueryAndSource(query, this.sdmName.apiName);
            const rows = normalizeRows(result).filter((r) => r.dim !== null && r.dim !== undefined && r.dim !== '');
            rows.sort((a, b) => Number(b.val) - Number(a.val));
            this.rows = rows.slice(0, limit);
            notify(this.sdk, this.rows.length ? 'LOADED' : 'NODATA');
        } catch (e) {
            this.error = (e && e.message) || 'Query failed';
            notify(this.sdk, 'ERROR', { message: this.error });
        }
    }

    handleSelect(event) {
        const value = event.currentTarget.dataset.value;
        this.applySelection(value);
    }
    handleKey(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            this.applySelection(event.currentTarget.dataset.value);
        }
    }
    applySelection(value) {
        if (!this.sdk || !this.sdk.actions) return;
        const next = this.selected === value ? null : value;
        this.selected = next;
        // Publish (or clear) the filter on the bound dimension. Empty values = no filter.
        this.sdk.actions.applyFilter({
            fieldOrFields: this.dimensionField.name,
            values: next === null ? [] : [next],
            operator: 'In',
            dataSourceName: this.sdmName.apiName
        });
    }
}
