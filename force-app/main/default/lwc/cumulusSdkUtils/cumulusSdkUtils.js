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

// ---------------------------------------------------------------------------------------------
// Dashboard filters (added Nov 2026)
//
// fetchDataUsingQueryAndSource() does not apply the dashboard's filters to a query on its own, so a
// widget that only re-runs its query on FILTER_CHANGE keeps showing unfiltered numbers. These helpers
// read the active filters (sdk.getContext().dashboardState.filters, or the last FILTER_CHANGE payload),
// translate them to the Semantic Query API's flattenFilter form and add them to the query.
//   filter: { flattenFilter: { filters: [{ fieldName: 'Table.Field', operator: 'In', values: [...] }], filterLogic: '1 AND 2' } }
// (format verified against the live API; an empty filter list is rejected, so none is added when there are no filters).
// If the API rejects the filtered query, the widget falls back to the unfiltered one rather than showing an error.
// ---------------------------------------------------------------------------------------------
const lastPayloads = new WeakMap();
const diagnostics = new WeakMap();

/** Set to false to hide the small grey filter-status line on the KPI tiles. */
export const SHOW_FILTER_DIAGNOSTICS = false;

function diag(sdk) {
    if (!sdk) return {};
    if (!diagnostics.has(sdk)) diagnostics.set(sdk, { events: 0, raw: '', applied: 0, outcome: 'not run yet' });
    return diagnostics.get(sdk);
}

/** One short line describing what the last query saw: events heard, filters received and applied, outcome. */
export function filterDiagnostics(sdk) {
    const d = diag(sdk);
    const ctx = sdk && typeof sdk.getContext === 'function' ? 'ctx' : 'no-ctx';
    return `filters: ${d.events} change events, ${ctx}, applied ${d.applied}, ${d.outcome}, queried ${d.at || 'never'}${d.raw ? ` | ${d.raw}` : ''}`;
}

/** Subscribe to FILTER_CHANGE and remember the payload; returns the unsubscribe function. */
export function onFilterChange(sdk, callback) {
    if (!sdk || typeof sdk.on !== 'function') return undefined;
    return sdk.on(SDK_EVENTS.FILTER_CHANGE, (payload) => {
        lastPayloads.set(sdk, payload);
        diag(sdk).events += 1;
        callback(payload);
    });
}

const OPERATORS = {
    in: 'In', values: 'In', invalues: 'In', equals: 'In', equal: 'In', eq: 'In', is: 'In', oneof: 'In', includes: 'In',
    notin: 'NotIn', notinvalues: 'NotIn', notequals: 'NotIn', notequal: 'NotIn', ne: 'NotIn', isnot: 'NotIn', excludes: 'NotIn', exclude: 'NotIn',
    greaterthan: 'GreaterThan', gt: 'GreaterThan', greaterthanorequalto: 'GreaterThanOrEqualTo', greaterthanorequal: 'GreaterThanOrEqualTo', gte: 'GreaterThanOrEqualTo',
    lessthan: 'LessThan', lt: 'LessThan', lessthanorequalto: 'LessThanOrEqualTo', lessthanorequal: 'LessThanOrEqualTo', lte: 'LessThanOrEqualTo'
};

function rawFilterList(payload, sdk) {
    const pick = (p) => (Array.isArray(p) ? p : p && Array.isArray(p.filters) ? p.filters : null);
    let list = pick(payload);
    if (!list) {
        try {
            const ctx = sdk && typeof sdk.getContext === 'function' ? sdk.getContext() : null;
            list = pick(ctx && ctx.dashboardState && ctx.dashboardState.filters);
        } catch (e) {
            list = null;
        }
    }
    if (!list) list = pick(sdk && lastPayloads.get(sdk));
    return list || [];
}

function plainValue(v) {
    if (v && typeof v === 'object') {
        if ('value' in v) return v.value;
        if ('val' in v) return v.val;
        if ('label' in v) return v.label;
    }
    return v;
}

/**
 * Turn whatever the SDK reports into [{ fieldName: 'Table.Field', operator, values }] for one model.
 * Filters for another data source, with no values, with an unsupported operator or without a resolvable
 * table are skipped.
 */
export function normalizeFilters(raw, sdmApiName, tableHints = []) {
    const out = [];
    (raw || []).forEach((f) => {
        if (!f || typeof f !== 'object') return;
        const src = f.dataSource || f.dataSourceName || f.dataSourceApiName || (f.source && (f.source.name || f.source));
        if (src && sdmApiName && typeof src === 'string' && src.toLowerCase() !== String(sdmApiName).toLowerCase()) return;
        // The dashboard reports e.g. {"fields":[{"model":"RB_Service_Cases.Channel"}],"operator":"In","values":["Voice"]}
        // (observed in sdo1010); the other spellings cover the documented UnifiedFilterJson and applyFilter shapes.
        const asName = (x) => {
            if (typeof x === 'string') return x;
            if (x && typeof x === 'object') {
                const k = ['fieldName', 'name', 'field', 'apiName', 'model'].find((key) => typeof x[key] === 'string');
                return k ? x[k] : undefined;
            }
            return undefined;
        };
        const first = (x) => (Array.isArray(x) ? asName(x[0]) : asName(x));
        let name = first(f.fieldName) || first(f.field) || first(f.name) || first(f.fieldOrFields) || first(f.fields);
        if (!name) return;
        let table = f.objectName || f.tableName || f.table || f.dataObject || f.dataObjectName;
        name = name.replace(/[[\]]/g, '');
        if (name.includes('.')) {
            const parts = name.split('.');
            name = parts.pop();
            table = table || parts.pop();
        }
        table = table || (tableHints.length ? tableHints[0] : undefined);
        if (!table) return;
        const op = OPERATORS[String(f.operator || f.operation || 'In').replace(/[^a-z]/gi, '').toLowerCase().replace(/^(filteroperator|filteroperation)/, '')];
        if (!op) return;
        const values = (Array.isArray(f.values) ? f.values : f.value !== undefined ? [f.value] : []).map(plainValue).filter((v) => v !== undefined && v !== null && v !== '');
        if (!values.length) return;
        out.push({ fieldName: `${table}.${name}`, operator: op, values });
    });
    return out;
}

/** Tables referenced by a query's table_field expressions (used to resolve filters that carry no table). */
export function queryTables(query) {
    const seen = [];
    ((query && query.fields) || []).forEach((f) => {
        const tf = f && f.expression && (f.expression.table_field || f.expression.tableField);
        const t = tf && (tf.table_name || tf.tableName);
        if (t && !seen.includes(t)) seen.push(t);
    });
    return seen;
}

/** Copy of the query with the filters ANDed in; the same query when there are none. */
export function withFilters(query, filters) {
    if (!filters || !filters.length) return query;
    return { ...query, filter: { flattenFilter: { filters, filterLogic: filters.map((_, i) => String(i + 1)).join(' AND ') } } };
}

/** Run a query with the dashboard's active filters applied; falls back to the unfiltered query if the filtered one fails. */
export async function fetchWithFilters(sdk, query, sdmApiName) {
    const raw = rawFilterList(undefined, sdk);
    const filters = normalizeFilters(raw, sdmApiName, queryTables(query));
    const d = diag(sdk);
    try {
        d.raw = JSON.stringify(raw).slice(0, 170);
    } catch (e) {
        d.raw = 'unreadable';
    }
    d.applied = filters.length;
    d.at = new Date().toLocaleTimeString();
    d.outcome = raw.length ? (filters.length ? 'sent with filters' : 'received but none usable') : 'none received';
    try {
        // diagnostics: open the browser console and look for "[cumulus] filters" to see what the dashboard sent
        if (raw.length || filters.length) {
            // eslint-disable-next-line no-console
            console.debug('[cumulus] filters', JSON.stringify({ model: sdmApiName, received: raw, applied: filters }));
        }
    } catch (e) {
        // diagnostics only
    }
    if (filters.length) {
        try {
            return await sdk.fetchDataUsingQueryAndSource(withFilters(query, filters), sdmApiName);
        } catch (e) {
            // fall through: a filter that does not relate to this widget's tables must not break the widget
            d.outcome = `filtered query failed (${String((e && e.message) || e).slice(0, 60)}), used unfiltered`;
        }
    }
    return sdk.fetchDataUsingQueryAndSource(query, sdmApiName);
}
