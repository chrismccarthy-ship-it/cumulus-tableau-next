import { LightningElement, api, track } from 'lwc';
import { SDK_EVENTS, notify, fieldExpression, aggregationMethod, normalizeRows, formatValue } from 'c/cumulusSdkUtils';

/**
 * Cumulus Next Best Actions — a ranked worklist built from any semantic model:
 * entity (who), context (why), score (how urgent). Lowest or highest score first.
 * Selecting a row filters the dashboard to that entity so the charts explain the case.
 * Re-bind it to a different model (households → advisors' clients → policies) without redeploying.
 */
export default class CumulusNextBestActions extends LightningElement {
    @api sdk;
    @api sdmName; // SemanticModel
    @api entityField; // SemanticDimension — e.g. Household Name
    @api contextField; // SemanticDimension — e.g. Segment / Event Type
    @api scoreField; // SemanticMeasure — e.g. Product Count (Avg), Opportunity Value (Sum)
    @api title = 'Next Best Actions';
    @api actionLabel = 'Review';
    @api lowestFirst = false; // true = lowest score is the most urgent (e.g. fewest products)
    @api topN = 8;
    @api format = 'number';

    @track items = [];
    @track error;
    selected = null;
    _unsubscribe;
    _lastKey;

    get isConfigured() {
        return Boolean(this.sdmName && this.sdmName.apiName && this.entityField && this.entityField.name && this.scoreField && this.scoreField.name);
    }
    get hasContext() {
        return Boolean(this.contextField && this.contextField.name);
    }
    get scoreLabel() {
        return this.isConfigured ? this.scoreField.label : '';
    }
    get list() {
        return this.items.map((r, i) => ({
            key: `${i}-${r.entity}`,
            rank: i + 1,
            entity: r.entity,
            context: r.context,
            score: formatValue(r.score, this.format),
            cls: `item ${this.selected === r.entity ? 'selected' : ''}`,
            pressed: this.selected === r.entity ? 'true' : 'false'
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
        const key = this.isConfigured ? `${this.sdmName.apiName}|${this.entityField.name}|${this.hasContext ? this.contextField.name : ''}|${this.scoreField.name}|${this.scoreField.aggregation}|${this.lowestFirst}|${this.topN}` : '';
        if (key !== this._lastKey) {
            this._lastKey = key;
            this.load();
        }
    }

    async load() {
        if (!this.isConfigured) {
            notify(this.sdk, 'ERROR', { message: 'Map a semantic model, an entity dimension and a score measure in the widget panel.' });
            return;
        }
        if (!this.sdk || typeof this.sdk.fetchDataUsingQueryAndSource !== 'function') return;
        this.error = undefined;
        try {
            const fields = [{ expression: fieldExpression(this.entityField.name), alias: 'entity', rowGrouping: true }];
            if (this.hasContext) fields.push({ expression: fieldExpression(this.contextField.name), alias: 'context', rowGrouping: true });
            const score = { expression: fieldExpression(this.scoreField.name), alias: 'score', rowGrouping: false };
            if (String(this.scoreField.name).includes('.')) score.semanticAggregationMethod = aggregationMethod(this.scoreField);
            fields.push(score);
            const query = { fields, options: { limitOptions: { limit: 200 } } };
            const result = await this.sdk.fetchDataUsingQueryAndSource(query, this.sdmName.apiName);
            const raw = this.rowsOf(result);
            const dir = this.lowestFirst === true || this.lowestFirst === 'true' ? 1 : -1;
            raw.sort((a, b) => dir * (Number(a.score) - Number(b.score)));
            this.items = raw.filter((r) => r.entity).slice(0, Math.max(1, Math.min(50, Number(this.topN) || 8)));
            notify(this.sdk, this.items.length ? 'LOADED' : 'NODATA');
        } catch (e) {
            this.error = (e && e.message) || 'Query failed';
            notify(this.sdk, 'ERROR', { message: this.error });
        }
    }

    /** rows come back positionally in field order: entity[, context], score */
    rowsOf(result) {
        let rows = result;
        if (result && result.queryResults && result.queryResults.queryData) rows = result.queryResults.queryData.rows;
        else if (result && result.queryData) rows = result.queryData.rows;
        else if (result && result.rows) rows = result.rows;
        else if (result && result.data) rows = result.data;
        if (!Array.isArray(rows)) return normalizeRows(result).map((r) => ({ entity: r.dim, context: '', score: r.val }));
        return rows.map((r) => {
            const v = Array.isArray(r) ? r : Array.isArray(r && r.values) ? r.values : [r.entity, r.context, r.score];
            return this.hasContext ? { entity: v[0], context: v[1], score: v[2] } : { entity: v[0], context: '', score: v[1] };
        });
    }

    handleSelect(event) {
        this.applySelection(event.currentTarget.dataset.value);
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
        this.sdk.actions.applyFilter({
            fieldOrFields: this.entityField.name,
            values: next === null ? [] : [next],
            operator: 'In',
            dataSourceName: this.sdmName.apiName
        });
    }
}
