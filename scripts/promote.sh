#!/usr/bin/env bash
# Promote Cumulus Tableau Next assets from one org to another (sandbox → production) with the CLI.
#   scripts/promote.sh <source-alias> <target-alias> [--skip-datakit] [--check-only]
# Order: data kit → LWC extensions → workspaces/vizzes/dashboards → verify.
set -euo pipefail
SRC=${1:?source org alias}; DST=${2:?target org alias}; shift 2
SKIP_DK=0; CHECK=""
for f in "$@"; do case $f in --skip-datakit) SKIP_DK=1;; --check-only) CHECK="--dry-run";; esac; done
cd "$(dirname "$0")/.."

echo "== API versions"; for o in "$SRC" "$DST"; do sf org display -o "$o" --json | python3 -c "import sys,json;r=json.load(sys.stdin)['result'];print(f\"   {r['alias']:<12} {r['apiVersion']}  {r['instanceUrl']}\")"; done

echo "== retrieve from $SRC"
[ $SKIP_DK = 1 ] || sf project retrieve start --manifest manifests/manifest_datakit.xml -o "$SRC" --wait 30
sf project retrieve start --manifest manifests/manifest_lwc.xml    -o "$SRC" --wait 30
sf project retrieve start --manifest manifests/manifest_assets.xml -o "$SRC" --wait 30

echo "== deploy to $DST ${CHECK:+(validation only)}"
[ $SKIP_DK = 1 ] || sf project deploy start --manifest manifests/manifest_datakit.xml -o "$DST" --wait 30 $CHECK
if [ $SKIP_DK = 0 ] && [ -z "$CHECK" ]; then
  echo "   data kit deployed — run its data streams in $DST (Data 360 → Data Streams → Refresh Now) or ingest with scripts/load_data.py, then re-run with --skip-datakit"
  exit 0
fi
sf project deploy start --manifest manifests/manifest_lwc.xml    -o "$DST" --wait 30 $CHECK
sf project deploy start --manifest manifests/manifest_assets.xml -o "$DST" --wait 30 $CHECK

[ -n "$CHECK" ] || scripts/verify.sh "$DST"
