#!/usr/bin/env python3
"""
Deploy one Cumulus ATF template to an org and create the app from it (zero manual steps).

  python3 scripts/install_template.py --org demo --template Cumulus_Retail_Banking [--label "Retail Banking"] [--suffix " (demo)"] [--no-dashboard] [--deploy-only]

Steps
  1. sf project deploy start --source-dir force-app/main/default/appTemplates/<Template>
  2. GET  /app-framework/templates?          → find the template id (1zD…)
  3. POST /app-framework/apps?               → {"templateSourceId", "label", "name", "templateValues"}
     (equivalent: sf orchestrator app create --template-name <Template> -o <org>)
  4. Poll the app's data streams until every DataStreamRun is SUCCESS (≈6 min per stream, serial)
Notes (field-verified gotchas): every app-framework path needs a trailing "?"; the create response
nests under "app"; there is no requestStatus on the app record — poll data streams instead;
a metadata-deployed template shows as "empty" on the Templates page but Create works.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "67.0"


def sf_rest(org, path, method="GET", body=None):
    cmd = ["sf", "api", "request", "rest", f"/services/data/v{API}{path}", "-o", org, "--method", method]
    tmp = None
    if body is None and method == "DELETE":
        body = {}  # sf api request rest insists on a body for DELETE ("No 'mode' found in 'body' entry")
    if body is not None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(body, tmp); tmp.close()
        cmd += ["--body", "@" + tmp.name]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if tmp:
        os.unlink(tmp.name)
    txt = out.stdout.strip()
    if method == "DELETE" and not txt and out.returncode == 0:
        return {}
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        sys.exit(f"{method} {path} failed:\n{txt}\n{out.stderr}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--label")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--no-dashboard", action="store_true")
    ap.add_argument("--deploy-only", action="store_true")
    ap.add_argument("--skip-deploy", action="store_true")
    ap.add_argument("--wait-minutes", type=int, default=60)
    a = ap.parse_args()
    tdir = os.path.join(ROOT, "force-app", "main", "default", "appTemplates", a.template)
    if not os.path.isdir(tdir):
        sys.exit(f"no template at {tdir} — run python3 atf/build_templates.py")

    if not a.skip_deploy:
        print(f"== deploying {a.template}")
        r = subprocess.run(["sf", "project", "deploy", "start", "--source-dir", tdir, "-o", a.org, "--wait", "30", "--json"], capture_output=True, text=True)
        j = json.loads(r.stdout or "{}")
        if j.get("status") != 0:
            sys.exit(f"deploy failed: {json.dumps(j.get('result', j), indent=1)[:3000]}")
        print("   deployed")
    if a.deploy_only:
        return

    print("== locating template")
    tpls = sf_rest(a.org, "/app-framework/templates?")
    items = tpls.get("templates") or tpls.get("items") or tpls
    tid = None
    for t in items if isinstance(items, list) else []:
        if t.get("name") == a.template:
            tid = t.get("id")
    if not tid:
        sys.exit(f"template {a.template} not found in org. Response keys: {list(tpls)[:10]}")
    print(f"   {a.template} = {tid}")

    stamp = time.strftime("%m%d%H%M")
    app_name = f"{a.template}_{stamp}"
    body = {"templateSourceId": tid, "label": a.label or f"{a.template.replace('_', ' ')}", "name": app_name,
            "templateValues": {"LabelSuffix": a.suffix, "CreateDashboard": not a.no_dashboard}}
    print(f"== creating app {app_name}")
    created = sf_rest(a.org, "/app-framework/apps?", "POST", body)
    app = created.get("app", created)
    app_id = app.get("id")
    print(f"   app id {app_id} (status {app.get('applicationStatus')})")

    print("== waiting for data streams (serial, ~6 min each)")
    chain = json.load(open(os.path.join(tdir, "create-chain.json")))
    expected = [n["parameters"]["dataLakeObject"]["name"] for n in chain["definition"]["nodes"].values() if n["graphNodeType"]["name"] == "DataStreamUpsert"]  # stream physical name = DLO node name
    print("   expecting streams:", ", ".join(expected))
    deadline = time.time() + a.wait_minutes * 60
    seen_done = set()
    while time.time() < deadline:
        # the list endpoint is paginated; read each expected stream directly (GET by name, 404 until its node runs)
        status = {}
        for e in expected:
            r = subprocess.run(["sf", "api", "request", "rest", f"/services/data/v{API}/ssot/data-streams/{e}?", "-o", a.org], capture_output=True, text=True)
            try:
                j = json.loads(r.stdout.strip())
                if isinstance(j, dict) and j.get("name"):
                    status[e] = j.get("lastRunStatus")
            except json.JSONDecodeError:
                pass
        done = {k for k, v in status.items() if v == "SUCCESS"}
        failed = {k for k, v in status.items() if v in ("FAILED", "ERROR")}
        if done - seen_done:
            print("   SUCCESS:", ", ".join(sorted(done - seen_done)))
            seen_done |= done
        if failed:
            sys.exit(f"stream(s) failed: {sorted(failed)} — check Data Cloud → Data Streams → Refresh History")
        app_state = sf_rest(a.org, f"/app-framework/apps/{app_id}?").get("app", {}).get("applicationStatus")
        if app_state and app_state.lower().startswith("success"):
            print(f"== app {app_name} complete ({app_state})")
            return
        time.sleep(45)
    print("timed out waiting; check Setup → App Hub → Monitor")


if __name__ == "__main__":
    main()
