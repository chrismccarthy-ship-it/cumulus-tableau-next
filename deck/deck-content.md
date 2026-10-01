# Tableau Next for Builders
## MCP, SDKs, APIs & CLI for Financial Services demos
Service Solutions enablement · 45 minutes + Q&A
Everything in this deck is installable from the `cumulus-tableau-next` repo — seven line-of-business demos, four LWC extensions, one command.

---

# Meet John Edwards, CIO of Cumulus Bank
**Cumulus Financial Group** is our single fictional institution for every demo: retail banking, wealth, asset management, insurance, commercial banking, financial advisors, lending.
John's mandate: give service teams insight *in the flow of work* without another data project.
His question to us: "Can your people show me this in my industry, in my org, next week?" — this session is how we say yes.

---

# Three challenges, four shifts

| Challenge | What the data says | The shift Tableau Next enables |
|---|---|---|
| Capacity crisis | Advisors spend ~65% of time on admin, 35% with clients (McKinsey) | Overburdened workforce → AI-supported capacity (Analytics Agent, MCP) |
| Data dilemma | 71% of financial-services systems are disconnected | Siloed data → one semantic model on Data 360 |
| Cost of compliance | Every new tool is another audit surface | Compliance catch-up → compliance by design (permission sets, OAuth, per-user MCP access) |

Fourth shift: manual processes → automated — CLI deploys, data kits, App Templates. That is the builder story we tell today.

---

# What Tableau Next is made of

Five building blocks, one center of gravity:
- **Workspace** — the folder-with-permissions that holds everything below
- **Semantic model** — data objects, relationships, measures, calculated fields, metrics — built on Data 360
- **Metric** — a named, governed number (loss ratio, first-contact resolution)
- **Visualization** — one chart, one semantic model
- **Dashboard** — a layout of vizzes, filters and (our addition) custom LWC extension widgets

Change the data underneath and dashboards keep working, because every viz points at the model, not at a table.

---

# Today's map

**Build → Extend → Package → Deploy → Converse**
1. Build — a semantic model, vizzes and a dashboard per line of business
2. Extend — four reusable LWC dashboard extensions with dynamic data binding
3. Package — App Templates, data kits, 2GP
4. Deploy — CLI manifests, sandbox to production, a GitHub Actions pipeline
5. Converse — the Tableau Next MCP server, the Embedding SDK, REST and Semantic Query APIs

One repo. Every demo reproducible in under 40 minutes in any Tableau Next org.

---

# Section B — Build

---

# The semantic model is the center of gravity

- It is the only thing vizzes, dashboards, extensions, the MCP server and the Analytics Agent ever talk to
- One model per line of business: 3–5 data objects, many-to-one relationships, 6–10 measures, 2–4 calculated measures (ratios, averages, counts), 4–6 metrics
- Authoring API: `POST /services/data/v67.0/ssot/semantic/models` — the same JSON the App Template ships
- Business preferences in the model (plain English) steer the Analytics Agent: "ratios that divide across objects should be grouped by the denominator object"

Lesson from the build: get the model right and everything above it is cheap to regenerate.

---

# Live demo 1 — the Cumulus Insurance workspace

Click path: Tableau Next → Workspaces → *Cumulus Insurance* → *Cumulus Insurance Overview*
- Four KPI tiles: premium in force, open claims, average claim cycle time, loss ratio
- Loss ratio by line (Personal Auto worst at 55%), claims trend with the June 2026 hail spike, renewals by producer, Agentforce-handled claim cases
- The red **Threshold Banner** at the top is a custom LWC — we come back to it in Section C
- Ask the agent from the dashboard: "Which line of business has the worst loss ratio?"

Backup: pre-recorded GIF D1 in the repo.

---

# Seven Cumulus examples, one headline each

| Line of business | Persona | Headline insight |
|---|---|---|
| Retail Banking | Branch service manager | Card-dispute cases spike in two branches after a fee change |
| Wealth | Advisor team lead | Households with fewer than 2 interactions a quarter churn 3× more |
| Asset Management | Institutional client service | Reconciliation requests breach SLA at quarter-end |
| Insurance | Claims service manager | The hail event drives a 40% cycle-time increase |
| Commercial Banking | RM desk lead | Onboarding takes 2× longer without treasury products |
| Financial Advisors | Individual advisor | 30% of life events get no follow-up in 14 days |
| Lending | Loan operations manager | Document collection is 55% of cycle time |

196,778 synthetic rows across 38 tables, seeded and deterministic — no customer data anywhere.

---

# Section C — Extend with LWC

---

# Why dashboard extensions

- **Native look**: the widget lives in the dashboard grid, inherits filters, resizes with the layout
- **Adds action**: a ranked list that filters the dashboard on click, a banner that turns red above a threshold, a next-best-action list with record links
- **Reusable**: one component, any semantic model — the dashboard author binds it in the widget panel, no redeploy

Four extensions ship in the repo: `cumulusKpiTile`, `cumulusRankedBars`, `cumulusNextBestActions`, `cumulusThresholdBanner`.

---

# Anatomy of an extension

```xml
<LightningComponentBundle xmlns="http://soap.sforce.com/2006/04/metadata">
  <apiVersion>67.0</apiVersion>
  <isExposed>true</isExposed>
  <masterLabel>Cumulus KPI Tile</masterLabel>
  <targets><target>analytics__Dashboard</target></targets>
  <targetConfigs>
    <targetConfig targets="analytics__Dashboard">
      <property name="sdmName" type="SemanticModel" label="Semantic model"/>
      <property name="measure" type="SemanticMeasure" label="Measure"/>
      <property name="target"  type="Number" label="Target"/>
    </targetConfig>
  </targetConfigs>
</LightningComponentBundle>
```
The three property types — `SemanticModel`, `SemanticMeasure`, `SemanticDimension` — are what make binding dynamic.

---

# Dynamic data binding, for humans

- The dashboard author picks the model, measure and dimension in the widget panel
- Your code just reads `this.sdmName`, `this.measure`, `this.dimension` — it never hard-codes a model name
- Re-point the same widget from Insurance to Lending without touching code
- Guard for "not configured yet": show a friendly message, report `NODATA`, don't throw

Gotcha we hit: boolean `@api` properties must default to `false` (LWC1503) — name them so false is the safe default (`belowIsBad`).

---

# The SDK in six lines

```js
import { getAnalyticsSdk } from "analytics/sdk";
const sdk = await getAnalyticsSdk(this);
sdk.notifyLifecycleChange(this, "INIT");
const rows = await sdk.fetchDataUsingQueryAndSource(query, { type: "SemanticModel", name: this.sdmName.apiName });
sdk.on("FILTER_CHANGE", () => this.refresh());
sdk.applyFilter({ dataSource: this.sdmName.apiName, fieldName: "INS_Policies.LineOfBusiness", operator: "Equals", values: [line] });
```
`cumulusSdkUtils` in the repo wraps the query builder, row normalisation and lifecycle events so each extension is ~120 lines.

---

# Live demo 2 — bind, click, re-bind

1. Edit *Cumulus Insurance Overview* → add widget → **Cumulus Ranked Bars**
2. Bind: model = Cumulus Insurance Model, dimension = Producer, measure = Premium
3. Click a bar → every viz on the page filters to that producer
4. Open *Cumulus Lending Overview*, drop the same widget, bind to Loan Officer / Applications — no deploy

The extension widget is also shipped *inside* the App Template dashboard JSON (`type: "extension"`, `source.name: "c:cumulusRankedBars"`), so installs arrive pre-bound.

---

# Prompting an AI agent to write one correctly

Six directives that produced working components on the first deploy:
1. Target `analytics__Dashboard`, apiVersion 67.0, `isExposed` true
2. Use `SemanticModel` / `SemanticMeasure` / `SemanticDimension` property types, never string model names
3. Call `notifyLifecycleChange` for INIT, LOADED, NODATA, ERROR
4. Subscribe to `FILTER_CHANGE`; unsubscribe in `disconnectedCallback`
5. Add `semanticAggregationMethod` only to `Object.Field` references, not calculated measures
6. Keyboard-operable with ARIA state; no external CSS

Verify: unmapped → model A → model B, in that order.

---

# Extension gotchas

- apiVersion 66.0 or higher; the dynamic-binding org setting must be on
- Renaming a model field breaks every widget bound to it — treat semantic model API names as a contract
- Font sizes, colors and layout come from the dashboard theme; don't fight it
- Mobile: dashboards stack widgets, so keep extensions narrow-safe
- A missing LWC in the target org renders as an empty widget, not a deploy error — deploy LWCs first

---

# Section D — Package

---

# Three ways assets travel

| Path | What moves | Best for | Status |
|---|---|---|---|
| Metadata manifests (`package.xml`) | Workspaces, vizzes, dashboards, LWCs | Sandbox → production in one customer | GA |
| Data kit + 2GP package | Data streams, DLOs, semantic models + assets + LWCs | ISV / cross-org distribution when the data already exists | GA |
| App Template Framework | CSVs, streams, model, vizzes, dashboard — created from scratch on install | Demos in *any* org, including empty ones | Template Builder Beta; REST + `sf orchestrator` plugin work today |

We shipped all three; the App Template is what makes "install in any org in 40 minutes" true.

---

# App Template Framework — what an install actually does

The `create-chain.json` is a graph of nodes the platform runs in order:
`CSVUpsert → DataStreamUpsert → DataStreamRun` (per table, serial) → `WorkspaceUpsert → SemanticModelUpsert → VisualizationUpsert ×10 → DashboardUpsert`
- Tokens resolve at runtime: `${App.DataLakeObjects.INS_Policies_DLO.Name}`, `${App.SemanticModels.Cumulus_Insurance_SDM.Id}`
- Variables drive the wizard: label suffix, "create dashboard?"
- Create by REST (`POST /app-framework/apps?`) or `sf orchestrator app create`

Insurance install: 55 nodes, 28 minutes, zero manual steps.

---

# The one thing that fails (and the fix)

Symptom: `SemanticModelUpsert` fails with **"The [dataType] field is missing"** even though the DLO fields are all there.
Cause: a freshly loaded DLO is not readable by the semantic-model service for roughly ten minutes after its stream reports complete.
What does not work: re-running a real stream as a "settle" step — it just makes that DLO fresh again.
What works: a 1-row **clock** stream that no model reads, run twice after the last real stream — an 11-minute delay node built from the only node type that takes time.

Field-verified over five installs; every template in the repo ships with it.

---

# Data kits and 2GP in three commands

**Data kit** (Data 360 Setup → Data Kits): add the streams, DLOs and semantic models, download its manifest, retrieve it — respect the publishing sequence: model → workspace → viz → dashboard.

```bash
sf package create --name CumulusTableauNext --package-type Unlocked --path force-app -v devhub
sf package version create --package CumulusTableauNext --installation-key-bypass --wait 30 -v devhub
sf package version promote --package CumulusTableauNext@0.1.0-1 -v devhub
```
LWCs and App Templates are ordinary metadata — they go in the same package. Data-kit members do not include LWCs or Flows.

---

# Section E — Deploy

---

# Sandbox → production runbook

1. `sf org login web -a sandbox` and `-a prod`; confirm both API versions (`sf org display`) — manifests must not exceed the target
2. Retrieve: data kit → LWCs → assets (`sf project retrieve start --manifest …`)
3. Deploy the data kit first; run its streams in prod (the kit ships structure, not rows)
4. Deploy LWCs, then assets
5. `scripts/verify.sh prod` — every workspace, model and dashboard present

`scripts/promote.sh sandbox prod` runs the whole thing; `--check-only` validates without deploying.

---

# Manifest anatomy

```xml
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
  <types><members>Cumulus_Insurance_WS</members><name>AnalyticsWorkspace</name></types>
  <types><members>INS_Loss_Ratio_By_LOB</members><name>AnalyticsVisualization</name></types>
  <types><members>Cumulus_Insurance_Overview</members><name>AnalyticsDashboard</name></types>
  <types><members>cumulusThresholdBanner</members><name>LightningComponentBundle</name></types>
  <types><members>Cumulus_Insurance</members><name>AppFrameworkTemplateBundle</name></types>
  <version>67.0</version>
</Package>
```
API names are the last URL segment of each asset (`…/tableau/dashboard/<name>/view`). `scripts/build_manifests.py` generates all four manifests from the template tree so they never drift.

---

# Permissions and prerequisites

- **Deployer**: Data Cloud Architect, Tableau Next Admin, Metadata API Edit Access, Approve Uninstalled Connected Apps
- **Viewers**: Tableau Next Consumer + workspace access
- **MCP `analyze_data`**: Concierge / Analytics Q&A enabled in the org
- **Embedding**: an External Client App, CORS entry, trusted domain for inline frames, first-party cookie requirement off
- **Org settings**: dynamic data binding on; API 66.0+; Data 360 provisioned

Everything above is a checklist in the repo README.

---

# The pipeline — `ci/promote.workflow.yml`

- Pull request touching `force-app/**` or `manifests/**` → `atf/preflight.py` (template rules) → manifests regenerated and diffed → `sf project deploy start --dry-run` against production
- Merge to `main` → real deploy, LWCs first, then assets → `verify.sh`
- Auth via `SFDX_AUTH_URL_*` secrets from `sf org auth show-sfdx-auth-url`; the URL is a credential — never log it

Copy the file into `.github/workflows/` once your repo exists.

---

# Section F — Converse

---

# The Tableau Next MCP server

- Salesforce-hosted: `https://api.salesforce.com/platform/mcp/v1/analytics/tableau-next`
- Twenty read-only tools: `list_semantic_models`, `list_semantic_model_metrics`, `get_dashboard`, `search_assets` … and **`analyze_data`** — a natural-language question answered by the Analytics Agent against the best-matching model
- Per-user OAuth through an External Client App; a Consumer sees only what they can see in the UI
- Beta authoring server adds create/update for dashboards, models, vizzes and alerts

Connect Claude, Claude Code, Cursor or Agentforce — recipes in `mcp/README.md`.

---

# Live demo 3 — ask the org a question

Prompt in Claude: *"Using the Cumulus Insurance model, what is the loss ratio by line of business and which line is worst?"*
- Claude calls `analyze_data` → the agent writes a semantic query (row grouping on `INS_Policies.LineOfBusiness`, `USER_AGG(Loss_Ratio)`) → answer: Personal Auto, 55%
- Follow-up: *"Show me the same for the June 2026 hail month"* — the agent adds a date filter
- Metadata tools let Claude discover the fields before asking

Twenty ready prompts per line of business in `mcp/prompts/`.

---

# Embedding SDK v2 — dashboards in your own app

Flow: External Client App → web-server OAuth (PKCE) → access token → `POST /services/oauth2/singleaccess` → **frontdoor URL** → `initializeAnalyticsSdk({ authCredential, orgUrl })`

```js
import { initializeAnalyticsSdk, AnalyticsDashboard } from "@salesforce/analytics-embedding-sdk";
await initializeAnalyticsSdk({ authCredential: frontdoorUrl, orgUrl });
const dash = new AnalyticsDashboard({ parentIdOrElement: "host", idOrApiName: "Cumulus_Retail_Banking_Overview" });
await dash.render();
await dash.applyFilters([{ dataSource: "Cumulus_Retail_Banking_Model_988", fieldName: "RB_Service_Cases.BranchName", operator: "Equals", values: ["Cumulus NY Branch 1"] }]);
```
v2.0 is mandatory since July 2026. `embed/` in the repo is a running Express sample.

---

# Analytics Agent embed, filters and events

- `AnalyticsAgent` with `contextConfig: { contextType: DASHBOARD, contextTypeIdOrApiName }` — the agent answers *about this dashboard*
- Events: `COMPONENT_LOADED`, `UPDATED_FILTERS`, `UPDATED_SELECTIONS`, global `ERROR`
- Multi-org: `orgConfigs: [...]` and `orgUrl` per component
- Frontdoor URLs are short-lived — fetch one per page load; SDK `logout()` ends every Salesforce session in the browser

The Cumulus sample page: dashboard on the left, agent on the right, event log underneath.

---

# REST and Semantic Query API — when you need raw numbers

- **Semantic Query API**: `POST /services/data/v67.0/semantic-engine/gateway` — the same query the agent writes, as JSON: fields, row groupings, aggregation, filters, sort, limit
- **Tableau Next REST**: `/tableau/workspaces`, `/visualizations`, `/dashboards` — create, read, share, download
- **Semantic model authoring**: `/ssot/semantic/models` and sub-resources; `/validate` before you save
- **Data 360 SQL**: `/ssot/queryv2` for the DLO rows themselves
- **App Framework**: `/app-framework/templates?` and `/apps?` (note the trailing `?`)

Postman collection in `postman/` — every call above, pre-filled for Cumulus.

---

# Section G — Close

---

# Get started in 40 minutes

1. Clone `cumulus-tableau-next`; `sf org login web -a demo`
2. `sf project deploy start --manifest manifests/manifest_lwc.xml -o demo`
3. `python3 scripts/install_template.py --org demo --template Cumulus_Insurance`
4. Open *Cumulus Insurance Overview*; connect Claude to the MCP server; ask your first question

Then install the other six. Questions, fixes, ideas: the repo README and the Service Solutions Tableau Next channel.

---

# Why this matters for Cumulus

- Overburdened workforce → analytics and an agent in the flow of work
- Siloed data → one governed semantic model per line of business
- Manual processes → templated installs, scripted deploys, a pipeline
- Compliance catch-up → OAuth, permission sets, per-user MCP access, nothing hard-coded

John Edwards gets an industry-specific demo in his org next week. Every SE in this room can build it.

---

# Appendix A1 — Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `The [dataType] field is missing` on SemanticModelUpsert | DLO not yet readable after load | Clock-stream delay node (built into every template) |
| `No 'mode' found in 'body' entry` on `sf api request rest --method DELETE` | CLI requires a body | Pass `--body "{}"` |
| Viz JSON rejected: `mode`, `stylesheet`, `allHeaders`, font size > 16 | Old field names | Use the v67 style shape in `atf/build_vizzes.py` |
| LWC1503 on deploy | Boolean `@api` default `true` | Rename so `false` is the default |
| App-framework call returns 404 | Missing trailing `?` | `/app-framework/apps?` |
| DLO names like `INS_Policies_DLO3__dll` | Re-installs add a suffix | Tokens absorb it; leave old DLOs (they cannot be deleted) |

---

# Appendix A2 — MCP tool catalog

`analyze_data`, `list_semantic_models`, `get_semantic_model`, `get_semantic_model_logical_view`, `list_semantic_model_data_objects`, `list_semantic_model_dimensions`, `list_semantic_model_measures`, `list_semantic_model_calculated_dimensions`, `list_semantic_model_calculated_measures`, `list_semantic_model_metrics`, `get_semantic_model_metric`, `list_semantic_model_relationships`, `list_workspaces`, `list_workspace_assets`, `list_dashboards`, `get_dashboard`, `list_visualizations`, `get_visualization`, `search_assets`
All read-only; every call runs as the signed-in user.

---

# Appendix A3 — Sources

Salesforce Help and Developer docs: Tableau Next MCP server reference and guide; Tableau Next REST API; Semantic Layer / Semantic Query API; App Template Framework overview and Get Started; Dashboard Extension SDK for LWC; Embedding SDK v2 (Get Started, Integrating, Add Functionality, Set Up, Best Practices, Troubleshooting); Data 360 data kits and packaging; Use CLI to Deploy Tableau Next Assets. Industry statistics from the Salesforce Financial Services demo context (McKinsey, Capgemini, Salesforce research). All demo data is synthetic.
