# Presenter guide — Tableau Next for Builders

45 minutes of content, 15 of Q&A. Timings are per section; the slide numbers match `deck-content.md` (section dividers not counted). Before you start: sdo (or your demo org) open on the *Cumulus Insurance Overview* dashboard, Claude open with the Tableau Next MCP connector, a terminal in the repo folder, the GIF backups in `deck/gifs/` (record them after your first dry run — D1 workspace tour, D2 bind/click/re-bind, D3 manifest retrieve, D4 Claude ↔ MCP).

## A — Why (5 min)

**1 Title.** One sentence: "Everything you see today installs from one repo into any Tableau Next org in about 40 minutes."

**2 John Edwards.** The persona from the FinServ demo context. The line to land: John doesn't want a data project, he wants insight where his service teams already work. Our job as SEs is to show it in *his* line of business, in *his* org, quickly — that's why the developer surface matters to non-developers.

**3 Three challenges, four shifts.** Read the two stats (65/35 McKinsey, 71% disconnected). The fourth shift — manual → automated — is the one this deck is about. Don't linger.

**4 Building blocks.** Point at the semantic model and say it's the only thing everything else talks to. Everything after this slide is a consequence of that sentence.

**5 Map.** Build → Extend → Package → Deploy → Converse. Tell them which section they can skip if they only present (A, B, F) and which they need to build (C, D, E).

## B — Build (7 min)

**6 Semantic model is the center of gravity.** Mention the authoring API exists but that nobody in the room needs to call it — the App Template does. The "business preferences" bullet is the surprise: plain English in the model steers the agent (show the loss-ratio grouping rule if asked).

**7 Live demo 1 (3 min).** Tableau Next → Workspaces → Cumulus Insurance → Overview. Walk top to bottom: banner (it's an LWC — tease Section C), four KPIs, loss ratio by line (Personal Auto is worst), claims trend (point at June 2026 — the hail event), renewals by producer. Then ask the in-dashboard agent "Which line of business has the worst loss ratio?" If the agent stalls, move on; you'll do MCP later. Recovery: GIF D1.

**8 Seven examples.** Don't read the table; pick two headlines that match the room (retail card disputes, lending document collection). Say all seven are installed the same way and the data is synthetic and deterministic.

## C — Extend with LWC (10 min)

**9 Why extensions.** Native look, inherits filters, adds action. Name the four components.

**10 Anatomy.** Point at the three property *types*. That's the whole trick: the author chooses the model in the panel, the code never names one.

**11 Dynamic binding for humans.** The re-point story: same widget, Insurance → Lending, no deploy. Mention the LWC1503 boolean gotcha only if there are builders in the room.

**12 SDK in six lines.** Read the six calls aloud in order: get SDK, INIT, fetch, listen for filter changes, apply a filter. Everything else is UI.

**13 Live demo 2 (3 min).** Edit *Cumulus Insurance Overview* → Add widget → Cumulus Ranked Bars → bind model/dimension/measure → Save → click a bar → the page filters. Then open *Cumulus Lending Overview*, add the same widget, bind to loan officer/applications. Recovery: GIF D2. If the widget shows "configure me", that *is* the point — bind it.

**14 Prompting an agent.** These six directives are what produced working components on the first deploy. Encourage them to paste the slide into Claude Code with the repo open.

**15 Gotchas.** Fast. The one to emphasise: renaming a model field breaks bound widgets — API names are a contract.

## D — Package (7 min)

**16 Three ways.** Decision matrix. Manifests for one customer's sandbox→prod; data kit + 2GP when the data already exists; App Template when the org is empty (demos). We shipped all three.

**17 What an install does.** The chain graph. Read the node sequence once. Mention tokens (`${App.DataLakeObjects…}`) so they understand why re-installs don't collide.

**18 The one thing that fails.** This is the most useful slide in the deck for anyone who builds a template: DLOs aren't readable by the model service for ~10 minutes after load; the clock stream is the fix. Tell the story in 60 seconds: four failed installs, one manual test ten minutes later that worked, a 1-row stream run twice.

**19 Data kits and 2GP.** Three commands. Say the publishing sequence out loud (model → workspace → viz → dashboard) — it's the thing that fails silently in data kits.

## E — Deploy (5 min)

**20 Runbook.** Five steps; `scripts/promote.sh sandbox prod`. Emphasise "data kit first, LWCs before dashboards".

**21 Manifest anatomy.** Show the five metadata types. `build_manifests.py` means nobody hand-edits members.

**22 Permissions.** Read the deployer line and the viewer line; the rest is a checklist in the README.

**23 Pipeline.** PR = validate (dry-run), merge = deploy. Auth URL is a secret. Recovery if asked "does it work?": it's a standard `sf` CLI workflow; the interesting part is the preflight step for templates.

## F — Converse (8 min)

**24 MCP server.** Salesforce-hosted, 20 read-only tools, per-user OAuth. The one tool to remember is `analyze_data`. Beta authoring server exists; don't demo it.

**25 Live demo 3 (3 min).** In Claude: "Using the Cumulus Insurance model, what is the loss ratio by line of business and which line is worst?" Show the tool call and the answer (Personal Auto, 55%). Follow-up on the June 2026 hail month. Recovery: GIF D4, or the `mcp/prompts/` file.

**26 Embedding SDK.** Walk the flow arrow once: ECA → OAuth → token → frontdoor URL → `initializeAnalyticsSdk`. The code is eight lines; the Express sample in `embed/` runs locally after the four org settings on the permissions slide.

**27 Agent embed, filters, events.** Single-context agent bound to a dashboard; event names; frontdoor URLs are short-lived. If time is short, skip.

**28 REST + Semantic Query API.** Where raw numbers come from; Postman collection. Say "trailing `?` on app-framework paths" — it will save someone an hour.

## G — Close (3 min)

**29 Get started in 40 minutes.** Four commands. Point at the README.

**30 Why it matters.** Four shifts, back to John Edwards. Stop talking; take questions.

## Likely questions

- *Is the Dashboard Extension SDK GA?* Introduced Spring '26 as beta; Tableau's feature page lists dynamic data binding as GA; check the release notes for the customer's release before promising it.
- *Can I use this with real FSC data?* Yes — re-point the extensions and vizzes at an FSC semantic model; the data kit path is designed for that.
- *Why not one PPTX/Slides deck from Gamma?* The Gamma plan caps 10 cards per generation; the deck is a 7-page Gamma merged into one PPTX for Slides.
- *Does the MCP server respect permissions?* Yes, every call runs as the signed-in user via the External Client App.
- *How long does an install take?* ≈ 6 minutes per data stream plus the 11-minute clock delay; Insurance (3 streams) is 28 minutes; Wealth/Commercial (5 streams) about 45. Six templates installed in parallel in ~45 minutes.
