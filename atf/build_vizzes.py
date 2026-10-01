#!/usr/bin/env python3
"""
Generate Tableau Next visualizations + a dashboard for each Cumulus ATF template.

Writes force-app/main/default/appTemplates/<T>/visualizations/*.json and dashboards/<T>_Overview.json,
bound to the template's semantic model through ${App.SemanticModels.<T>_SDM.*} tokens.
Re-run atf/build_templates.py afterwards so create-chain.json picks the files up.

Viz kinds (shapes mirror charts retrieved from a live org + the ATF reference templates):
  kpi(measure)                      big number   (Text mark)
  bar(dim, measure[, color])        horizontal bars, sorted desc
  col(dim, measure[, color])        vertical bars
  line(time_dim, measure[, color])  trend
  donut(dim, measure)               share

Field refs: "Object.Field" = table field, "calc:Name" = calculated measure (UserAgg).
Usage: python3 atf/build_vizzes.py [--lob retail_banking,...]
"""
import argparse
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TPL = os.path.join(ROOT, "force-app", "main", "default", "appTemplates")

FONTS = {k: {"color": "#2E2E2E", "size": 13} for k in ("axisTickLabels", "fieldLabels", "headers", "legendLabels", "markLabels", "marks")}
FONTS["actionableHeaders"] = {"color": "#0250D9", "size": 13}
NUMFMT = {"decimalPlaces": 1, "displayUnits": "Auto", "includeThousandSeparator": True, "negativeValuesFormat": "Auto", "prefix": "", "suffix": "", "type": "NumberShort"}


def label_of(name):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ")
    return s.replace("Pct", "%").replace("Id", "ID").replace("A U M", "AUM").replace("C S A T", "CSAT")


def field(ref, role, function=None, label=None):
    if ref.startswith("calc:"):
        f = {"displayCategory": "Continuous", "fieldName": ref[5:], "function": "UserAgg", "role": "Measure", "type": "Field", "label": label or label_of(ref[5:])}
    else:
        obj, name = ref.split(".", 1)
        f = {"fieldName": name, "objectName": obj, "role": role, "type": "Field", "label": label or label_of(name),
             "displayCategory": "Continuous" if role == "Measure" else "Discrete"}
        if role == "Measure":
            f["function"] = function or "Sum"
    return f


def base_style(axis_keys=(), pane_keys=(), header_keys=()):
    """Mirrors the v67 style block of a chart retrieved from a live org (CSI_NPS_Trend)."""
    fmt = lambda t: {"defaults": {"format": {"numberFormatInfo": dict(NUMFMT, type=t)}}}
    return {"axis": {"fields": {k: {"isVisible": True, "isZeroLineVisible": True, "range": {"includeZero": True, "type": "Auto"}, "scale": {"format": {"numberFormatInfo": NUMFMT}},
                                    "ticks": {"majorTicks": {"type": "Auto"}, "minorTicks": {"type": "Auto"}}} for k in axis_keys}},
            "encodings": {"fields": {k: fmt("Number") for k in pane_keys}},
            "fieldLabels": {"columns": {"showDividerLine": False, "showLabels": True}, "rows": {"showDividerLine": False, "showLabels": True}},
            "fit": "Entire", "fonts": FONTS,
            "headers": {"columns": {"mergeRepeatedCells": True, "showIndex": False}, "fields": {k: {"hiddenValues": [], "isVisible": True, "showMissingValues": False} for k in header_keys},
                        "rows": {"mergeRepeatedCells": True, "showIndex": False}},
            "lines": {"axisLine": {"color": "#C9C9C9"}, "fieldLabelDividerLine": {"color": "#C9C9C9"}, "separatorLine": {"color": "#C9C9C9"}, "zeroLine": {"color": "#E5E5E5"}},
            "marks": {"fields": {}, "headers": {"color": {"color": ""}, "isAutomaticSize": True, "label": {"canOverlapLabels": False, "marksToLabel": {"type": "All"}, "showMarkLabels": False}, "range": {"reverse": True}, "size": {"isAutomatic": True, "type": "Pixel", "value": 13}},
                      "panes": {"color": {"color": "#0B5CAB"}, "isAutomaticSize": True, "label": {"canOverlapLabels": False, "marksToLabel": {"type": "All"}, "showMarkLabels": True}, "range": {"reverse": False}, "size": {"isAutomatic": True, "type": "Percentage", "value": 75}}},
            "referenceLines": {}, "shading": {"backgroundColor": "#FFFFFF", "banding": {}}, "showDataPlaceholder": False, "title": {"isVisible": True}}


def viz(tname, name, label, fields, rows, cols, mark, encodings=(), stacked=False, sort_desc_by=None, style=None):
    ws = f"{tname}_WS"
    return {"label": label, "name": name,
            "dataSource": {"name": f"${{App.SemanticModels.{tname}_SDM.Name}}", "id": f"${{App.SemanticModels.{tname}_SDM.Id}}", "type": "SemanticModel"},
            "fields": fields, "interactions": [],
            "view": {"label": "default", "name": f"{name}_default", "viewSpecification": {
                     "sortOrders": {"columns": [], "rows": [], "fields": ({sort_desc_by[0]: {"type": "Nested", "order": "Descending", "byField": sort_desc_by[1]}} if sort_desc_by else {})}}},
            "visualSpecification": {"columns": cols, "forecasts": {}, "layout": "Vizql", "legends": {},
                                    "marks": {"fields": {}, "headers": {"encodings": [], "isAutomatic": True, "stack": {"isAutomatic": True, "isStacked": False}, "type": "Text"},
                                              "panes": {"encodings": list(encodings), "isAutomatic": not encodings, "stack": {"isAutomatic": not stacked, "isStacked": stacked}, "type": mark}},
                                    "measureValues": [], "referenceLines": {}, "rows": rows, "style": style or base_style()},
            "workspace": {"label": tname.replace("_", " "), "name": f"${{App.Workspaces.{ws}.Name}}"}}


def kpi(t, name, label, measure, fn=None):
    f = {"F1": field(measure, "Measure", fn, label)}
    f["F1"]["displayCategory"] = "Discrete"
    st = base_style(pane_keys=("F1",), header_keys=("F1",))
    st["fonts"] = dict(FONTS, marks={"color": "#032D60", "size": 16})
    return viz(t, name, label, f, [], ["F1"], "Text", style=st)


def bar(t, name, label, dim, measure, fn=None, color=None, horizontal=True, stacked=False, top=None):
    f = {"F1": field(dim, "Dimension"), "F2": field(measure, "Measure", fn)}
    enc = []
    if color:
        f["F3"] = field(color, "Dimension"); enc.append({"fieldKey": "F3", "type": "Color"})
    rows, cols = (["F1"], ["F2"]) if horizontal else (["F2"], ["F1"])
    st = base_style(axis_keys=("F2",), pane_keys=("F2",), header_keys=("F1",))
    v = viz(t, name, label, f, rows, cols, "Bar", enc, stacked=bool(color) or stacked, sort_desc_by=("F1", "F2"), style=st)
    # (a top-N `rowLimit` is rejected by the create API in v67 — sort descending and keep the widget tall instead)
    return v


def line(t, name, label, time_dim, measure, fn=None, color=None, second=None):
    """Line over time. `second` adds a second measure as its own pane (one axis each, never dual-axis)."""
    f = {"F1": field(time_dim, "Dimension"), "F2": field(measure, "Measure", fn)}
    rows, enc = ["F2"], []
    if second:
        m2, fn2 = split_fn(second)
        f["F4"] = field(m2, "Measure", fn2); rows.append("F4")
    if color:
        f["F3"] = field(color, "Dimension"); enc.append({"fieldKey": "F3", "type": "Color"})
    st = base_style(axis_keys=tuple(rows), pane_keys=tuple(rows), header_keys=("F1",))
    st["marks"]["panes"]["label"]["showMarkLabels"] = False  # a number on every point is noise on a 24-month line
    # mirror a UI-built line viz (Sessions_Trend_Analysis): pixel size, automatic — a non-automatic size makes the viz unrenderable
    st["marks"]["panes"]["size"] = {"isAutomatic": True, "type": "Pixel", "value": 3}
    return viz(t, name, label, f, rows, ["F1"], "Line", enc, style=st)


def donut(t, name, label, dim, measure, fn=None):
    f = {"F1": field(measure, "Measure", fn), "F2": field(dim, "Dimension"), "F3": field(dim, "Dimension")}
    enc = [{"fieldKey": "F1", "type": "Angle"}, {"fieldKey": "F2", "type": "Color"}, {"fieldKey": "F3", "type": "Label"}]
    return viz(t, name, label, f, [], [], "Donut", enc, style=base_style(pane_keys=("F1",)))


# ---------------------------------------------------------------------------------
# Per-LOB dashboards: 4 KPIs across the top, then charts on a 36-column grid.
# ---------------------------------------------------------------------------------
SPECS = {
    "Cumulus_Retail_Banking": {
        "title": "Service Command Center", "subtitle": "Branch service manager view — cases, resolution, satisfaction, cross-sell",
        "filters": [("RB_Service_Cases.Region", "Region"), ("RB_Service_Cases.Channel", "Channel")],
        "kpis": [],
        # KPI band as cumulusKpiTile extensions: (widget, title, measure(name, agg, label), colour, sentiment, format, target, trend dimension)
        "kpi_tiles": [("cases", "Service Cases", ("Case_Count", "UserAgg", "Service Cases"), "#0B5CAB", "UpIsBad", "number", "", "RB_Service_Cases.CreatedMonth"),
                      ("fcr", "First-Contact Resolution", ("FCR_Rate", "UserAgg", "FCR Rate"), "#1BAF7A", "UpIsGood", "percent", "0.75", "RB_Service_Cases.CreatedMonth"),
                      ("aht", "Avg Handle Time (min)", ("Avg_Handle_Time", "UserAgg", "Avg Handle Time"), "#EDA100", "UpIsBad", "number", "15", "RB_Service_Cases.CreatedMonth"),
                      ("csat", "Avg CSAT", ("Avg_CSAT", "UserAgg", "Avg CSAT"), "#EB6834", "UpIsGood", "number", "3.5", "RB_Service_Cases.CreatedMonth")],
        "charts": [("line", "RB_Disputes_Trend", "Card Dispute Cases by Month", "RB_Service_Cases.CreatedMonth", "calc:Card_Dispute_Cases", None),
                   ("line", "RB_Cases_Trend", "All Service Cases by Month", "RB_Service_Cases.CreatedMonth", "calc:Case_Count", None),
                   ("bartop", "RB_Disputes_By_Branch", "Card Dispute Cases by Branch (top 10)", "RB_Service_Cases.BranchName", "calc:Card_Dispute_Cases", 10),
                   ("bar", "RB_Cases_By_Channel", "Cases by Channel", "RB_Service_Cases.Channel", "calc:Case_Count", None),
                   ("bar", "RB_CSAT_By_Type", "Avg CSAT by Case Type", "RB_Service_Cases.CaseType", "RB_Service_Cases.CSAT|Avg", None),
                   ("bar", "RB_AHT_By_Agentforce", "Handle Time: Agentforce vs Human", "RB_Service_Cases.AgentforceHandled", "RB_Service_Cases.HandleTimeMinutes|Avg", None),
                   ("donut", "RB_Deposits_By_Segment", "Deposits by Segment", "RB_Financial_Accounts.Segment", "RB_Financial_Accounts.Balance")],
    },
    "Cumulus_Wealth": {
        "kpis": [("WM_KPI_AUM", "Total AUM", "calc:Total_AUM"), ("WM_KPI_NNA", "Net New Assets", "calc:Net_New_Assets"),
                 ("WM_KPI_Households", "Households", "calc:Household_Count"), ("WM_KPI_Interactions", "Interactions per Household", "calc:Interactions_Per_Household")],
        "charts": [("line", "WM_Net_Flows_Trend", "Net Flows by Month", "WM_Net_Flows.FlowMonth", "WM_Net_Flows.NetFlow", None),
                   ("bar", "WM_AUM_By_Advisor", "AUM by Advisor", "WM_Households.AdvisorName", "WM_Households.AUM", "WM_Households.ServiceTier"),
                   ("bar", "WM_Interactions_Churn", "Interactions per Household: Churned vs Retained", "WM_Households.Churned", "WM_Households.InteractionCount|Avg", None),
                   ("donut", "WM_Allocation", "Asset Allocation", "WM_Holdings.AssetClass", "WM_Holdings.MarketValue"),
                   ("bar", "WM_Goals_Status", "Goals by Status and Type", "WM_Goals.GoalType", "WM_Goals.TargetValue|Count", "WM_Goals.Status")],
    },
    "Cumulus_Asset_Management": {
        "kpis": [("AM_KPI_AUM", "Total AUM", "calc:Total_AUM"), ("AM_KPI_Requests", "Service Requests", "calc:Request_Count"),
                 ("AM_KPI_Cycle", "Avg Cycle Time (days)", "calc:Avg_Cycle_Time"), ("AM_KPI_Pipeline", "Pipeline Amount", "calc:Pipeline_Amount")],
        "charts": [("line", "AM_Flows_Trend", "Net Flows by Month and Strategy", "AM_Mandate_Flows.FlowMonth", "AM_Mandate_Flows.NetFlow", "AM_Mandate_Flows.Strategy"),
                   ("bar", "AM_Cycle_By_Type", "Cycle Time by Request Type: Quarter-End vs Normal", "AM_Service_Requests.RequestType", "AM_Service_Requests.CycleTimeDays|Avg", "AM_Service_Requests.IsQuarterEnd"),
                   ("bar", "AM_SLA_Breaches", "SLA Breaches by Request Type", "AM_Service_Requests.RequestType", "calc:Request_Count", "AM_Service_Requests.SLABreached"),
                   ("bar", "AM_Pipeline_By_Stage", "Pipeline by Stage", "AM_Deals.Stage", "AM_Deals.Amount", None),
                   ("donut", "AM_AUM_By_Strategy", "AUM by Strategy", "AM_Mandates.Strategy", "AM_Mandates.AUM")],
    },
    "Cumulus_Insurance": {
        "kpis": [("INS_KPI_Claims", "Claims", "calc:Claim_Count"), ("INS_KPI_Loss_Ratio", "Loss Ratio", "calc:Loss_Ratio"),
                 ("INS_KPI_Cycle", "Avg Claim Cycle Time (days)", "calc:Avg_Claim_Cycle_Time"), ("INS_KPI_Premium", "Written Premium", "calc:Written_Premium")],
        "charts": [("line", "INS_Claims_Trend", "Claims by Loss Month and Type", "INS_Claims.LossMonth", "calc:Claim_Count", "INS_Claims.ClaimType"),
                   ("bar", "INS_Cycle_By_CAT", "Cycle Time: Catastrophe vs Normal by State", "INS_Claims.State", "INS_Claims.CycleTimeDays|Avg", "INS_Claims.IsCatastrophe"),
                   ("bar", "INS_Loss_Ratio_By_LOB", "Loss Ratio by Line of Business", "INS_Policies.LineOfBusiness", "calc:Loss_Ratio", None),
                   ("donut", "INS_Claims_By_Status", "Open Claims by Status", "INS_Claims.Status", "calc:Claim_Count"),
                   ("bar", "INS_Renewals_By_Producer", "Policies by Producer Type and Status", "INS_Policies.ProducerType", "INS_Policies.AnnualPremium|Count", "INS_Policies.Status"),
                   ("bar", "INS_Cases_Agentforce", "Claim Cases: Agentforce vs Human (CSAT)", "INS_Claim_Cases.AgentforceHandled", "INS_Claim_Cases.CSAT|Avg", None)],
    },
    "Cumulus_Commercial": {
        "kpis": [("CB_KPI_Pipeline", "Pipeline Amount", "calc:Pipeline_Amount"), ("CB_KPI_Commitments", "Total Commitments", "calc:Total_Commitments"),
                 ("CB_KPI_Util", "Avg Utilization %", "calc:Avg_Utilization"), ("CB_KPI_Onboarding", "Avg Onboarding Days", "calc:Avg_Onboarding_Days")],
        "charts": [("bar", "CB_Pipeline_By_Stage", "Pipeline by Stage and Product", "CB_Deals.Stage", "CB_Deals.Amount", "CB_Deals.Product"),
                   ("bar", "CB_Onboarding_Treasury", "Onboarding Days: With vs Without Treasury", "CB_Onboarding.OnboardingType", "CB_Onboarding.CycleTimeDays|Avg", "CB_Onboarding.HasTreasuryProducts"),
                   ("bar", "CB_Utilization_By_Rating", "Utilization by Risk Rating", "CB_Credit_Facilities.RiskRating", "CB_Credit_Facilities.UtilizationPct|Avg", "CB_Credit_Facilities.OverCovenant"),
                   ("donut", "CB_Treasury_Penetration", "Accounts by Treasury Product Count", "CB_Business_Accounts.TreasuryProductCount", "CB_Business_Accounts.AnnualRevenue|Count"),
                   ("bar", "CB_Cases_By_Type", "Service Cases by Type", "CB_Service_Cases.CaseType", "CB_Service_Cases.HandleTimeMinutes|Count", None)],
    },
    "Cumulus_Advisors": {
        "kpis": [("FA_KPI_AUM", "Book AUM", "calc:Book_AUM"), ("FA_KPI_Activities", "Activities", "calc:Activities"),
                 ("FA_KPI_Life_Events", "Life Events", "calc:Life_Events"), ("FA_KPI_Opportunity", "Life Event Opportunity", "calc:Life_Event_Opportunity")],
        "charts": [("bar", "FA_Life_Events_Followup", "Life Events: Follow-up Within 14 Days", "FA_Life_Events.EventType", "calc:Life_Events", "FA_Life_Events.FollowUpWithin14Days"),
                   ("bar", "FA_Book_By_Stage", "Book AUM by Life Stage and Risk", "FA_Book_Of_Business.LifeStage", "FA_Book_Of_Business.AUM", "FA_Book_Of_Business.RiskProfile"),
                   ("bar", "FA_Activities_By_Advisor", "Activities by Advisor", "FA_Activities.AdvisorName", "calc:Activities", "FA_Activities.ActivityType"),
                   ("donut", "FA_Referral_Funnel", "Referrals by Status", "FA_Referrals.Status", "calc:Referral_Count"),
                   ("bar", "FA_Life_Events_Source", "Life Events by Detection Source", "FA_Life_Events.DetectedSource", "FA_Life_Events.OpportunityValue", None)],
    },
    "Cumulus_Lending": {
        "kpis": [("LN_KPI_Apps", "Applications", "calc:Applications"), ("LN_KPI_Volume", "Requested Volume", "calc:Requested_Volume"),
                 ("LN_KPI_TTC", "Avg Time to Close (days)", "calc:Avg_Time_To_Close"), ("LN_KPI_Stage", "Avg Days in Stage", "calc:Avg_Days_In_Stage")],
        "charts": [("line", "LN_Apps_Trend", "Applications by Month and Channel", "LN_Applications.SubmittedMonth", "calc:Applications", "LN_Applications.Channel"),
                   ("bar", "LN_Days_By_Stage", "Avg Days in Stage", "LN_Stage_Events.StageName", "LN_Stage_Events.DaysInStage|Avg", None),
                   ("bar", "LN_Status_By_Channel", "Applications by Channel and Status", "LN_Applications.Channel", "calc:Applications", "LN_Applications.Status"),
                   ("donut", "LN_Volume_By_Product", "Requested Volume by Product", "LN_Applications.ProductName", "LN_Applications.RequestedAmount"),
                   ("bar", "LN_LO_Leaderboard", "Funded Volume by Loan Officer", "LN_Applications.LoanOfficerName", "LN_Applications.RequestedAmount", "LN_Applications.IsFunded")],
    },
}


# ---------------------------------------------------------------------------------
# LWC dashboard-extension widgets per LOB (components in force-app/main/default/lwc)
# props use the same shapes the widget panel writes; the model binds through tokens.
# ---------------------------------------------------------------------------------
def SDM(t):
    return {"apiName": f"${{App.SemanticModels.{t}_SDM.Name}}", "id": f"${{App.SemanticModels.{t}_SDM.Id}}", "label": t.replace("_", " ") + " Model"}


def measure(name, agg, label):
    return {"name": name, "aggregation": agg, "label": label}


def dimension(name, label):
    return {"name": name, "label": label}


EXTENSIONS = {
    "Cumulus_Retail_Banking": [("banner", "cumulusThresholdBanner", 3, {"measureField": measure("Avg_CSAT", "UserAgg", "Avg CSAT"), "threshold": "3.5", "belowIsBad": True, "alertMessage": "CSAT below the 3.5 target — Card Dispute cases score lowest",
                                "okMessage": "CSAT at or above target", "format": "number", "focusDimension": dimension("RB_Service_Cases.CaseType", "Case Type"), "focusValue": "Card Dispute"}),
                               ("nba", "cumulusNextBestActions", 12, {"entityField": dimension("RB_Households.HouseholdName", "Household Name"), "contextField": dimension("RB_Households.Segment", "Segment"),
                                "scoreField": measure("RB_Households.ProductCount", "Avg", "Product Count"), "title": "Cross-sell: fewest products", "actionLabel": "Call", "lowestFirst": True, "topN": 8})],
    "Cumulus_Wealth": [("kpi", "cumulusKpiTile", 4, {"measureField": measure("Total_AUM", "UserAgg", "Total AUM"), "title": "AUM vs Target", "target": "1500000000", "sentiment": "UpIsGood", "format": "currency"})],
    "Cumulus_Asset_Management": [("bars", "cumulusRankedBars", 10, {"dimensionField": dimension("AM_Mandate_Flows.ClientName", "Client Name"), "measureField": measure("AM_Mandate_Flows.NetFlow", "Sum", "Net Flow"),
                                  "title": "Net flows by client (click to filter)", "topN": 10, "format": "currency"})],
    "Cumulus_Insurance": [("banner", "cumulusThresholdBanner", 3, {"measureField": measure("Loss_Ratio", "UserAgg", "Loss Ratio"), "threshold": "0.6", "alertMessage": "Loss ratio above 60% — review pricing and claims handling",
                           "okMessage": "Loss ratio within target", "format": "percent", "focusDimension": dimension("INS_Policies.LineOfBusiness", "Line Of Business"), "focusValue": "Renters"})],
    "Cumulus_Commercial": [("kpi", "cumulusKpiTile", 4, {"measureField": measure("CB_Credit_Facilities.UtilizationPct", "Avg", "Utilization %"), "title": "Avg Utilization vs Covenant", "target": "80", "sentiment": "UpIsBad", "format": "number"})],
    "Cumulus_Advisors": [("nba", "cumulusNextBestActions", 12, {"entityField": dimension("FA_Life_Events.HouseholdName", "Household Name"), "contextField": dimension("FA_Life_Events.EventType", "Event Type"),
                          "scoreField": measure("FA_Life_Events.OpportunityValue", "Sum", "Opportunity Value"), "title": "Life events to follow up", "actionLabel": "Schedule", "lowestFirst": False, "topN": 8, "format": "currency"})],
    "Cumulus_Lending": [("banner", "cumulusThresholdBanner", 3, {"measureField": measure("Avg_Time_To_Close", "UserAgg", "Avg Time to Close"), "threshold": "30", "alertMessage": "Time to close above 30 days — document collection is the bottleneck",
                         "okMessage": "Time to close within target", "format": "number", "focusDimension": dimension("LN_Applications.Channel", "Channel"), "focusValue": "Branch"})],
}


def ext_widget(tname, wname, comp, props):
    p = dict(props); p["sdmName"] = SDM(tname)
    return {"actions": [], "name": wname, "label": comp, "parameters": {"fullyQualifiedName": f"c:{comp}", "properties": p,
            "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#E5E5E5", "borderEdges": [], "borderRadius": 8, "borderWidth": 1}},
            "source": {"name": f"c:{comp}", "namespace": "c", "type": "LightningWebComponent"}, "type": "extension"}


def split_fn(ref):
    if "|" in ref:
        r, fn = ref.split("|")
        return r, fn
    return ref, None


def build(tname):
    spec = SPECS[tname]
    out = os.path.join(TPL, tname)
    vdir, ddir = os.path.join(out, "visualizations"), os.path.join(out, "dashboards")
    for d in (vdir, ddir):
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
    names = []
    for (n, lab, m) in spec["kpis"]:
        m, fn = split_fn(m)
        json.dump(kpi(tname, n, lab, m, fn), open(os.path.join(vdir, n + ".json"), "w"), indent=2); names.append(n)
    for c in spec["charts"]:
        kind, n, lab, dim, m = c[:5]
        color = c[5] if len(c) > 5 else None
        m, fn = split_fn(m)
        v = {"line": lambda: line(tname, n, lab, dim, m, fn, color), "bar": lambda: bar(tname, n, lab, dim, m, fn, color),
             "line2": lambda: line(tname, n, lab, dim, m, fn, None, second=color), "bartop": lambda: bar(tname, n, lab, dim, m, fn, None, top=color),
             "col": lambda: bar(tname, n, lab, dim, m, fn, color, horizontal=False), "donut": lambda: donut(tname, n, lab, dim, m, fn)}[kind]()
        json.dump(v, open(os.path.join(vdir, n + ".json"), "w"), indent=2); names.append(n)
    # Dashboard on the 96-column, 0-indexed grid Tableau Next uses (rowHeight 10px):
    #   title + filters | alert banner (extension) | 4 KPIs | list/tile extension + trend | charts, 3 per band
    W = 96
    widgets, layout = {}, []
    def vis(n, extra=None):
        w = {"actions": [], "name": f"w_{n}", "parameters": {"legendPosition": "Bottom", "receiveFilterSource": {"filterMode": "all", "widgetIds": []},
                                                                "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#D9E1EC", "borderEdges": [], "borderRadius": 12, "borderWidth": 1}},
             "source": {"id": f"${{App.Visualizations.{n}.Id}}", "name": f"${{App.Visualizations.{n}.Name}}"}, "type": "visualization"}
        if extra:
            w["parameters"].update(extra)
        widgets[w["name"]] = w
        return w["name"]
    def place(name, col, row, colspan, rowspan):
        layout.append({"name": name, "column": col, "row": row, "colspan": colspan, "rowspan": rowspan})
    row = 0
    # header band: title text + filters
    title = spec.get("title", f"{tname.replace('_', ' ')} Overview"); sub = spec.get("subtitle", "")
    widgets["hdr"] = {"actions": [], "name": "hdr", "type": "text", "parameters": {"conditionalFormattingRules": [], "receiveFilterSource": {"filterMode": "all", "widgetIds": []},
                      "content": [{"attributes": {"color": "#032D60", "size": "22px", "bold": True}, "insert": title, "rules": []}, {"attributes": {"align": "left"}, "insert": "\n", "rules": []},
                                  {"attributes": {"color": "#5C6B82", "size": "13px"}, "insert": sub, "rules": []}, {"attributes": {"align": "left"}, "insert": "\n", "rules": []}]}}
    filters = spec.get("filters", [])
    fw = 16
    place("hdr", 0, row, W - fw * len(filters), 5)
    for i, (ref, lab) in enumerate(filters):
        obj, fld = ref.split(".", 1)
        wn = f"flt_{fld}"
        widgets[wn] = {"actions": [], "label": lab, "name": wn, "type": "filter", "source": {"name": SDM(tname)["apiName"], "id": SDM(tname)["id"]},
                       "parameters": {"filterOption": {"dataType": "Text", "fieldName": fld, "objectName": obj, "selectionType": "multiple"}, "isLabelHidden": False,
                                      "receiveFilterSource": {"filterMode": "all", "widgetIds": []}, "viewType": "list",
                                      "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#D9E1EC", "borderEdges": [], "borderRadius": 12, "borderWidth": 1}}}
        place(wn, W - fw * (len(filters) - i), row, fw, 5)
    row += 5
    exts = EXTENSIONS.get(tname, [])
    banners = [e for e in exts if e[1] == "cumulusThresholdBanner"]
    sides = [e for e in exts if e[1] != "cumulusThresholdBanner"]
    for wname, comp, height, props in banners:
        widgets[f"x_{wname}"] = ext_widget(tname, f"x_{wname}", comp, props)
        place(f"x_{wname}", 0, row, W, 5); row += 5
    # KPI band: cumulusKpiTile extensions (big number, colour, sparkline, delta) or plain Text vizzes
    tiles = spec.get("kpi_tiles", [])
    if tiles:
        kw = W // len(tiles)
        for i, (wn, title, (mname, magg, mlab), colour, sent, fmt, target, trend) in enumerate(tiles):
            props = {"measureField": measure(mname, magg, mlab), "title": title, "accentColor": colour, "sentiment": sent, "format": fmt, "target": target}
            if trend:
                props["trendDimension"] = dimension(trend, label_of(trend.split(".")[-1]))
            widgets[f"k_{wn}"] = ext_widget(tname, f"k_{wn}", "cumulusKpiTile", props)
            place(f"k_{wn}", i * kw, row, kw, 14)
        row += 14
    elif spec["kpis"]:
        kw = W // len(spec["kpis"])
        for i, (n, _, _) in enumerate(spec["kpis"]):
            place(vis(n), i * kw, row, kw, 9)
        row += 9
    # trend band: side extension (left third) + first chart
    charts = list(spec["charts"])
    first = charts.pop(0)[1]
    if sides:
        wname, comp, height, props = sides[0]
        widgets[f"x_{wname}"] = ext_widget(tname, f"x_{wname}", comp, props)
        place(f"x_{wname}", 0, row, 28, 34)
        place(vis(first), 28, row, W - 28, 34)
    else:
        place(vis(first), 0, row, W, 30)
    row += 34 if sides else 30
    # remaining charts, three per band
    per = 3
    for j, c in enumerate(charts):
        cw = W // per
        place(vis(c[1]), (j % per) * cw, row + (j // per) * 28, cw, 28)
    dash = {"name": f"{tname}_Overview", "label": f"{tname.replace('_', ' ')} Overview ${{Variables.LabelSuffix}}",
            "description": f"{tname.replace('_', ' ')} — service and business KPIs for the Cumulus Financial Group demo.",
            "customConfig": {"queryCacheEnabled": True, "queryCacheStaleness": "30min"},
            "layouts": [{"columnCount": W, "maxWidth": 1600, "name": "default", "pages": [{"label": "Overview", "name": "overview", "widgets": layout}], "rowHeight": 10,
                         "style": {"backgroundColor": "#EEF2F7", "cellSpacingX": 12, "cellSpacingY": 12, "gutterColor": "#EEF2F7"}}],
            "style": {"widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#D9E1EC", "borderEdges": [], "borderRadius": 12, "borderWidth": 1}},
            "widgets": widgets, "workspaceIdOrApiName": f"${{App.Workspaces.{tname}_WS.Name}}"}
    json.dump(dash, open(os.path.join(ddir, f"{tname}_Overview.json"), "w"), indent=2)
    print(f"{tname:28s} {len(names)} vizzes, 1 dashboard")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", help="comma-separated template names (default all)")
    a = ap.parse_args()
    for t in (a.template.split(",") if a.template else SPECS):
        build(t)


if __name__ == "__main__":
    main()
