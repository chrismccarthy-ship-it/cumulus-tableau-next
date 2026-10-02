#!/usr/bin/env python3
"""Preflight checks for the Cumulus ATF templates (rules from the field-verified playbook).
Usage: python3 atf/preflight.py [template_dir ...]   (default: all under force-app/main/default/appTemplates)
Exit 1 on any FAIL."""
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "force-app", "main", "default", "appTemplates")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def check_template(d):
    fails, warns = [], []
    name = os.path.basename(d)

    def need(p):
        if not os.path.exists(os.path.join(d, p)):
            fails.append(f"missing {p}")
    for p in ("template-info.json", "template-policy.json", "variables.json", "layout.json", "create-chain.json", "sdms/sdm.json", "workspaces/workspace.json"):
        need(p)
    if fails:
        return name, fails, warns
    info = json.load(open(os.path.join(d, "template-info.json")))
    chain = json.load(open(os.path.join(d, "create-chain.json")))
    sdm = json.load(open(os.path.join(d, "sdms", "sdm.json")))
    # V5 chain name null; R9 policy
    if any(c.get("name") is not None for c in info["chainDefinitions"]):
        fails.append("template-info.chainDefinitions[].name must be null (V5)")
    if info.get("name") != name:
        fails.append(f"template-info.name {info.get('name')} != folder {name}")
    # R1 / R1a: no physical names or org-resident refs
    blob = ""
    for p in glob.glob(os.path.join(d, "**", "*.json"), recursive=True):
        blob += open(p).read()
    if "__dll" in blob or "__dlm" in blob:
        fails.append("physical __dll/__dlm name found in shipped JSON (R1)")
    for k in ("workspaceId", "cacheKey"):
        if f'"{k}"' in blob:
            fails.append(f"org-resident key {k} present (R1a)")
    if '"stylesheet"' in blob:
        fails.append("a visualization carries `stylesheet` — not packageable (R11)")
    # chain integrity
    nodes = chain["definition"]["nodes"]
    for nid, n in nodes.items():
        if n["referenceId"] != nid:
            fails.append(f"node {nid} referenceId mismatch")
        for s in n["sources"]:
            if s not in nodes:
                fails.append(f"node {nid} sources unknown node {s}")
        f = n["parameters"].get("file")
        if f and not os.path.exists(os.path.join(d, f)):
            fails.append(f"node {nid} file missing: {f}")
        if ".." in (f or ""):
            fails.append(f"node {nid} file has '..'")
        t = n["graphNodeType"]["name"]
        if t == "DataStreamRun" and (len(n["sources"]) != 1 or nodes[n["sources"][0]]["graphNodeType"]["name"] not in ("DataStreamUpsert", "DataStreamRun")):
            fails.append(f"{nid}: DataStreamRun must source exactly its own DataStreamUpsert (R5) or, for the settle step, the previous run")
    # SDM must depend transitively on every run (R6)
    def ancestors(nid, seen=None):
        seen = seen or set()
        for s in nodes[nid]["sources"]:
            if s not in seen:
                seen.add(s); ancestors(s, seen)
        return seen
    sdm_nodes = [k for k, v in nodes.items() if v["graphNodeType"]["name"] == "SemanticModelUpsert"]
    runs = {k for k, v in nodes.items() if v["graphNodeType"]["name"] == "DataStreamRun"}
    for s in sdm_nodes:
        if not runs <= ancestors(s):
            fails.append("SemanticModelUpsert does not depend on every DataStreamRun (R6)")
    # datastreams vs CSVs
    dlo_tokens = set()
    for k, v in nodes.items():
        if v["graphNodeType"]["name"] == "DataStreamUpsert":
            dlo_tokens.add(v["parameters"]["dataLakeObject"]["name"])
            ds = json.load(open(os.path.join(d, v["parameters"]["file"])))
            csv_node = nodes[v["sources"][0]]
            csv_path = os.path.join(d, csv_node["parameters"]["file"])
            with open(csv_path, newline="", encoding="utf-8") as f:
                rd = csv.reader(f)
                header = next(rd)
                rows = list(rd)
            sf = {x["name"]: x["dataType"] for x in ds["sourceFields"]}
            if [x["name"] for x in ds["sourceFields"]] != header:
                fails.append(f"{k}: sourceFields != CSV header order")
            for x in ds["sourceFields"]:
                if "datatype" in x:
                    fails.append(f"{k}: lowercase datatype (R3)")
                if x["dataType"] not in ("Text", "Number", "Date", "Boolean"):
                    fails.append(f"{k}: unsupported dataType {x['dataType']} on {x['name']}")
            if not any(x["isPrimaryKey"] for x in ds["dataLakeObjectInfo"]["fields"]):
                fails.append(f"{k}: DLO has no primary key")
            if not ds["dataLakeObjectInfo"]["name"].startswith("${App.DataLakeObjects."):
                fails.append(f"{k}: DLO name not tokenized (R1)")
            # sample-check values
            for i, col in enumerate(header):
                vals = [r[i] for r in rows[:2000]]
                typ = sf[col]
                if typ == "Date" and any(v and not ISO.match(v) for v in vals):
                    fails.append(f"{k}: non-ISO date in {col} (R2)")
                if typ == "Boolean" and any(v not in ("true", "false", "") for v in vals):
                    fails.append(f"{k}: non-boolean value in {col} (R4a)")
                if typ == "Number":
                    for v in vals:
                        if v:
                            try:
                                float(v)
                            except ValueError:
                                fails.append(f"{k}: non-numeric value '{v}' in {col}"); break
            pk = [x["name"] for x in ds["dataLakeObjectInfo"]["fields"] if x["isPrimaryKey"]][0]
            pi = header.index(pk)
            if len({r[pi] for r in rows}) != len(rows):
                fails.append(f"{k}: primary key {pk} not unique")
            if os.path.getsize(csv_path) > 25e6:
                warns.append(f"{k}: CSV > 25 MB")
    # SDM bindings reference existing DLO tokens and fields
    for o in sdm["semanticDataObjects"]:
        m = re.match(r"\$\{App\.DataLakeObjects\.(\w+)\.Name\}", o["dataObjectName"])
        if not m or m.group(1) not in dlo_tokens:
            fails.append(f"SDM object {o['apiName']} binds to unknown DLO token {o['dataObjectName']}")
    names = {o["apiName"] for o in sdm["semanticDataObjects"]}
    fields = {o["apiName"]: {x["apiName"] for x in o["semanticDimensions"] + o["semanticMeasurements"]} for o in sdm["semanticDataObjects"]}
    for r in sdm["semanticRelationships"]:
        for side, fld in (("leftSemanticDefinitionApiName", "leftSemanticFieldApiName"), ("rightSemanticDefinitionApiName", "rightSemanticFieldApiName")):
            if r[side] not in names or r["criteria"][0][fld] not in fields[r[side]]:
                fails.append(f"relationship {r['apiName']} references unknown object/field")
    calc_names = {c["apiName"] for c in sdm["semanticCalculatedMeasurements"]}
    calc_names = set(calc_names) | {c["apiName"] for c in sdm.get("semanticCalculatedDimensions", [])}
    for mtc in sdm["semanticMetrics"]:
        mref = mtc.get("measurementReference", {})
        if "calculatedFieldApiName" in mref:
            if mref["calculatedFieldApiName"] not in calc_names:
                fails.append(f"metric {mtc['apiName']} references unknown calc {mref['calculatedFieldApiName']}")
            if mtc.get("aggregationType") != "UserAgg":
                fails.append(f"metric {mtc['apiName']} on a calculated measure must use aggregationType UserAgg")
            refs = []
        elif "tableFieldReference" in mref:
            refs = [mref["tableFieldReference"]]
        else:
            fails.append(f"metric {mtc['apiName']} has no measurementReference"); refs = []
        for ref in refs + [mtc["timeDimensionReference"]["tableFieldReference"]] + [x["tableFieldReference"] for x in mtc["additionalDimensions"]]:
            if ref["tableApiName"] not in names or ref["fieldApiName"] not in fields[ref["tableApiName"]]:
                fails.append(f"metric {mtc['apiName']} references unknown field {ref}")
    for c in sdm["semanticCalculatedMeasurements"]:
        for obj in re.findall(r"\[(\w+)\]", c["expression"]):
            if obj not in names and not any(obj in f for f in fields.values()):
                fails.append(f"calc {c['apiName']} references unknown object/field {obj}")
        if "%" in c["expression"]:
            fails.append(f"calc {c['apiName']} contains % (parser gotcha)")
    # visualizations bind to the SDM token and reference real fields; dashboards reference shipped vizzes
    vdir = os.path.join(d, "visualizations")
    viz_names = set()
    for vf in sorted(glob.glob(os.path.join(vdir, "*.json"))):
        v = json.load(open(vf)); viz_names.add(v["name"])
        if v["dataSource"]["name"] != f"${{App.SemanticModels.{name}_SDM.Name}}":
            fails.append(f"viz {v['name']} dataSource not bound to the template SDM token")
        for fk, f in v["fields"].items():
            if "objectName" in f:
                if f["objectName"] not in names or f["fieldName"] not in fields[f["objectName"]]:
                    fails.append(f"viz {v['name']} field {fk} -> {f['objectName']}.{f['fieldName']} not in SDM")
            elif f["fieldName"] not in calc_names:
                fails.append(f"viz {v['name']} field {fk} -> calc {f['fieldName']} not in SDM")
        if "stylesheet" in v["visualSpecification"]:
            fails.append(f"viz {v['name']} carries stylesheet (R11)")
    for df in sorted(glob.glob(os.path.join(d, "dashboards", "*.json"))):
        dash = json.load(open(df))
        lwc_dir = os.path.join(ROOT, "force-app", "main", "default", "lwc")
        for w in dash["widgets"].values():
            if w.get("type") == "extension":
                fq = w["parameters"].get("fullyQualifiedName", "")
                comp = fq.split(":")[-1]
                if fq != w["source"]["name"] or not os.path.isdir(os.path.join(lwc_dir, comp)):
                    fails.append(f"dashboard {dash['name']} extension widget {w['name']} -> {fq} (component missing or names differ)")
                sdm = w["parameters"].get("properties", {}).get("sdmName", {})
                if sdm.get("apiName") != f"${{App.SemanticModels.{name}_SDM.Name}}":
                    fails.append(f"dashboard {dash['name']} extension widget {w['name']} not bound to the SDM token")
                continue
            if w.get("type") == "text":
                continue
            if w.get("type") == "filter":
                if w["source"]["name"] != f"${{App.SemanticModels.{name}_SDM.Name}}":
                    fails.append(f"dashboard {dash['name']} filter {w['name']} not bound to the SDM token")
                continue
            m = re.match(r"\$\{App\.Visualizations\.(\w+)\.Name\}", w["source"]["name"])
            if not m or m.group(1) not in viz_names:
                fails.append(f"dashboard {dash['name']} widget {w['name']} references unknown viz {w['source']['name']}")
        if dash.get("workspaceIdOrApiName") != f"${{App.Workspaces.{name}_WS.Name}}":
            fails.append(f"dashboard {dash['name']} not bound to workspace token")
    return name, fails, warns


def main():
    dirs = sys.argv[1:] or sorted(glob.glob(os.path.join(TPL, "Cumulus_*")))
    bad = 0
    for d in dirs:
        name, fails, warns = check_template(d)
        status = "PASS" if not fails else "FAIL"
        bad += bool(fails)
        print(f"{status}  {name}")
        for f in fails:
            print(f"      ✗ {f}")
        for w in warns:
            print(f"      ! {w}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
