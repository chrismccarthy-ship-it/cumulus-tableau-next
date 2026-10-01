#!/usr/bin/env python3
"""
Remove Cumulus / test assets from an org so a demo can be re-installed cleanly.

  python3 scripts/cleanup_org.py --org demo --prefix Cumulus_Ins_Test --prefix T_Ext_Test [--apps] [--dry-run]

Order matters (children before parents): dashboards → visualizations → semantic models → workspaces → apps.
Data streams / DLOs are left alone: the platform refuses to delete DLOs that were created by an app
(CANNOT_DELETE_ENTITY) and the templates tolerate the numeric suffixes it adds on re-install.
Templates are removed with `sf project delete source` (they are metadata), see --templates.
"""
import argparse
import subprocess
import sys

from install_template import sf_rest  # noqa: E402  (same folder)


def listing(org, path, key):
    """Follow nextPageUrl-style pagination on Tableau Next list endpoints."""
    items, url = [], path
    while url:
        j = sf_rest(org, url)
        items += j.get(key) or j.get("items") or []
        nxt = j.get("nextPageUrl") or j.get("nextPage")
        url = nxt.split("/services/data/v67.0")[-1] if nxt else None
    return items


def matches(name, prefixes):
    return any((name or "").startswith(p) for p in prefixes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--prefix", action="append", required=True, help="asset label/name prefix (repeatable)")
    ap.add_argument("--apps", action="store_true", help="also delete app-framework apps whose name matches")
    ap.add_argument("--templates", action="store_true", help="also delete deployed AppFrameworkTemplateBundles whose name matches")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    def kill(kind, path, ident, label):
        print(f"  {'would delete' if a.dry_run else 'delete'} {kind}: {label} ({ident})")
        if not a.dry_run:
            r = sf_rest(a.org, path, "DELETE")
            if isinstance(r, dict) and r.get("errorCode"):
                print(f"     !! {r.get('errorCode')}: {r.get('message')}")

    print("== dashboards")
    for d in listing(a.org, "/tableau/dashboards?pageSize=200", "dashboards"):
        if matches(d.get("name"), a.prefix) or matches(d.get("label"), a.prefix):
            kill("dashboard", f"/tableau/dashboards/{d['id']}", d["id"], d.get("name"))
    print("== visualizations")
    for v in listing(a.org, "/tableau/visualizations?pageSize=200", "visualizations"):
        if matches(v.get("name"), a.prefix) or matches(v.get("label"), a.prefix):
            kill("visualization", f"/tableau/visualizations/{v['id']}", v["id"], v.get("name"))
    print("== semantic models")
    for m in listing(a.org, "/ssot/semantic/models?", "semanticModels"):
        if matches(m.get("apiName"), a.prefix) or matches(m.get("label"), a.prefix):
            kill("semantic model", f"/ssot/semantic/models/{m['apiName']}?", m["apiName"], m.get("label"))
    print("== workspaces")
    for w in listing(a.org, "/tableau/workspaces?pageSize=200", "workspaces"):
        if matches(w.get("name"), a.prefix) or matches(w.get("label"), a.prefix):
            kill("workspace", f"/tableau/workspaces/{w['id']}", w["id"], w.get("name"))
    if a.apps:
        print("== apps")
        for app in (sf_rest(a.org, "/app-framework/apps?").get("apps") or []):
            if matches(app.get("name"), a.prefix) or matches(app.get("label"), a.prefix):
                kill("app", f"/app-framework/apps/{app['id']}?", app["id"], app.get("name"))
    if a.templates:
        print("== templates (metadata)")
        for t in (sf_rest(a.org, "/app-framework/templates?").get("templates") or []):
            if matches(t.get("name"), a.prefix):
                print(f"  {'would delete' if a.dry_run else 'delete'} template {t['name']}")
                if not a.dry_run:
                    subprocess.run(["sf", "project", "delete", "source", "-o", a.org, "--metadata", f"AppFrameworkTemplateBundle:{t['name']}", "--no-prompt"], check=False)
    print("done")


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    main()
