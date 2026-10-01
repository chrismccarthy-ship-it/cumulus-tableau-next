# Packaging the Cumulus app (2GP unlocked package)

What ships in the package: the seven **App Templates** (`AppFrameworkTemplateBundle`) and the four **dashboard-extension LWCs**. The templates carry the CSVs, data streams, semantic models, vizzes and dashboards, so installing the package plus creating the apps gives a subscriber org the whole demo — the data kit path in `manifests/` is the alternative when the target org already owns the data.

```
# 0. Dev Hub is the same org we build in (sdo has Dev Hub enabled) — or authorize a different one
sf org login web -a devhub
sf config set target-dev-hub=devhub

# 1. Create the package once (unlocked; managed needs a namespace)
sf package create --name CumulusTableauNext --package-type Unlocked --path force-app -v devhub
#    → writes packageAliases.CumulusTableauNext = 0Ho… into sfdx-project.json

# 2. Create a version (bump versionNumber in sfdx-project.json between releases)
sf package version create --package CumulusTableauNext --installation-key-bypass --wait 30 -v devhub --code-coverage
#    → 04t… id (also written to packageAliases)

# 3. Promote before installing in production
sf package version promote --package CumulusTableauNext@0.1.0-1 -v devhub

# 4. Install in a subscriber org, then create the apps from the packaged templates
sf package install --package 04t… -o subscriber --wait 30 --publish-wait 30
for t in Cumulus_Retail_Banking Cumulus_Wealth Cumulus_Asset_Management Cumulus_Insurance Cumulus_Commercial Cumulus_Advisors Cumulus_Lending; do
  python3 scripts/install_template.py --org subscriber --template $t --skip-deploy
done
```

## What the subscriber sees
Tableau Next → **App Templates** lists the seven Cumulus templates ("empty" thumbnail is normal for metadata-deployed templates). **Create App** (or the script above) runs the chain: upload CSVs → data streams → workspace → semantic model → vizzes → dashboard. Roughly 20–35 minutes per app, streams run serially.

## Rules that bit us
- Package versions validate every template file; a template that installs fine can still fail packaging on `template-info.json` (all `variables` must be referenced somewhere) — `atf/preflight.py` checks this.
- The LWCs must be in the same package (or an installed dependency) — dashboards reference them as `c:cumulusKpiTile`; a missing bundle renders as an empty widget, not an install error.
- `versionNumber` `0.1.0.NEXT` auto-increments the build number; promote only what you demoed.
- Unlocked packages can be upgraded in place (`sf package install` with the newer 04t); templates already used to create apps are not re-run — re-create the app to pick up template changes.
- To share the templates *without* a package (quick internal demos): `sf project deploy start --manifest manifests/manifest_templates.xml -o <org>`.
