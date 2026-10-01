# Cumulus Financial Group — Tableau Next demo kit

Seven financial-services line-of-business examples for Tableau Next (retail banking, wealth, asset management, insurance, commercial banking, financial advisors, lending), built to be installed into any Salesforce org with Data 360 + Tableau Next, and to teach the developer surface: **MCP, Embedding SDK, Dashboard Extension SDK (custom LWC), REST / Semantic Query APIs, data kits, 2GP packaging, CLI deployment and the App Template Framework**.

Companion to the *Tableau Next for Builders* enablement deck (Service Solutions org). Fictional data; synthetic people; no PII.

## Quick start (30 minutes)

```bash
git clone <this repo> && cd cumulus-tableau-next
sf org login web --alias demo                          # an org with Data 360 + Tableau Next enabled
python3 data/generate.py && python3 data/validate.py   # 38 CSVs, ~197k rows (seed 42) + integrity checks
python3 atf/build_templates.py && python3 atf/preflight.py   # 7 App Template Framework templates
scripts/install.sh demo Cumulus_Retail_Banking         # deploy the template + Create App (~25–35 min, unattended)
```

**How it installs:** each LOB is an **App Template Framework "CSV data template"**. The template ships its own CSVs; *Create App* runs a chain that uploads each CSV → creates a Data Stream + DLO → refreshes it → creates the workspace → the semantic model (objects, relationships, calculated measures, metrics) → visualizations → dashboard. No Data 360 configuration beforehand, no hard-coded org names (every asset is bound through `${App.…}` tokens). Ingestion runs serially at ~6 min per stream, so templates are kept to 3–5 streams. Equivalent CLI: `sf orchestrator app create --template-name Cumulus_Retail_Banking -o demo`.

Fast path with no install (present-only): in Tableau Next open a workspace → **Add → Semantic Model → Upload file** and upload the CSVs from `force-app/main/default/appTemplates/<Template>/csvs/`.

## Repository layout

| Path | What | Phase |
|---|---|---|
| `data/generate.py`, `data/validate.py` | Synthetic data generator + validator; `data/DATA_DICTIONARY.md`; `data/ingestion/cumulus_schema.yaml` (Ingestion API schema) | P1 ✅ |
| `data/out/<lob>/*.csv` | Generated CSVs (regenerate any time) | P1 ✅ |
| `mcp/` | Tableau Next MCP connection recipes (Claude, Claude Code, Cursor, Agentforce, Postman) + 7 prompt packs | P6 ✅ |
| `postman/` | Postman collection: REST API, Semantic Query API, App Framework API, MCP | P6 ✅ |
| `atf/build_templates.py`, `atf/preflight.py` | Generates the 7 ATF templates (denormalized CSVs, data streams, semantic models, chain) and checks them against the packaging rules | P2 ✅ |
| `force-app/main/default/appTemplates/Cumulus_*/` | The seven installable templates (`csvs/`, `datastreams/`, `sdms/`, `workspaces/`, `create-chain.json`, …); `visualizations/` + `dashboards/` arrive in P3 | P2 ✅ / P3 |
| `scripts/` | `install.sh`, `install_template.py` (deploy + Create App + poll), `load_data.py` (alternative Ingestion API bulk loader), `verify.sh` | P7 (draft) |
| `manifests/` | `manifest_lwc.xml`; `manifest_assets.xml` + data-kit manifest for the *sandbox → production* teaching path (P5) | P5 |
| `force-app/main/default/` | Data kit metadata, semantic models, Tableau Next assets, `lwc/` extensions | P2–P5 |
| `embed/` | Node/Express sample: ECA web-server flow → frontdoor URL → `AnalyticsDashboard` / `AnalyticsAgent` embeds | P6 |
| `docs/` | Presenter guide, deployment runbook, troubleshooting | P8 |

## The seven examples

| Workspace | Persona | Headline insight | Extension |
|---|---|---|---|
| `Cumulus_Retail_Banking` | Branch service manager | Card-dispute cases spike in BR-003 / BR-011 after the May 2026 fee change; Lauren Bailey's $75 dispute | Next Best Actions |
| `Cumulus_Wealth` | Advisor team lead | Households with < 2 interactions/quarter churn ~3×; Ashford Family Office $40M onboarding | KPI tile |
| `Cumulus_Asset_Management` | Institutional client service | Reconciliation requests breach SLA at quarter-end | Ranked bars |
| `Cumulus_Insurance` | Claims service manager | June 2026 hail CAT drives +40% cycle time in CO/UT/AZ; Elena Ruiz HO-3 | Threshold banner |
| `Cumulus_Commercial` | RM desk lead | Onboarding takes 2× longer without treasury products; Meridian Logistics sFTP/ACH | KPI tile |
| `Cumulus_Advisors` | Financial advisor | 30% of life events get no follow-up in 14 days | Next Best Actions (re-bound) |
| `Cumulus_Lending` | Loan operations manager | Document collection = 55% of cycle time; digital 25% faster | Threshold banner |

## Data model conventions

Column names follow Data 360 Financial Services DMO vocabulary where one exists (Financial Account, Financial Account Transaction, Financial Holding, Insurance Policy, Application) so the semantic models can later be re-pointed at a real Agentforce Financial Services org. Every table has a single-column primary key; `*Id` columns are foreign keys validated by `data/validate.py`. See `data/DATA_DICTIONARY.md`.

## Status
- P0 environment ✅ · P1 data ✅ · P2 templates (data streams + semantic models) ✅ · P6 MCP/Postman ✅ · repo skeleton ✅
- Next: first live install in the build org (P2 verification) → P3 visualizations + dashboards → P4 LWCs → P5 sandbox→prod manifests + data kit + 2GP → P7 install hardening → P8 deck.
