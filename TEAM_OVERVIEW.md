# Cumulus Financial Group: Tableau Next demo kit

**Repo:** https://github.com/chrismccarthy-ship-it/cumulus-tableau-next

## What it is
A ready-to-install set of seven financial-services Tableau Next demos, plus the developer material to show how they were built. Each one ships its own synthetic data, so you can stand up a working workspace, semantic model and dashboard in a Data 360 + Tableau Next org without building anything by hand. All data is fictional, with no PII.

## What's included

| Demo (workspace) | Persona | The story it tells |
|---|---|---|
| Retail Banking | Branch service manager | Card-dispute cases spike at two branches after a fee change |
| Wealth | Advisor team lead | Households with fewer than 2 interactions a quarter churn ~3x |
| Asset Management | Institutional client service | Reconciliation requests breach SLA at quarter-end |
| Insurance | Claims service manager | A hail catastrophe adds ~40% to claim cycle time in three states |
| Commercial Banking | RM desk lead | Onboarding takes 2x longer without treasury products |
| Financial Advisors | Financial advisor | 30% of client life events get no follow-up in 14 days |
| Lending | Loan operations manager | Document collection is 55% of loan cycle time |

Per demo: 3-5 data streams, a semantic model (relationships, calculated measures, metrics), visualizations, and 2 dashboards (confirmed for Retail Banking and Wealth). Each demo also has a custom LWC extension (Next Best Actions, KPI tile, ranked bars or threshold banner).

Across the kit: 38 CSVs, about 197k rows, 7 workspaces, 65 visualizations, 7 dashboards (counts from the repo docs).

**Developer material** (for teams who want to build their own):
- MCP connection recipes and 7 prompt packs (Claude, Claude Code, Cursor, Agentforce, Postman)
- Postman collection covering the REST, Semantic Query, App Framework and MCP APIs
- Embedding SDK sample app (Node/Express) for embedding dashboards
- Dashboard Extension SDK examples (custom LWCs)
- Data kit manifests and 2GP packaging for sandbox-to-production moves
- Presenter guide and slide content in `deck/`

## How it can help your team
- **Skip the blank-canvas problem.** A realistic FS demo per line of business, each with a persona and a headline insight to present.
- **Install, don't build.** One command per demo creates the data streams, model and dashboards. The repo estimates 25-35 minutes per demo.
- **Show the developer surface.** The same repo teaches MCP, embedding, extensions and packaging with working examples.
- **Re-point to real orgs.** Column names follow Data 360 Financial Services vocabulary, so models can later be pointed at an Agentforce Financial Services org.

## Install (short version)
```bash
git clone https://github.com/chrismccarthy-ship-it/cumulus-tableau-next
cd cumulus-tableau-next
sf org login web --alias demo      # needs Data 360 + Tableau Next
scripts/install.sh demo Cumulus_Retail_Banking
```
Requires a user with Data Cloud Architect and Tableau Next Admin. No-install option: upload the CSVs from `force-app/main/default/appTemplates/<Template>/csvs/` into a workspace.

## Caveats to tell the team
- In my run (one org, 2026-11-05) each demo took closer to 60 minutes than 25-35, and one install failed on a transient upload error and needed a retry.
- On Windows, `scripts/install_template.py` can't launch `sf` (needs `sf.cmd`) and crashes on a `→` print.
- `manifests/manifest_lwc.xml` is missing the `CumulusConsoleActions` Apex class, so the LWC deploy fails on a fresh org until it's added.
- I haven't yet opened the dashboards in the UI, so rendering and the LWC widgets are unverified.
- The repo is public on GitHub, so anyone with the link can clone it. It references an internal enablement deck, so check that before sharing it with customers.
