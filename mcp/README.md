# Tableau Next MCP — connection recipes

The **Tableau Next MCP server** is a Salesforce-hosted MCP server that exposes your org's Tableau Next assets and semantic models to any MCP-compatible AI client. It is *not* the Tableau Cloud MCP at `mcp.tableau.com` (that one talks to Tableau Cloud sites, not Salesforce orgs).

| | |
|---|---|
| Production URL | `https://api.salesforce.com/platform/mcp/v1/analytics/tableau-next` |
| Sandbox / scratch URL | `https://api.salesforce.com/platform/mcp/v1/sandbox/analytics/tableau-next` |
| Auth | Per-user OAuth 2.0 + PKCE through an **External Client App (ECA)**; the user's permissions apply to every tool call |
| Tools | 20 read-only tools (below); a separate **Beta** server adds create/update/delete for dashboards, semantic models, visualizations and alerts |
| Needs | Tableau Next Admin (to add the server), Concierge / Analytics Q&A enabled (for `analyze_data`) |

Docs: https://developer.salesforce.com/docs/platform/hosted-mcp-servers/guide/tableau-next.html

## Tool catalog (production server)

| Group | Tools |
|---|---|
| Ask questions | `analyze_data` (natural-language question → Analytics Agent answers from the best-matching semantic model) |
| Dashboards & vizzes | `list_dashboards`, `get_dashboard`, `list_visualizations`, `get_visualization` |
| Semantic model structure | `list_semantic_models`, `get_semantic_model`, `list_semantic_model_data_objects`, `list_semantic_model_relationships`, `get_semantic_model_logical_view` |
| Business logic | `list_semantic_model_measures`, `list_semantic_model_dimensions`, `list_semantic_model_metrics`, `get_semantic_model_metric`, `list_semantic_model_calculated_dimensions`, `list_semantic_model_calculated_measures` |
| Discovery | `list_workspaces`, `list_workspace_assets`, `search_assets` |

> Screenshot the live tool list during the build — some Salesforce pages call the Q&A tool `query_semantic_data`; the live server returns `analyze_data`.

## One-time admin setup (any client)

1. Setup → **Salesforce Hosted MCP Servers** → enable, and activate the *Tableau Next* server.
2. Setup → **External Client App Manager** → New. OAuth: enable **Web Server Flow** + **PKCE**, scopes `api`, `refresh_token, offline_access`, plus the MCP scope shown in Setup. Add the callback URL for each client (below).
3. Copy the **Consumer Key** — it is the OAuth *Client ID* every client asks for.
4. Assign users **Tableau Next Consumer** (view) or Platform Analyst/Admin as appropriate; enable **Concierge: Analytics Q&A** for `analyze_data`.

## Client recipes

### Claude (claude.ai / Claude Desktop)
Settings → Connectors → **Add custom connector** → URL = production URL above → *Advanced* → OAuth Client ID = ECA Consumer Key → Connect → sign in to the org. Callback URL to whitelist in the ECA: `https://claude.ai/api/mcp/auth_callback` (check Setup for the current value).

### Claude Code
```bash
claude mcp add --transport http tableau-next \
  https://api.salesforce.com/platform/mcp/v1/analytics/tableau-next \
  --callback-port 38000 --client-id <ECA_CONSUMER_KEY>
claude            # then type /mcp → tableau-next → Authenticate
```
ECA callback URL: `http://localhost:38000/callback`.

### Cursor
`~/.cursor/mcp.json`:
```json
{ "mcpServers": { "tableau-next": { "url": "https://api.salesforce.com/platform/mcp/v1/analytics/tableau-next" } } }
```
Cursor performs the OAuth flow natively; add its callback URL (shown in Cursor's MCP settings) to the ECA.

### Agentforce (Agent Builder / Agentforce Vibes)
Agentforce Vibes has the hosted servers auto-enabled — no ECA needed. For an Agentforce agent, add the hosted MCP server as an action source in Agent Builder (Setup → Agentforce → MCP Servers) and expose `analyze_data` + `search_assets` as actions. Salesforce notes native Agentforce calls are 10–20x faster than desktop clients.

### Postman
Import `postman/cumulus-tableau-next.postman_collection.json`; the MCP folder uses Postman's MCP request type against the production URL with OAuth 2.0 (PKCE) — Client ID = ECA Consumer Key.

## Demo script (slide 27)
1. In Claude: *"Which Cumulus retail branches have rising Card Dispute cases since May?"* → `analyze_data` finds `Cumulus_Retail_Banking_SDM` and answers (BR-003, BR-011).
2. *"What semantic models do I have for Cumulus?"* → `list_semantic_models`.
3. *"Show me the metrics in the wealth model and explain Net New Assets."* → `list_semantic_model_metrics` → `get_semantic_model_metric`.
4. *"Open the insurance claims dashboard"* → `search_assets` + `get_dashboard` returns the URL.

Per-LOB prompt packs are in `mcp/prompts/`.
