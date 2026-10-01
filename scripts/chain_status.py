#!/usr/bin/env python3
"""Show the per-node status of an App Template Framework create chain (what Setup → App Hub → Monitor shows).
Usage: python3 scripts/chain_status.py --org <alias> --app <1zA… app id | app name>"""
import argparse
import json
import subprocess
import sys

API = "67.0"


def rest(org, path):
    r = subprocess.run(["sf", "api", "request", "rest", f"/services/data/v{API}{path}", "-o", org], capture_output=True, text=True)
    try:
        return json.loads(r.stdout.strip())
    except json.JSONDecodeError:
        sys.exit(f"GET {path} failed: {r.stdout[:300]} {r.stderr[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--full", action="store_true", help="print full status messages")
    a = ap.parse_args()
    app_id = a.app
    if not app_id.startswith("1zA"):
        apps = rest(a.org, "/app-framework/apps?").get("apps", [])
        match = [x for x in apps if x.get("name") == a.app or x.get("label") == a.app]
        if not match:
            sys.exit(f"app {a.app} not found")
        app_id = match[-1]["id"]
    app = rest(a.org, f"/app-framework/apps/{app_id}?")
    print(f"{app.get('name')}  status={app.get('applicationStatus')}  template={app.get('templateSourceId')}")
    act = rest(a.org, f"/app-framework/apps/{app_id}/activities/latest?")
    rr = act["runtimeRequest"]
    print(f"chain run {rr['id']}: {rr['requestStatus']} ({rr.get('durationInSeconds')} s)")
    rt = rest(a.org, rr["uri"].replace(f"/services/data/v{API}", ""))
    for name, node in rt["definition"]["nodes"].items():
        typ = node["graphNode"]["graphNodeType"]["name"]
        res = node.get("results", {})
        ex = res.get("execute") or res.get("validate") or {}
        st = ex.get("taskStatus", "NotStarted")
        msg = (ex.get("statusMessage") or "")
        flag = "✓" if st == "CompleteStatus" else ("✗" if "Fail" in st else "…")
        print(f" {flag} {name:32s} {typ:22s} {st:18s} {msg if a.full else msg[:160]}")
    print("summary:", rt.get("taskSummary"))


if __name__ == "__main__":
    main()
