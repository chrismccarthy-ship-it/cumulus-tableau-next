#!/usr/bin/env bash
# Cumulus Tableau Next — install into a target org.
#
#   scripts/install.sh <org-alias>                       # all seven LOB templates (≈ 3 h of serial ingestion)
#   scripts/install.sh <org-alias> Cumulus_Retail_Banking # one LOB (≈ 25–35 min)
#
# Primary path = App Template Framework "CSV data templates": each template ships its CSVs and,
# on Create App, builds Data Stream → DLO → Semantic Model → Visualizations → Dashboard by itself.
# Nothing to configure in Data 360 first. Requires Data 360 + Tableau Next enabled and a user with
# Data Cloud Architect + Tableau Next Admin.
set -euo pipefail
ORG="${1:?usage: scripts/install.sh <org-alias> [Template_Name]}"
ONLY="${2:-}"
cd "$(dirname "$0")/.."

echo "== 1. Tooling & org"
sf --version
sf org display -o "$ORG" --json | python3 -c "import sys,json; r=json.load(sys.stdin)['result']; print('   org:', r['username'], r['instanceUrl'])"

echo "== 2. Templates"
[ -d force-app/main/default/appTemplates/Cumulus_Retail_Banking ] || { python3 data/generate.py >/dev/null && python3 atf/build_templates.py; }
python3 atf/preflight.py

echo "== 3. LWC dashboard extensions (phase P4; harmless if absent)"
sf project deploy start --manifest manifests/manifest_lwc.xml -o "$ORG" --wait 20 2>/dev/null || echo "   (no LWCs yet)"

echo "== 4. Deploy template(s) and create app(s)"
if [ -n "$ONLY" ]; then
  python3 scripts/install_template.py --org "$ORG" --template "$ONLY"
else
  for t in Cumulus_Retail_Banking Cumulus_Wealth Cumulus_Asset_Management Cumulus_Insurance Cumulus_Commercial Cumulus_Advisors Cumulus_Lending; do
    python3 scripts/install_template.py --org "$ORG" --template "$t"
  done
fi

echo "== 5. Verify"
scripts/verify.sh "$ORG" || true
echo "Done. Tableau Next → Workspaces → Cumulus … (add the LWC extension widgets to dashboards if this org's bindings didn't carry over)."
