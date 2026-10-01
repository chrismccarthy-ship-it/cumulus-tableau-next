#!/usr/bin/env python3
"""
Publish (or re-publish) a template's visualizations + dashboard straight into a live org through the Tableau Next REST API,
resolving the App Template tokens against an installed app. Lets you iterate on dashboard design in minutes instead of
re-running a 30-minute install.

  python3 scripts/publish_dashboard.py --org demo --template Cumulus_Retail_Banking --app 1zAKh000000wkBzMAI [--suffix _v2] [--replace]

--suffix  creates new assets named <name><suffix> (safe A/B next to the installed ones)
--replace updates the installed assets in place (PATCH by name)
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_template import sf_rest  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "force-app", "main", "default", "appTemplates")


def app_tokens(org, app_id, template):
    """Map ${App.<Type>.<node>.<Name|Id>} → real values from the app's asset list."""
    tok = {"${App.Name}": template, "${Variables.LabelSuffix}": ""}
    for a in sf_rest(org, f"/app-framework/apps/{app_id}/assets?").get("assets", []):
        t, src = a["type"], a["templateAssetSourceName"]
        if t == "SemanticModel":
            tok[f"${{App.SemanticModels.{src}.Name}}"] = a["assetIdOrName2"] or a["assetIdOrName"]
            tok[f"${{App.SemanticModels.{src}.Id}}"] = a["assetIdOrName"]
        elif t == "Workspace":
            tok[f"${{App.Workspaces.{src}.Name}}"] = a["assetIdOrName2"] or a["assetIdOrName"]
            tok[f"${{App.Workspaces.{src}.Id}}"] = a["assetIdOrName"]
    return tok


def resolve(obj, tok):
    s = json.dumps(obj)
    for k, v in tok.items():
        s = s.replace(k, v)
    return json.loads(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True); ap.add_argument("--template", required=True); ap.add_argument("--app", required=True)
    ap.add_argument("--suffix", default=""); ap.add_argument("--replace", action="store_true")
    a = ap.parse_args()
    tdir = os.path.join(TPL, a.template)
    tok = app_tokens(a.org, a.app, a.template)
    if not any(k.startswith("${App.SemanticModels") for k in tok):
        sys.exit("no semantic model on that app yet")
    # existing assets by name (for --replace)
    def listing(path, key):
        """The list endpoints cap at 100 rows and paginate with ?offset= (no nextPageUrl)."""
        items, off = [], 0
        while True:
            page = sf_rest(a.org, f"{path}?pageSize=100&offset={off}").get(key, [])
            items += page
            if len(page) < 100:
                return items
            off += 100
    vizzes = {v["name"]: v["id"] for v in listing("/tableau/visualizations", "visualizations")}
    dashes = {d["name"]: d["id"] for d in listing("/tableau/dashboards", "dashboards")}
    created = {}
    for f in sorted(glob.glob(os.path.join(tdir, "visualizations", "*.json"))):
        v = resolve(json.load(open(f)), tok)
        base = v["name"]; v["name"] = base + a.suffix; v["label"] = v["label"] + (" " + a.suffix.strip("_") if a.suffix else "")
        v["workspace"] = {"name": tok[f"${{App.Workspaces.{a.template}_WS.Name}}"]}
        if a.replace and v["name"] in vizzes:
            r = sf_rest(a.org, f"/tableau/visualizations/{vizzes[v['name']]}", "PATCH", v)
        elif v["name"] in vizzes:
            r = sf_rest(a.org, f"/tableau/visualizations/{vizzes[v['name']]}", "PATCH", v)
        else:
            r = sf_rest(a.org, "/tableau/visualizations", "POST", v)
        if not isinstance(r, dict) or not r.get("id"):
            sys.exit(f"viz {v['name']} failed: {json.dumps(r)[:1200]}")
        created[base] = r
        print(f"  viz {v['name']:36s} {r['id']}")
        tok[f"${{App.Visualizations.{base}.Id}}"] = r["id"]; tok[f"${{App.Visualizations.{base}.Name}}"] = r["name"]
    for f in sorted(glob.glob(os.path.join(tdir, "dashboards", "*.json"))):
        d = resolve(json.load(open(f)), tok)
        d["name"] = d["name"] + a.suffix; d["label"] = d["label"].strip() + (" " + a.suffix.strip("_") if a.suffix else "")
        d["workspaceIdOrApiName"] = tok[f"${{App.Workspaces.{a.template}_WS.Name}}"]
        if d["name"] in dashes:
            r = sf_rest(a.org, f"/tableau/dashboards/{dashes[d['name']]}", "PATCH", d)
        else:
            r = sf_rest(a.org, "/tableau/dashboards", "POST", d)
        if not isinstance(r, dict) or not r.get("id"):
            sys.exit(f"dashboard {d['name']} failed: {json.dumps(r)[:1500]}")
        print(f"  dashboard {d['name']} {r['id']}  → /tableau/dashboard/{r['name']}/view")


if __name__ == "__main__":
    main()
