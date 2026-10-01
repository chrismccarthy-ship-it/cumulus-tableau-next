# Embedding SDK sample — Cumulus Service Command Center

A small Express app that embeds the Cumulus Retail Banking dashboard (and optionally the Analytics & Visualization Agent) in an external web page with the **Tableau Next Embedding SDK v2**.

```
embed/
├── server.js          OAuth 2.0 web-server flow (PKCE) → access token → frontdoor URL (never exposed to the page except on demand)
├── public/index.html  initializeAnalyticsSdk → AnalyticsDashboard (+ AnalyticsAgent), filters, events
├── package.json       @salesforce/analytics-embedding-sdk ^2.0.0
└── .env.example
```

## One-time org setup (Salesforce Admin + Tableau Next Admin)
1. Tableau Next → **Administration → External Client App → New**: callback URL `http://localhost:3000/getAccessToken`, OAuth flow **Web Server Flow**, enable **PKCE**, default scopes. Copy the consumer key (and secret if you enable "Require Secret").
2. Setup → **CORS** → add `http://localhost:3000`.
3. Setup → **Session Settings → Trusted Domains for Inline Frames** → add `localhost` (type **Lightning Out**).
4. Setup → **My Domain → Routing and Policies** → make sure **Require first-party use of Salesforce cookies** is *off*.
5. Users who view the page must exist in the org with **Tableau Next Consumer** (or higher) and access to the Cumulus workspace.

## Run
```bash
cd embed && cp .env.example .env   # fill in the ECA values
npm install && npm start           # http://localhost:3000 → "Sign in with Salesforce"
```

## What to show on stage
- The dashboard renders inside a non-Salesforce page with the user's own permissions.
- The branch dropdown calls `applyFilters([{ dataSource, fieldName: "RB_Service_Cases.BranchName", operator: "Equals", values }])`; the event log shows `UPDATED_FILTERS` / `UPDATED_SELECTIONS`.
- Set `window.CUMULUS_AGENT_ID` (or edit `index.html`) to embed the agent in **single-context mode** bound to the dashboard.
- Multi-org: swap the single `orgUrl/authCredential` for `orgConfigs: [...]` and pass `orgUrl` on each component (see the project doc "Analytics Embedding SDK").

Notes: frontdoor URLs are short-lived — the page fetches a fresh one on every load; `logout()` on the SDK logs out every Salesforce session in the browser; the semantic model API name in `applyFilters` is the one the App Template created (the chain derives it from the model label, e.g. `Cumulus_Retail_Banking_Model_988`) — read it from `GET /services/data/v67.0/ssot/semantic/models?`.
