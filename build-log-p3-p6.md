# Build log — P3 (vizzes/dashboards), P4 (LWC extensions), P5 (deploy/package), P6 part 2 (embedding)

Org: `sdo` only (single-host egress allowlist). Repo: `SalesforceProjects\cumulus-tableau-next` (not yet on GitHub — daily reminder active).

## Where things stand (16 Sep, evening)

| Piece | State |
|---|---|
| Synthetic data (38 tables, 196,778 rows) + dictionary | done, validated |
| 7 App Templates (CSV → stream → workspace → SDM → vizzes → dashboard) | built, preflight PASS ×7; **all seven installed end-to-end in sdo** (Insurance 55/55, Asset Mgmt 56/56, Lending 52/52, Commercial 60/60, Advisors 56/56, Retail 59/59, Wealth 60/60 nodes; six ran in parallel in ~45 min) |
| 65 vizzes + 7 dashboards (4 KPI tiles, 5–6 charts, 1 extension widget each) | all created by the chains: `Cumulus_<LOB>_Overview` ×7; models `Cumulus_<LOB>_Model_988` (Insurance `_9881`) |
| 4 dashboard-extension LWCs (`cumulusKpiTile`, `cumulusRankedBars`, `cumulusNextBestActions`, `cumulusThresholdBanner`) | deployed to sdo; chain-created dashboard with an extension widget proven (`Cumulus_Ins_Test_Overview1`); **runtime rendering not yet eyeballed** |
| Sandbox→prod: `manifests/*` (generated), `scripts/promote.sh`, `ci/promote.workflow.yml` | done (validate-on-PR, deploy-on-main) |
| Packaging: `packaging/README.md` (2GP unlocked, install + create apps) | runbook done; package not yet created against the Dev Hub |
| Embedding: `embed/` (Express + SDK v2, ECA web-server flow + PKCE + frontdoor) | code done; needs an External Client App in sdo to run |
| MCP recipes + Postman collection | done; hosted Tableau MCP `analyze_data` verified against `Cumulus_Insurance_Model_9881` (loss ratio by LOB → Personal Auto 55%) |
| Org cleanup: `scripts/cleanup_org.py` | done |

## The "[dataType] field is missing" saga (the one thing worth teaching)

`SemanticModelUpsert` failed four runs in a row with `Creation of semantic entities ([INS_Policies, INS_Claims, INS_Claim_Cases]) failed. caused by: The [dataType] field is missing.` even though:

- the DLO field metadata (`GET /ssot/data-lake-objects/<name>?`) showed `dataType` on every field,
- the identical SDM body created fine through the REST API against a DLO that had existed for a while (test template `Cumulus_Ins_Test`, hardcoded `INS_*_DLO1__dll`),
- the `${App.DataLakeObjects.<node>.Name}` token resolved correctly (`/app-framework/apps/{id}/assets?` shows `INS_Claims_DLO3__dll`).

Field-verified on run 4: the same SDM body posted **10 minutes after** the last DataStreamRun finished succeeded. So the DLO becomes readable by the semantic-model service a few minutes after the stream reports complete. Re-running a real stream as a "settle" step does not help (it just refreshes that DLO again; run 4 proved it). Fix in `atf/build_templates.py`: each template ingests a 1-row **clock** stream (`<PFX>_Clock`, not referenced by any semantic model) and runs it twice after the last real stream — a ~11-minute delay node built from the only node type that takes time. Wall time per install becomes ≈ 6 min × streams + 12 min.

Other field notes this phase: `sf org login device` no longer exists (use `sf org auth show-sfdx-auth-url`); `/app-framework/*` paths need a trailing `?`; DLO physical names get a numeric suffix on every re-install (tokens absorb it); DLOs created by an app cannot be deleted (`CANNOT_DELETE_ENTITY`) — leave them; viz JSON v67 rejects `mode`, `stylesheet`, `allHeaders`, font sizes >16; LWC boolean `@api` props must default to `false` (LWC1503); `.github/` is a protected path for the desktop bridge, so the workflow lives at `ci/promote.workflow.yml` until the repo exists.

## Next

1. Template tree is on the machine as `force-app/main/default/appTemplates.zip` (the bridge can't write 191 files cheaply) — unzip it in place, or regenerate with `python3 atf/build_templates.py && python3 atf/build_vizzes.py && python3 atf/build_templates.py`.
2. Hughbie to eyeball `T_Ext_Test` and the chain-created Insurance dashboard for LWC runtime behaviour.
3. Commit the template tree to the repo; create the 2GP package; create the ECA and run the embed sample.
4. P8 deck via Gamma → PPTX → Drive/Slides.

Also fixed: `sf api request rest --method DELETE` needs a body (`{}`) or it errors with "No 'mode' found in 'body' entry"; `sf_rest` now handles it and `scripts/cleanup_org.py` works (test SDMs removed; `T_Ext_Test` and `Cumulus_Ins_Test_*` kept for the LWC eyeball check).
