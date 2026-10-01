import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, buildQuery, normalizeRows, formatValue } from 'c/cumulusSdkUtils';

/**
 * Cumulus Threshold Banner — compares a bound measure with a threshold and turns the banner
 * red when it is breached. Optionally offers a one-click "focus" filter on a bound dimension
 * value (e.g. filter the dashboard to the offending line of business).
 */
export default class CumulusThresholdBanner extends LightningElement {
    @api sdk;
    @api sdmName; // SemanticModel
    @api measureField; // SemanticMeasure
    @api threshold; // number
    @api belowIsBad = false; // default: above the threshold is bad
    @api okMessage = 'Within target';
    @api alertMessage = 'Above threshold — attention needed';
    @api format = 'number';
    @api focusDimension; // optional SemanticDimension
    @api focusValue; // optional String value to filter the dashboard to

    @track value = null;
    @track error;
    focused = false;
    _unsubscribe;
    _lastKey;

    get isConfigured() {
        return Boolean(this.sdmName && this.sdmName.apiName && this.measureField && this.measureField.name && this.threshold !== undefined && this.threshold !== '');
    }
    get breached() {
        if (this.value === null) return false;
        const below = this.belowIsBad === true || this.belowIsBad === 'true';
        return below ? Number(this.value) < Number(this.threshold) : Number(this.value) > Number(this.threshold);
    }
    get bannerClass() {
        return `banner ${this.breached ? 'alert' : 'ok'}`;
    }
    get message() {
        return this.breached ? this.alertMessage : this.okMessage;
    }
    get detail() {
        return `${this.measureField ? this.measureField.label : ''}: ${formatValue(this.value, this.format)} (threshold ${formatValue(this.threshold, this.format)})`;
    }
    get canFocus() {
        return Boolean(this.focusDimension && this.focusDimension.name && this.focusValue);
    }
    get focusLabel() {
        return this.focused ? 'Clear focus' : `Focus on ${this.focusValue}`;
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
        const key = this.isConfigured ? `${this.sdmName.apiName}|${this.measureField.name}|${this.measureField.aggregation}|${this.threshold}` : '';
        if (key !== this._lastKey) {
            this._lastKey = key;
            this.load();
        }
    }

    async load() {
        if (!this.isConfigured) {
            notify(this.sdk, 'ERROR', { message: 'Map a semantic model, a measure and a threshold in the widget panel.' });
            return;
        }
        if (!this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.error = undefined;
        try {
            const result = await this.sdk.fetchDataUsingQueryAndSource(buildQuery({ measureField: this.measureField, limit: 1 }), this.sdmName.apiName);
            const rows = normalizeRows(result);
            this.value = rows.length ? rows[0].val : null;
            notify(this.sdk, rows.length ? 'LOADED' : 'NODATA');
        } catch (e) {
            this.error = (e && e.message) || 'Query failed';
            notify(this.sdk, 'ERROR', { message: this.error });
        }
    }

    handleFocus() {
        if (!this.sdk || !this.sdk.actions || !this.canFocus) return;
        this.focused = !this.focused;
        this.sdk.actions.applyFilter({
            fieldOrFields: this.focusDimension.name,
            values: this.focused ? [this.focusValue] : [],
            operator: 'In',
            dataSourceName: this.sdmName.apiName
        });
    }
}
