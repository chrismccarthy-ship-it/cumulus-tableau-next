#!/usr/bin/env python3
"""
Create / update the two full-page console dashboards (one extension widget each) in a live org and write the
same dashboard JSON (tokenised) into the templates so a fresh install ships them.

  python3 scripts/publish_console.py --org buildorg
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_template import sf_rest  # noqa: E402
from publish_dashboard import app_tokens  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "force-app", "main", "default", "appTemplates")
LOB_CONFIGS = {
    "Cumulus_Asset_Management": {"entity": {"field": "AM_Service_Requests.ClientName", "label": "Client"}, "month": "Request_Month", "region": {"field": "AM_Service_Requests.Region", "label": "Region"},
        "kpis": [{"name": "Request_Count", "label": "Service requests", "format": "number", "upGood": False, "weight": True}, {"name": "SLA_Breach_Rate", "label": "SLA breach rate", "format": "percent", "upGood": False, "primary": True}, {"name": "Avg_Cycle_Time", "label": "Avg cycle (days)", "format": "number", "upGood": False}],
        "extra": {"dims": ["AM_Mandates.ClientName"], "kpis": [{"name": "Total_AUM", "label": "AUM", "format": "currency", "upGood": True}]},
        "target": {"kpi": "SLA_Breach_Rate", "value": 0.2}, "persona": "Client service lead", "domain": "Client Service Insights", "modelLabel": "Cumulus Asset Management", "slack": "am-client-service"},
    "Cumulus_Insurance": {"entity": {"field": "INS_Claims.State", "label": "State"}, "month": "INS_Claims.LossMonth", "region": {"field": "INS_Claims.LineOfBusiness", "label": "Line"},
        "kpis": [{"name": "Claim_Count", "label": "Claims", "format": "number", "upGood": False, "weight": True}, {"name": "Total_Paid", "label": "Paid", "format": "currency", "upGood": False}, {"name": "Avg_Claim_Cycle_Time", "label": "Avg cycle (days)", "format": "number", "upGood": False, "primary": True}, {"name": "Open_Claims", "label": "Open claims", "format": "number", "upGood": False}, {"name": "CAT_Claims", "label": "Catastrophe claims", "format": "number", "upGood": False}],
        "target": {"kpi": "Avg_Claim_Cycle_Time", "value": 14}, "persona": "Claims service manager", "domain": "Claims Insights", "modelLabel": "Cumulus Insurance", "slack": "claims-leadership"},
    "Cumulus_Commercial": {"entity": {"field": "CB_Deals.RelationshipManagerName", "label": "Relationship Manager"}, "month": "Deal_Month", "region": {"field": "CB_Deals.Region", "label": "Region"},
        "kpis": [{"name": "CB_Deals.DealId", "agg": "Count", "label": "Deals", "format": "number", "upGood": True, "weight": True}, {"name": "Pipeline_Amount", "label": "Pipeline", "format": "currency", "upGood": True}, {"name": "Won_Amount", "label": "Won", "format": "currency", "upGood": True}, {"name": "Win_Rate", "label": "Win rate", "format": "percent", "upGood": True, "primary": True}],
        "extra": {"dims": ["CB_Credit_Facilities.RelationshipManagerName"], "kpis": [{"name": "Total_Commitments", "label": "Commitments", "format": "currency", "upGood": True}, {"name": "Avg_Utilization", "label": "Utilization %", "format": "number", "upGood": False}]},
        "persona": "RM desk lead", "domain": "Relationship Insights", "modelLabel": "Cumulus Commercial Banking", "slack": "commercial-desk"},
    "Cumulus_Advisors": {"entity": {"field": "FA_Life_Events.AdvisorName", "label": "Advisor"}, "month": "Event_Month", "region": {"field": "FA_Life_Events.Region", "label": "Region"},
        "kpis": [{"name": "Life_Events", "label": "Life events", "format": "number", "upGood": True, "weight": True}, {"name": "Followup_Rate", "label": "Follow-up in 14 days", "format": "percent", "upGood": True, "primary": True}, {"name": "Life_Event_Opportunity", "label": "Opportunity", "format": "currency", "upGood": True}],
        "extra": {"dims": ["FA_Book_Of_Business.AdvisorName"], "kpis": [{"name": "Book_AUM", "label": "Book AUM", "format": "currency", "upGood": True}, {"name": "Household_Count", "label": "Households", "format": "number", "upGood": True}]},
        "target": {"kpi": "Followup_Rate", "value": 0.9}, "persona": "Advisor team lead", "domain": "Advisor Insights", "modelLabel": "Cumulus Financial Advisors", "slack": "advisor-leadership"},
    "Cumulus_Lending": {"entity": {"field": "LN_Applications.LoanOfficerName", "label": "Loan Officer"}, "month": "LN_Applications.SubmittedMonth", "region": {"field": "LN_Applications.Region", "label": "Region"},
        "kpis": [{"name": "Applications", "label": "Applications", "format": "number", "upGood": True, "weight": True}, {"name": "Pull_Through_Rate", "label": "Pull-through", "format": "percent", "upGood": True, "primary": True}, {"name": "Avg_Time_To_Close", "label": "Avg time to close (days)", "format": "number", "upGood": False}, {"name": "Requested_Volume", "label": "Requested volume", "format": "currency", "upGood": True}],
        "target": {"kpi": "Pull_Through_Rate", "value": 0.7}, "persona": "Loan operations manager", "domain": "Lending Insights", "modelLabel": "Cumulus Lending", "slack": "loan-ops"},
}
LOB_LOOK = {  # (title, accent, header from, header to, page bg)
    "Cumulus_Asset_Management": ("Institutional Client Service Console", "#0F766E", "#2B2A26", "#D97706", "#F7F4EE"),
    "Cumulus_Insurance": ("Claims Service Console", "#7C3AED", "#2E1065", "#DB2777", "#F5F0FB"),
    "Cumulus_Commercial": ("Relationship Desk Console", "#2563EB", "#1E3A8A", "#F59E0B", "#F0F3F8"),
    "Cumulus_Advisors": ("Advisor Team Console", "#15803D", "#14532D", "#7E22CE", "#F2F6F1"),
    "Cumulus_Lending": ("Loan Operations Console", "#0891B2", "#0E4A5C", "#C026D3", "#EEF6F8"),
}
APP_IDS = {"Cumulus_Asset_Management": "1zAKh000000wkBkMAI", "Cumulus_Insurance": "1zAKh000000wkBaMAI", "Cumulus_Commercial": "1zAKh000000wkBfMAI", "Cumulus_Advisors": "1zAKh000000wkBuMAI", "Cumulus_Lending": "1zAKh000000wkBpMAI"}
CONSOLES = [
    ("Cumulus_Retail_Banking", "1zAKh000000wkBzMAI", "Cumulus_Retail_RVP_Console", "Cumulus Retail RVP Console", "cumulusRetailConsole",
     {"title": "RVP – Retail Sales Performance", "accentColor": "#0F766E"}, "#F5F7FA"),
    ("Cumulus_Wealth", "1zAKh000000wkC4MAI", "Cumulus_Wealth_Advisor_Console", "Cumulus Wealth Advisor Console", "cumulusWealthConsole",
     {"title": "Wealth Performance", "accentColor": "#1D4ED8"}, "#EEF2FF"),
] + [(t, APP_IDS[t], f"{t}_Console", LOB_LOOK[t][0], "cumulusLobConsole",
      {"title": LOB_LOOK[t][0], "accentColor": LOB_LOOK[t][1], "headerFrom": LOB_LOOK[t][2], "headerTo": LOB_LOOK[t][3], "config": json.dumps(LOB_CONFIGS[t])}, LOB_LOOK[t][4]) for t in LOB_CONFIGS]


def dashboard(tname, dname, label, comp, props, bg):
    p = dict(props); p["sdmName"] = {"apiName": f"${{App.SemanticModels.{tname}_SDM.Name}}", "id": f"${{App.SemanticModels.{tname}_SDM.Id}}", "label": tname.replace("_", " ") + " Model"}
    w = {"actions": [], "name": "console", "label": comp, "parameters": {"fullyQualifiedName": f"c:{comp}", "properties": p,
         "widgetStyle": {"backgroundColor": bg, "borderColor": bg, "borderEdges": [], "borderRadius": 16, "borderWidth": 0}},
         "source": {"name": f"c:{comp}", "namespace": "c", "type": "LightningWebComponent"}, "type": "extension"}
    return {"name": dname, "label": label + " ${Variables.LabelSuffix}", "description": f"{label} — full-page console extension with AI-driven insights and actions.",
            "customConfig": {"queryCacheEnabled": True, "queryCacheStaleness": "30min"},
            "layouts": [{"columnCount": 96, "maxWidth": 1800, "name": "default", "pages": [{"label": "Console", "name": "console", "widgets": [{"name": "console", "column": 0, "row": 0, "colspan": 96, "rowspan": 150}]}], "rowHeight": 10,
                         "style": {"backgroundColor": bg, "cellSpacingX": 0, "cellSpacingY": 0, "gutterColor": bg}}],
            "style": {"widgetStyle": {"backgroundColor": bg, "borderColor": bg, "borderEdges": [], "borderRadius": 16, "borderWidth": 0}},
            "widgets": {"console": w}, "workspaceIdOrApiName": f"${{App.Workspaces.{tname}_WS.Name}}"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--org", required=True); a = ap.parse_args()
    existing = {}
    off = 0
    while True:
        page = sf_rest(a.org, f"/tableau/dashboards?pageSize=100&offset={off}").get("dashboards", []); existing.update({d["name"]: d["id"] for d in page})
        if len(page) < 100: break
        off += 100
    for tname, app_id, dname, label, comp, props, bg in CONSOLES:
        d = dashboard(tname, dname, label, comp, props, bg)
        json.dump(d, open(os.path.join(TPL, tname, "dashboards", f"{dname}.json"), "w"), indent=2)
        tok = app_tokens(a.org, app_id, tname); tok["${Variables.LabelSuffix}"] = ""
        s = json.dumps(d)
        for k, v in tok.items(): s = s.replace(k, v)
        live = json.loads(s); live["label"] = live["label"].strip(); live["workspaceIdOrApiName"] = tok[f"${{App.Workspaces.{tname}_WS.Name}}"]
        r = sf_rest(a.org, f"/tableau/dashboards/{existing[dname]}", "PATCH", live) if dname in existing else sf_rest(a.org, "/tableau/dashboards", "POST", live)
        if not isinstance(r, dict) or not r.get("id"): sys.exit(f"{dname} failed: {json.dumps(r)[:800]}")
        print(f"  dashboard {dname} {r['id']}  → /tableau/dashboard/{r['name']}/view")


if __name__ == "__main__":
    main()
