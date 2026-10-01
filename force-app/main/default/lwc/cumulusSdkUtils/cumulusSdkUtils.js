/**
 * Shared helpers for the Cumulus Tableau Next dashboard extensions.
 * Wraps the Dashboard Extension SDK conventions from the Salesforce guide
 * ("Enhance Your Dashboard Functionality with Custom LWC Extensions").
 */

// Event / lifecycle constants. The SDK exposes these on the injected `sdk` object in current
// releases; the string fallbacks match the documented values.
export const SDK_EVENTS = { FILTER_CHANGE: 'filterChange', PARAMETER_CHANGE: 'parameterChange' };

export function lifecycle(sdk, name) {
    const table = (sdk && sdk.LIFE_CYCLE_EVENTS) || {};
    const fallback = { INIT: 'init', LOADED: 'loaded', ERROR: 'error', NODATA: 'noData' };
    return table[name] || fallback[name];
}

export function notify(sdk, name, details) {
    try {
        if (sdk && sdk.actions && typeof sdk.actions.notifyLifecycleChange === 'function') {
            sdk.actions.notifyLifecycleChange(lifecycle(sdk, name), details);
        }
    } catch (e) {
        // never let telemetry break the widget
    }
}

/** "Model.Field" -> table_field expression; bare name -> semantic_field (calculated measure). */
export function fieldExpression(name) {
    const p = (name || '').split('.');
    return p.length === 2 ? { table_field: { name: p[1], table_name: p[0] } } : { semantic_field: { name } };
}

export function aggregationMethod(measureField) {
    const agg = (measureField && measureField.aggregation) || 'Sum';
    return `SEMANTIC_AGGREGATION_METHOD_${String(agg).toUpperCase()}`;
}

/** Build a grouped query: one optional grouping dimension + one aggregated measure. */
export function buildQuery({ dimensionField, measureField, limit = 101, sortDesc = true, sortByDim = false }) {
    const fields = [];
    if (dimensionField && dimensionField.name) {
        fields.push({ expression: fieldExpression(dimensionField.name), alias: 'dim', rowGrouping: true });
    }
    const m = { expression: fieldExpression(measureField.name), alias: 'val', rowGrouping: false };
    // table fields are aggregated with the author's chosen method; calculated measures carry their own aggregation
    if (String(measureField.name || '').includes('.')) m.semanticAggregationMethod = aggregationMethod(measureField);
    fields.push(m);
    const query = { fields, options: { limitOptions: { limit } } };
    // Semantic Query API sort shape (field-verified): {simpleSortOrder: {sortByFieldAlias, sortingOrder: ASC|DESC}}
    if (dimensionField && dimensionField.name && sortByDim) {
        query.options.sortOrders = [{ simpleSortOrder: { sortByFieldAlias: 'dim', sortingOrder: 'ASC' } }];
    } else if (dimensionField && dimensionField.name && sortDesc) {
        query.options.sortOrders = [{ simpleSortOrder: { sortByFieldAlias: 'val', sortingOrder: 'DESC' } }];
    }
    return query;
}

/** Normalise the various response shapes into [{dim, val}] */
export function normalizeRows(result) {
    if (!result) return [];
    let rows = result;
    if (result.queryResults && result.queryResults.queryData) rows = result.queryResults.queryData.rows;
    else if (result.queryData) rows = result.queryData.rows;
    else if (result.rows) rows = result.rows;
    else if (result.data) rows = result.data;
    if (!Array.isArray(rows)) return [];
    return rows.map((r) => {
        if (Array.isArray(r)) return { dim: r.length > 1 ? r[0] : null, val: r[r.length - 1] };
        if (r && Array.isArray(r.values)) return { dim: r.values.length > 1 ? r.values[0] : null, val: r.values[r.values.length - 1] };
        if (r && typeof r === 'object') return { dim: r.dim ?? null, val: r.val ?? Object.values(r).pop() };
        return { dim: null, val: r };
    });
}

export function formatValue(v, format) {
    if (v === null || v === undefined || v === '' || Number.isNaN(Number(v))) return '–';
    const n = Number(v);
    const abs = Math.abs(n);
    if (format === 'percent') return `${(n * 100).toFixed(1)}%`;
    const short = (x) => (x >= 1e9 ? `${(x / 1e9).toFixed(1)}B` : x >= 1e6 ? `${(x / 1e6).toFixed(1)}M` : x >= 1e3 ? `${(x / 1e3).toFixed(1)}K` : x.toFixed(x % 1 ? 1 : 0));
    const body = short(abs);
    const sign = n < 0 ? '-' : '';
    return format === 'currency' ? `${sign}$${body}` : `${sign}${body}`;
}
