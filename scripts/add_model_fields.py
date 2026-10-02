#!/usr/bin/env python3
"""
Add the calculated dimensions / measures the redesigned dashboards need to the LIVE semantic models
(idempotent: skips fields that already exist). The same definitions live in atf/build_templates.py
(`calc_dims` / `calcs`) so fresh installs get them too.

  python3 scripts/add_model_fields.py --org buildorg [--template Cumulus_Wealth]

Month grains:  LEFT(STR([Obj].[DateField]), 7)  -> "2026-08"   (DATETRUNC returns DateTime, which the authoring API rejects)
State codes:   MID([Obj].[BranchName], 9, 2)     -> "GA"       (branch names are "Cumulus GA Branch 1")
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "atf"))
from install_template import sf_rest  # noqa: E402
from build_templates import EXTRA_DIMS, EXTRA_CALCS, LOBS  # noqa: E402

LIVE_MODELS = {"Cumulus_Retail_Banking": "Cumulus_Retail_Banking_Model_988", "Cumulus_Wealth": "Cumulus_Wealth_Management_Model_988",
               "Cumulus_Asset_Management": "Cumulus_Asset_Management_Model_988", "Cumulus_Insurance": "Cumulus_Insurance_Model_9881",
               "Cumulus_Commercial": "Cumulus_Commercial_Banking_Model_988", "Cumulus_Advisors": "Cumulus_Financial_Advisors_Model_988",
               "Cumulus_Lending": "Cumulus_Lending_Model_988"}


def dim_body(api, label, expr):
    return {"apiName": api, "label": label, "expression": expr, "dataType": "Text", "displayCategory": "Discrete", "isQueryable": "Queryable",
            "isVisible": True, "semanticDataType": "None", "sortOrder": "None", "overriddenProperties": [], "filters": []}


def calc_body(api, label, expr, sentiment):
    return {"aggregationType": "UserAgg", "apiName": api, "dataType": "Number", "decimalPlace": 2, "directionality": "Up", "displayCategory": "Continuous",
            "expression": expr, "filters": [], "isOverrideBase": False, "isQueryable": "Queryable", "isVisible": True, "label": label, "level": "AggregateFunction",
            "overriddenProperties": [], "semanticDataType": "None", "sentiment": sentiment, "shouldTreatNullsAsZeros": False, "sortOrder": "None", "totalAggregationType": "Sum"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--template")
    ap.add_argument("--drop", nargs="*", default=[], help="calculated dimension api names to delete first (probe leftovers)")
    a = ap.parse_args()
    for t, model in LIVE_MODELS.items():
        if a.template and t != a.template:
            continue
        m = sf_rest(a.org, f"/ssot/semantic/models/{model}?")
        have_d = {d["apiName"] for d in m.get("semanticCalculatedDimensions", [])}
        have_m = {c["apiName"] for c in m.get("semanticCalculatedMeasurements", [])}
        for d in a.drop:
            if d in have_d:
                r = sf_rest(a.org, f"/ssot/semantic/models/{model}/calculated-dimensions/{d}?", "DELETE")
                print(f"{t}: dropped {d} {json.dumps(r)[:80]}")
        for api, label, expr in EXTRA_DIMS.get(t, []):
            if api in have_d:
                print(f"{t}: dim {api} exists"); continue
            r = sf_rest(a.org, f"/ssot/semantic/models/{model}/calculated-dimensions?", "POST", dim_body(api, label, expr))
            print(f"{t}: dim {api} -> {'ok' if r.get('id') else json.dumps(r)[:300]}")
        for api, label, expr, sent in EXTRA_CALCS.get(t, []):
            if api in have_m:
                print(f"{t}: calc {api} exists"); continue
            r = sf_rest(a.org, f"/ssot/semantic/models/{model}/calculated-measurements?", "POST", calc_body(api, label, expr, sent))
            print(f"{t}: calc {api} -> {'ok' if r.get('id') else json.dumps(r)[:300]}")


if __name__ == "__main__":
    main()
