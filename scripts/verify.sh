#!/usr/bin/env bash
# Quick post-install verification via the Tableau Next REST API.
set -euo pipefail
ORG="${1:?usage: scripts/verify.sh <org-alias>}"
cd "$(dirname "$0")/.."
echo "Workspaces containing 'Cumulus':"
sf api request rest "/services/data/v67.0/tableau/workspaces" -o "$ORG" 2>/dev/null \
  | python3 -c "import sys,json; ws=[w['name'] for w in json.load(sys.stdin).get('workspaces',[]) if 'Cumulus' in w['name']]; print('  ', ws or 'none yet')"
echo "Semantic models containing 'Cumulus':"
sf api request rest "/services/data/v67.0/ssot/semantic/models?limit=100" -o "$ORG" 2>/dev/null \
  | python3 -c "import sys,json; ms=[m['apiName'] for m in json.load(sys.stdin).get('items',[]) if 'Cumulus' in m['apiName']]; print('  ', ms or 'none yet')"
