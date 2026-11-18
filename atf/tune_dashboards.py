#!/usr/bin/env python3
"""
Apply the Nov 2026 dashboard tuning to every Cumulus Overview template (safe to re-run):

  1. less white space: shorter header, filters, banner, KPI tiles and headline blocks, 2 fewer rows on
     tall charts, 4 fewer on tall extensions, then every widget is pulled up under the widgets above it
     (column-aware); cell spacing 14 -> 8.

Run after atf/build_vizzes.py and atf/add_summary_widgets.py (the builder rewrites the dashboard files).
The same rules were applied to the live org dashboards on 2026-11-18.

Usage: python3 atf/tune_dashboards.py
"""
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), "force-app", "main", "default", "appTemplates")
RFS = {"filterMode": "all", "publishers": [], "widgetIds": []}


def new_height(name, rs, w):
    t = w.get("type")
    if name == "hdr" or name.startswith("flt_"):
        return min(rs, 4)
    if name == "x_banner":
        return min(rs, 3)
    if name.startswith("k_"):
        return min(rs, 10)
    if name.startswith("t_") and t == "extension":
        stat = "measureField" in (w["parameters"].get("properties") or {})
        return min(rs, 5 if stat else 4)
    if name.startswith("w_") and t == "visualization" and rs >= 22:
        return max(18, rs - 2)
    if name.startswith("x_") and rs >= 30:
        return rs - 4
    return rs


def fit_summary_height(d):
    """Size the static "Key insights" widget to its text (bullets + 3 rows) and pull the widgets below it up. Returns True if changed."""
    page = d["layouts"][0]["pages"][0]
    items = page["widgets"]
    sp = next((p for p in items if p["name"] == "summary"), None)
    if not sp or "summary" not in d["widgets"]:
        return False
    bullets = sum(1 for op in d["widgets"]["summary"]["parameters"]["content"] if str(op.get("insert", "")).startswith("•"))
    want = bullets + 3
    if sp["rowspan"] == want:
        return False
    sp["rowspan"] = want
    for it in items:
        it["_old_row"], it["_old_end"] = it["row"], it["row"] + it["rowspan"]
    placed = []
    for it in sorted(items, key=lambda x: (x["_old_row"], x["column"])):
        top = 0
        for p in placed:
            if it["column"] < p["column"] + p["colspan"] and p["column"] < it["column"] + it["colspan"] and p["_old_end"] <= it["_old_row"]:
                top = max(top, p["row"] + p["rowspan"])
        it["row"] = top
        placed.append(it)
    for it in items:
        it.pop("_old_row"); it.pop("_old_end")
    return True


def tune(path):
    d = json.load(open(path, encoding="utf-8"))
    page = d["layouts"][0]["pages"][0]
    items = page["widgets"]
    notes = []
    fitted = fit_summary_height(d)
    if fitted:
        notes.append("insights widget fitted to its text")
    # compaction (skipped once cellSpacingX is 8, which this step sets: the height rules are not repeatable)
    if d["layouts"][0].get("style", {}).get("cellSpacingX") == 8:
        notes.append("already compact, layout left as is")
        json.dump(d, open(path, "w", encoding="utf-8"), indent=2)
        return notes
    before = max(p["row"] + p["rowspan"] for p in items)
    for it in items:
        it["_old_row"], it["_old_end"] = it["row"], it["row"] + it["rowspan"]
        it["_rs"] = new_height(it["name"], it["rowspan"], d["widgets"][it["name"]])
    placed = []
    for it in sorted(items, key=lambda x: (x["_old_row"], x["column"])):
        top = 0
        for p in placed:
            if it["column"] < p["column"] + p["colspan"] and p["column"] < it["column"] + it["colspan"] and p["_old_end"] <= it["_old_row"]:
                top = max(top, p["row"] + p["_rs"])
        it["row"] = top
        placed.append(it)
    for it in items:
        it["rowspan"] = it["_rs"]
        for k in ("_old_row", "_old_end", "_rs"):
            it.pop(k)
    st = d["layouts"][0].setdefault("style", {})
    st["cellSpacingX"] = 8
    st["cellSpacingY"] = 8
    notes.append(f"rows {before} -> {max(p['row'] + p['rowspan'] for p in items)}")
    json.dump(d, open(path, "w", encoding="utf-8"), indent=2)
    return notes


def main():
    for t in sorted(os.listdir(TPL)):
        path = os.path.join(TPL, t, "dashboards", t + "_Overview.json")
        if os.path.exists(path):
            print(f"{t}_Overview: " + "; ".join(tune(path)))


if __name__ == "__main__":
    main()
