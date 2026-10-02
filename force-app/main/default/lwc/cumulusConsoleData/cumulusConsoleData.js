/**
 * Query + narrative helpers shared by the Cumulus console extensions.
 * `query()` is a thin wrapper over sdk.fetchDataUsingQueryAndSource that groups by several dimensions
 * and aggregates several measures in one call, returning plain objects keyed by alias.
 */
import { fieldExpression, aggregationMethod } from 'c/cumulusSdkUtils';

export async function query(sdk, modelApiName, { dims = [], measures = [], limit = 5000, sortBy = null, desc = true } = {}) {
    const fields = [];
    dims.forEach((d) => fields.push({ expression: fieldExpression(d.name), alias: d.alias, rowGrouping: true }));
    measures.forEach((m) => {
        const f = { expression: fieldExpression(m.name), alias: m.alias, rowGrouping: false };
        if (String(m.name).includes('.')) f.semanticAggregationMethod = aggregationMethod({ aggregation: m.agg || 'Sum' });
        fields.push(f);
    });
    const q = { fields, options: { limitOptions: { limit } } };
    if (sortBy) q.options.sortOrders = [{ simpleSortOrder: { sortByFieldAlias: sortBy, sortingOrder: desc ? 'DESC' : 'ASC' } }];
    // Gateway round-trips take ~4 s each; the demo data is static, so cache results per model+query for CACHE_TTL_MS
    // in sessionStorage (clearQueryCache() on an explicit refresh).
    const ck = 'cumulusq:' + modelApiName + ':' + hash(JSON.stringify(q));
    const cached = readCache(ck);
    const res = cached || await sdk.fetchDataUsingQueryAndSource(q, modelApiName);
    if (!cached) writeCache(ck, res);
    let rows = res;
    if (res && res.queryResults && res.queryResults.queryData) rows = res.queryResults.queryData.rows;
    else if (res && res.queryData) rows = res.queryData.rows;
    else if (res && res.rows) rows = res.rows;
    if (!Array.isArray(rows)) return [];
    const aliases = fields.map((f) => f.alias);
    return rows.map((r) => {
        const v = Array.isArray(r) ? r : r && Array.isArray(r.values) ? r.values : aliases.map((a) => r[a]);
        const o = {};
        aliases.forEach((a, i) => { o[a] = v[i]; });
        return o;
    });
}

export const CACHE_TTL_MS = 15 * 60 * 1000;
function hash(str) { let h = 5381; for (let i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) | 0; return (h >>> 0).toString(36); }
function readCache(k) { try { const raw = sessionStorage.getItem(k); if (!raw) return null; const { t, v } = JSON.parse(raw); return Date.now() - t < CACHE_TTL_MS ? v : null; } catch (e) { return null; } }
function writeCache(k, v) { try { const s = JSON.stringify({ t: Date.now(), v }); if (s.length < 2000000) sessionStorage.setItem(k, s); } catch (e) { /* quota or privacy mode — ignore */ } }
export function clearQueryCache() { try { Object.keys(sessionStorage).filter((k) => k.startsWith('cumulusq:')).forEach((k) => sessionStorage.removeItem(k)); } catch (e) { /* ignore */ } }
export const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
export const sum = (xs, f) => xs.reduce((a, x) => a + num(f ? f(x) : x), 0);
export const avg = (xs, f) => (xs.length ? sum(xs, f) / xs.length : 0);
export const pct = (v, d = 1) => `${(num(v) * 100).toFixed(d)}%`;
export function money(v) {
    const n = num(v), a = Math.abs(n), s = n < 0 ? '-' : '';
    if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(2)}B`;
    if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(2)}M`;
    if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(1)}K`;
    return `${s}$${a.toFixed(0)}`;
}
export function intfmt(v) { return Math.round(num(v)).toLocaleString(); }
export function signedPct(cur, prev) {
    if (!prev) return null;
    const d = (cur - prev) / Math.abs(prev);
    return { text: `${d >= 0 ? '+' : ''}${(d * 100).toFixed(1)}%`, good: d >= 0, abs: cur - prev };
}
/** last N months of a sorted month list */
export function lastMonths(months, n) { return months.slice(Math.max(0, months.length - n)); }
export function prevMonths(months, n) { const end = Math.max(0, months.length - n); return months.slice(Math.max(0, end - n), end); }
/** sparkline path for an SVG viewBox 200x40 */
export function sparkPath(vals) {
    const v = vals.map(num);
    if (v.length < 2) return { line: '', area: '', end: null };
    const mx = Math.max(...v), mn = Math.min(...v), span = mx - mn || 1;
    const pts = v.map((x, i) => [2 + (i * 196) / (v.length - 1), 36 - ((x - mn) / span) * 30]);
    const line = 'M' + pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('L');
    return { line, area: `${line}L${pts[pts.length - 1][0].toFixed(1)},40L${pts[0][0].toFixed(1)},40Z`, end: pts[pts.length - 1] };
}
export function rank(rows, key, desc = true) {
    return [...rows].sort((a, b) => (desc ? num(b[key]) - num(a[key]) : num(a[key]) - num(b[key])));
}
export function loadEdits(key) { try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch (e) { return {}; } }
export function saveEdits(key, obj) { try { localStorage.setItem(key, JSON.stringify(obj)); } catch (e) { /* ignore */ } }
