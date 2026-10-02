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
    if ref.startswith("dim:"):  # calculated dimension (model-level, no object)
        return {"displayCategory": "Discrete", "fieldName": ref[4:], "role": "Dimension", "type": "Field", "label": label or label_of(ref[4:])}
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
            "fieldLabels": {"columns": {"showDividerLine": False, "showLabels": False}, "rows": {"showDividerLine": False, "showLabels": False}},
            "fit": "Entire", "fonts": FONTS,
            "headers": {"columns": {"mergeRepeatedCells": True, "showIndex": False}, "fields": {k: {"hiddenValues": [], "isVisible": True, "showMissingValues": False} for k in header_keys},
                        "rows": {"mergeRepeatedCells": True, "showIndex": False}},
            "lines": {"axisLine": {"color": "#C9C9C9"}, "fieldLabelDividerLine": {"color": "#C9C9C9"}, "separatorLine": {"color": "#C9C9C9"}, "zeroLine": {"color": "#E5E5E5"}},
            "marks": {"fields": {}, "headers": {"color": {"color": ""}, "isAutomaticSize": True, "label": {"canOverlapLabels": False, "marksToLabel": {"type": "All"}, "showMarkLabels": False}, "range": {"reverse": True}, "size": {"isAutomatic": True, "type": "Pixel", "value": 13}},
                      "panes": {"color": {"color": "#0B5CAB"}, "isAutomaticSize": True, "label": {"canOverlapLabels": False, "marksToLabel": {"type": "All"}, "showMarkLabels": True}, "range": {"reverse": False}, "size": {"isAutomatic": True, "type": "Percentage", "value": 75}}},
            "referenceLines": {}, "shading": {"backgroundColor": "#FFFFFF", "banding": {}}, "showDataPlaceholder": False, "title": {"isVisible": False}}


# Bold, distinct hues for single-series charts (rotated per dashboard so neighbouring charts differ); titles reuse the hue.
PALETTE = ["#0B5CAB", "#7C3AED", "#059669", "#EA580C", "#DB2777", "#0891B2", "#CA8A04"]
CHART_COLOR = {}
# extra distinct hues used once a theme palette is exhausted, so no two single-series charts on a dashboard share a colour
EXTRA_HUES = ["#0F766E", "#B45309", "#BE123C", "#4F46E5", "#65A30D", "#0891B2", "#9333EA", "#EA580C", "#047857", "#1D4ED8", "#A21CAF", "#CA8A04"]


def next_hue(tname, used):
    for h in THEMES.get(tname, {}).get("palette", PALETTE) + EXTRA_HUES:
        if h.upper() not in {u.upper() for u in used}:
            return h
    return PALETTE[len(used) % len(PALETTE)]

# Per-industry visual theme (from deck/design-directions.html). Native widgets only take flat colours + radius, so the
# dark "Midnight / Violet / Console" directions become their light-surface equivalents here; the LWC extensions carry the
# gradients. Keys: page bg, header tile bg + title/subtitle colours, chart palette (also used for chart headlines), map ramp.
THEMES = {
    "Cumulus_Retail_Banking":   {"bg": "#F3F5F9", "hdr": "#E6F0FB", "title": "#0F3D7A", "sub": "#3B5577", "palette": ["#1E9BE8", "#0B5CAB", "#64748B", "#F26B4E", "#1E9BE8", "#0B5CAB"], "map": ("#CFE4FB", "#1E9BE8", "#F26B4E")},
    "Cumulus_Wealth":           {"bg": "#EEF0FB", "hdr": "#E3E5FA", "title": "#2E1F8F", "sub": "#4B4590", "palette": ["#6D5BD0", "#0EA5E9", "#EC4899", "#10B981", "#F59E0B", "#6D5BD0"], "map": ("#E4E1FA", "#EC4899", "#0EA5E9")},
    "Cumulus_Asset_Management": {"bg": "#F7F4EE", "hdr": "#EFEAE0", "title": "#2B2A26", "sub": "#5C5950", "palette": ["#0F766E", "#D97706", "#E11D48", "#2563EB", "#7C3AED", "#0F766E"], "map": ("#D9F0EC", "#E11D48", "#0F766E")},
    "Cumulus_Insurance":        {"bg": "#F5F0FB", "hdr": "#ECE2F8", "title": "#4C1D95", "sub": "#6B4FA3", "palette": ["#7C3AED", "#A855F7", "#DB2777", "#6D28D9", "#C026D3", "#7C3AED"], "map": ("#EDE4FA", "#A855F7", "#F59E0B")},
    "Cumulus_Commercial":       {"bg": "#F0F3F8", "hdr": "#DBEAFE", "title": "#1E3A8A", "sub": "#3B5577", "palette": ["#2563EB", "#EF4444", "#16A34A", "#F59E0B", "#8B5CF6", "#2563EB"], "map": ("#BFDBFE", "#1D4ED8", "#F59E0B")},
    "Cumulus_Advisors":         {"bg": "#F2F6F1", "hdr": "#DDEBDC", "title": "#14532D", "sub": "#3F6B4A", "palette": ["#15803D", "#7E22CE", "#0E7490", "#B45309", "#BE123C", "#15803D"], "map": ("#FDE7CF", "#15803D", "#7E22CE")},
    "Cumulus_Lending":          {"bg": "#EEF6F8", "hdr": "#CFF3F9", "title": "#0E4A5C", "sub": "#2F6E80", "palette": ["#0891B2", "#C026D3", "#0E7490", "#DB2777", "#0891B2", "#C026D3"], "map": ("#CFEFF6", "#0891B2", "#C026D3")},
}

# Map report per LOB (cumulusStateMap extension + a supporting ranked bar to its right):
#   (dimension, shade measure (name, agg, label, format), bubble measure or None, title, subtitle, side chart spec)
MAPS = {
    "Cumulus_Retail_Banking": ("dim:Case_State", ("Case_Count", "UserAgg", "Cases", "number"), ("Card_Dispute_Cases", "UserAgg", "Card Disputes", "number"),
                               "Where is service demand heaviest?", "Shade = cases by state · bubble = card disputes · click a state to filter",
                               ("bar", "RB_FCR_By_State", "FCR by State", "dim:Case_State", "calc:FCR_Rate", None)),
    "Cumulus_Wealth": ("dim:Household_State", ("Churn_Rate", "UserAgg", "Churn Rate", "percent"), ("Total_AUM", "UserAgg", "AUM", "currency"),
                       "Where the book lives — and where it leaks", "Shade = household churn rate · bubble = AUM by state",
                       ("bar", "WM_Churn_By_State", "Churn by State", "dim:Household_State", "calc:Churn_Rate", None)),
    "Cumulus_Asset_Management": ("AM_Service_Requests.Region", ("SLA_Breach_Rate", "UserAgg", "SLA Breach Rate", "percent"), ("Request_Count", "UserAgg", "Requests", "number"),
                                 "Service pressure by region", "US regions shaded by SLA breach rate · bubble = request volume (EMEA / APAC at right)",
                                 ("bar", "AM_Breach_By_Region", "SLA Breach Rate by Region", "AM_Service_Requests.Region", "calc:SLA_Breach_Rate", None)),
    "Cumulus_Insurance": ("INS_Claims.State", ("Loss_Ratio", "UserAgg", "Loss Ratio", "percent"), ("CAT_Claims", "UserAgg", "Catastrophe Claims", "number"),
                          "Loss ratio and catastrophe exposure by state", "Shade = loss ratio · bubble = catastrophe claims",
                          ("bar", "INS_Loss_Ratio_By_State", "Loss Ratio by State", "INS_Claims.State", "calc:Loss_Ratio", None)),
    "Cumulus_Commercial": ("CB_Credit_Facilities.Region", ("Total_Commitments", "UserAgg", "Commitments", "currency"), ("Facility_Count", "UserAgg", "Facilities", "number"),
                           "Credit exposure by region", "Shade = committed exposure · bubble = number of facilities",
                           ("bar", "CB_Utilization_By_Region", "Utilization by Region", "CB_Credit_Facilities.Region", "calc:Avg_Utilization", None)),
    "Cumulus_Advisors": ("dim:Household_State", ("Followup_Rate", "UserAgg", "Follow-up Rate", "percent"), ("Life_Event_Opportunity", "UserAgg", "Opportunity", "currency"),
                         "Life-event opportunity by state", "Shade = follow-up within 14 days · bubble = opportunity value",
                         ("bar", "FA_Opportunity_By_State", "Opportunity by State", "dim:Household_State", "calc:Life_Event_Opportunity", None)),
    "Cumulus_Lending": ("dim:Application_State", ("Pull_Through_Rate", "UserAgg", "Pull-Through Rate", "percent"), ("Applications", "UserAgg", "Applications", "number"),
                        "Pull-through by state", "Shade = share of applications funded · bubble = application volume",
                        ("bar", "LN_Time_To_Close_By_State", "Time to Close by State", "dim:Application_State", "calc:Avg_Time_To_Close", None)),
}


def paint(v, hex_color):
    """Set the single-series mark colour of a viz (no-op for colour-encoded charts, which keep the categorical palette)."""
    enc = v["visualSpecification"]["marks"]["panes"].get("encodings", [])
    if not any(e.get("type") == "Color" for e in enc):
        v["visualSpecification"]["style"]["marks"]["panes"]["color"]["color"] = hex_color
    return v


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
        # chart titles shown as text widgets above each viz (the dashboard does not render a viz's own label)
        "titles": {"RB_Disputes_Trend": ("Card disputes spiked with the Sep 2025 fee change", "Card Dispute cases per month, 24 months"),
                   "RB_Cases_Trend": ("Case volume is steady — the mix is the story", "All service cases per month"),
                   "RB_Disputes_By_Branch": ("Where disputes concentrate", "Card Dispute cases by branch, highest first"),
                   "RB_Cases_By_Channel": ("Voice and chat carry two-thirds of the load", "Cases by channel"),
                   "RB_CSAT_By_Type": ("Disputes drag CSAT below the 3.5 target", "Average CSAT by case type"),
                   "RB_AHT_By_Agentforce": ("Agentforce resolves as fast as human agents", "Average handle time, minutes"),
                   "RB_Deposits_By_Segment": ("Mass Market holds the largest deposit base", "Deposit balances by customer segment"),
                   "RB_Channel_Trend": ("Which channels are growing?", "Cases per month by channel"),
                   "RB_FCR_By_State": ("States below the 75% FCR target", "First-contact resolution by state")},
        "kpis": [],
        # KPI band as cumulusKpiTile extensions: (widget, title, measure(name, agg, label), colour, sentiment, format, target, trend dimension)
        "kpi_tiles": [("cases", "Service Cases", ("Case_Count", "UserAgg", "Service Cases"), "#1E9BE8", "UpIsBad", "number", "", "RB_Service_Cases.CreatedMonth"),
                      ("fcr", "First-Contact Resolution", ("FCR_Rate", "UserAgg", "FCR Rate"), "#0B5CAB", "UpIsGood", "percent", "0.75", "RB_Service_Cases.CreatedMonth"),
                      ("aht", "Avg Handle Time (min)", ("Avg_Handle_Time", "UserAgg", "Avg Handle Time"), "#1E9BE8", "UpIsBad", "number", "15", "RB_Service_Cases.CreatedMonth"),
                      ("csat", "Avg CSAT", ("Avg_CSAT", "UserAgg", "Avg CSAT"), "#0B5CAB", "UpIsGood", "number", "3.5", "RB_Service_Cases.CreatedMonth")],
        "charts": [("line", "RB_Disputes_Trend", "Card Dispute Cases by Month", "RB_Service_Cases.CreatedMonth", "calc:Card_Dispute_Cases", None),
                   ("line", "RB_Cases_Trend", "All Service Cases by Month", "RB_Service_Cases.CreatedMonth", "calc:Case_Count", None),
                   ("bartop", "RB_Disputes_By_Branch", "Card Dispute Cases by Branch (top 10)", "RB_Service_Cases.BranchName", "calc:Card_Dispute_Cases", 10),
                   ("bar", "RB_Cases_By_Channel", "Cases by Channel", "RB_Service_Cases.Channel", "calc:Case_Count", None),
                   ("bar", "RB_CSAT_By_Type", "Avg CSAT by Case Type", "RB_Service_Cases.CaseType", "RB_Service_Cases.CSAT|Avg", None),
                   ("bar", "RB_AHT_By_Agentforce", "Handle Time: Agentforce vs Human", "RB_Service_Cases.AgentforceHandled", "RB_Service_Cases.HandleTimeMinutes|Avg", None),
                   ("donut", "RB_Deposits_By_Segment", "Deposits by Segment", "RB_Financial_Accounts.Segment", "RB_Financial_Accounts.Balance"),
                   ("line", "RB_Channel_Trend", "Cases by Channel by Month", "RB_Service_Cases.CreatedMonth", "calc:Case_Count", "RB_Service_Cases.Channel")],
    },
    "Cumulus_Wealth": {
        "title": "Advisor Team Command Center", "subtitle": "Advisor team lead view — assets, flows, retention, goal health",
        "filters": [("WM_Households.Region", "Region"), ("WM_Households.ServiceTier", "Service Tier")],
        "titles": {"WM_Net_Flows_Trend": ("July's $45M inflow is one Private Wealth mandate", "Net new assets per month by service tier"),
                   "WM_Interactions_Churn": ("Churned households had a quarter of the interactions", "Average interactions per household, retained vs churned"),
                   "WM_Allocation": ("Equity is 55% of client assets", "Market value by asset class"),
                   "WM_Goals_Status": ("Four in ten goals are at risk or off track", "Client goals by status and type"),
                   "WM_AUM_By_Tier": ("Private Wealth is 61% of AUM", "Assets under management by service tier"),
                   "WM_Inflows_Trend": ("Gross inflows run $25–45M a month", "Inflows per month"),
                   "WM_Outflows_Trend": ("Outflows are steady — the swings are on the inflow side", "Outflows per month"),
                   "WM_Churn_By_State": ("Highest-churn states", "Share of households churned, by state")},
        "kpis": [],
        "kpi_tiles": [("aum", "Assets Under Management", ("Total_AUM", "UserAgg", "Total AUM"), "#6D5BD0", "UpIsGood", "currency", "", "WM_Net_Flows.FlowMonth", ("Net_New_Assets", "UserAgg", "Net New Assets", "currency"), "monthly net flows"),
                      ("nna", "Net New Assets", ("Net_New_Assets", "UserAgg", "Net New Assets"), "#0EA5E9", "UpIsGood", "currency", "", "WM_Net_Flows.FlowMonth"),
                      ("churn", "Household Churn Rate", ("Churn_Rate", "UserAgg", "Churn Rate"), "#EC4899", "UpIsBad", "percent", "0.05", "dim:Churn_Month", ("Churned_Households", "UserAgg", "Churned Households", "number"), "households churned per month"),
                      ("int", "Interactions per Household", ("Interactions_Per_Household", "UserAgg", "Interactions per Household"), "#10B981", "UpIsGood", "number", "30", "dim:Interaction_Month", ("Interaction_Count", "UserAgg", "Interactions", "number"), "interactions per month")],
        "charts": [("line", "WM_Net_Flows_Trend", "Net Flows by Month", "WM_Net_Flows.FlowMonth", "WM_Net_Flows.NetFlow", "WM_Net_Flows.ServiceTier"),
                   ("line", "WM_Inflows_Trend", "Inflows by Month", "WM_Net_Flows.FlowMonth", "calc:Inflow_Total", None),
                   ("line", "WM_Outflows_Trend", "Outflows by Month", "WM_Net_Flows.FlowMonth", "calc:Outflow_Total", None),
                   ("bar", "WM_Interactions_Churn", "Interactions: Retained vs Churned", "WM_Households.Churned", "WM_Households.InteractionCount|Avg", None),
                   ("bar", "WM_Goals_Status", "Goals by Status and Type", "WM_Goals.GoalType", "WM_Goals.TargetValue|Count", "WM_Goals.Status"),
                   ("donut", "WM_Allocation", "Asset Allocation", "WM_Holdings.AssetClass", "WM_Holdings.MarketValue"),
                   ("bar", "WM_AUM_By_Tier", "AUM by Service Tier", "WM_Households.ServiceTier", "WM_Households.AUM", None)],
    },
    "Cumulus_Asset_Management": {
        "title": "Institutional Client Service", "subtitle": "Client service lead view — mandates, flows, request SLAs, pipeline",
        "filters": [("AM_Service_Requests.Region", "Region"), ("AM_Service_Requests.ClientTier", "Client Tier")],
        "titles": {"AM_Flows_Trend": ("Flows are lumpy — mandate wins drive the months", "Net flows per month, all strategies"),
                   "AM_Cycle_By_Type": ("Quarter-end adds a day to every request type", "Average cycle time in days, quarter-end vs normal"),
                   "AM_SLA_Breaches": ("Reconciliation breaches SLA most often (36%)", "Service requests by type, breached vs met"),
                   "AM_Pipeline_By_Stage": ("$14B sits at RFP — the finals stage is the bottleneck", "Pipeline amount by stage"),
                   "AM_AUM_By_Strategy": ("Private Credit and Multi-Asset lead the book", "AUM by strategy"),
                   "AM_Requests_Trend": ("Request volume against the SLA line", "Service requests per month"),
                   "AM_Breach_By_Region": ("All regions, international desks included", "SLA breach rate by region")},
        "kpis": [],
        "kpi_tiles": [("aum", "Assets Under Management", ("Total_AUM", "UserAgg", "Total AUM"), "#0F766E", "UpIsGood", "currency", "", "AM_Mandate_Flows.FlowMonth", ("Ending_AUM", "UserAgg", "Ending AUM", "currency"), "ending AUM by month"),
                      ("req", "Service Requests", ("Request_Count", "UserAgg", "Service Requests"), "#D97706", "UpIsBad", "number", "", "dim:Request_Month"),
                      ("sla", "SLA Breach Rate", ("SLA_Breach_Rate", "UserAgg", "SLA Breach Rate"), "#E11D48", "UpIsBad", "percent", "0.2", "dim:Request_Month"),
                      ("cycle", "Avg Request Cycle (days)", ("Avg_Cycle_Time", "UserAgg", "Avg Cycle Time"), "#2563EB", "UpIsBad", "number", "3", "dim:Request_Month")],
        "charts": [("line", "AM_Flows_Trend", "Net Flows by Month", "AM_Mandate_Flows.FlowMonth", "AM_Mandate_Flows.NetFlow", None),
                   ("bar", "AM_Cycle_By_Type", "Cycle Time by Request Type", "AM_Service_Requests.RequestType", "AM_Service_Requests.CycleTimeDays|Avg", "AM_Service_Requests.IsQuarterEnd"),
                   ("bar", "AM_SLA_Breaches", "SLA Breaches by Request Type", "AM_Service_Requests.RequestType", "calc:Request_Count", "AM_Service_Requests.SLABreached"),
                   ("bar", "AM_Pipeline_By_Stage", "Pipeline by Stage", "AM_Deals.Stage", "AM_Deals.Amount", None),
                   ("donut", "AM_AUM_By_Strategy", "AUM by Strategy", "AM_Mandates.Strategy", "AM_Mandates.AUM"),
                   ("col", "AM_Requests_Trend", "Requests by Month", "dim:Request_Month", "calc:Request_Count", None)],
    },
    "Cumulus_Insurance": {
        "title": "Claims Service Command Center", "subtitle": "Claims service manager view — loss ratio, cycle time, catastrophe impact, renewals",
        "filters": [("INS_Policies.LineOfBusiness", "Line of Business"), ("INS_Claims.State", "State")],
        "titles": {"INS_Claims_Trend": ("June 2026 hail: six times the normal month", "Claims by loss month"),
                   "INS_Cycle_By_CAT": ("Catastrophe claims take 5 days longer to settle", "Average cycle time in days by state, CAT vs normal"),
                   "INS_Loss_Ratio_By_LOB": ("Personal Auto runs the highest loss ratio", "Paid claims over written premium, by line"),
                   "INS_Claims_By_Status": ("67 claims still open — most awaiting review", "Open claims by status"),
                   "INS_Renewals_By_Producer": ("Renewal rates are flat across producer types", "Policies by producer type and status"),
                   "INS_Cases_Agentforce": ("Agentforce-handled claim cases score higher CSAT", "Average CSAT, Agentforce vs human"),
                   "INS_Claims_By_State": ("Claims concentrate in the hail-belt states", "Claims by state"),
                   "INS_Loss_Ratio_By_State": ("Worst loss ratios by state", "Paid claims over written premium")},
        "kpis": [],
        "kpi_tiles": [("claims", "Claims Reported", ("Claim_Count", "UserAgg", "Claims"), "#7C3AED", "UpIsBad", "number", "", "INS_Claims.LossMonth"),
                      ("lr", "Loss Ratio", ("Loss_Ratio", "UserAgg", "Loss Ratio"), "#DB2777", "UpIsBad", "percent", "0.6", "INS_Claims.LossMonth"),
                      ("cycle", "Avg Claim Cycle (days)", ("Avg_Claim_Cycle_Time", "UserAgg", "Avg Claim Cycle Time"), "#A855F7", "UpIsBad", "number", "20", "INS_Claims.LossMonth"),
                      ("open", "Open Claims", ("Open_Claims", "UserAgg", "Open Claims"), "#C026D3", "UpIsBad", "number", "", "dim:Report_Month", ("Claim_Count", "UserAgg", "Claims", "number"), "claims reported per month")],
        "charts": [("line", "INS_Claims_Trend", "Claims by Loss Month", "INS_Claims.LossMonth", "calc:Claim_Count", None),
                   ("bar", "INS_Cycle_By_CAT", "Cycle Time: CAT vs Normal", "INS_Claims.State", "INS_Claims.CycleTimeDays|Avg", "INS_Claims.IsCatastrophe"),
                   ("bar", "INS_Loss_Ratio_By_LOB", "Loss Ratio by Line", "INS_Policies.LineOfBusiness", "calc:Loss_Ratio", None),
                   ("donut", "INS_Claims_By_Status", "Open Claims by Status", "INS_Claims.Status", "calc:Open_Claims"),
                   ("bar", "INS_Renewals_By_Producer", "Policies by Producer Type", "INS_Policies.ProducerType", "INS_Policies.AnnualPremium|Count", "INS_Policies.Status"),
                   ("bar", "INS_Cases_Agentforce", "Claim Case CSAT", "INS_Claim_Cases.AgentforceHandled", "INS_Claim_Cases.CSAT|Avg", None),
                   ("col", "INS_Claims_By_State", "Claims by State", "INS_Claims.State", "calc:Claim_Count", None)],
    },
    "Cumulus_Commercial": {
        "title": "Relationship Desk Command Center", "subtitle": "RM desk lead view — pipeline, credit utilization, onboarding, treasury cross-sell",
        "filters": [("CB_Business_Accounts.Region", "Region"), ("CB_Business_Accounts.Segment", "Segment")],
        "titles": {"CB_Pipeline_By_Stage": ("$900M of pipeline is still pre-proposal", "Deal amount by stage and product"),
                   "CB_Onboarding_Treasury": ("Onboarding takes twice as long without treasury products", "Average onboarding days, with vs without treasury"),
                   "CB_Utilization_By_Rating": ("Utilization is steady near 39% across ratings", "Average facility utilization by risk rating"),
                   "CB_Treasury_Penetration": ("42% of business accounts have no treasury product", "Accounts by treasury product count"),
                   "CB_Cases_By_Type": ("Access and wire inquiries lead service volume", "Service cases by type", (("CB_Service_Cases.HandleTimeMinutes", "Avg", "Handle Time"), "Avg handle time", "number", " min")),
                   "CB_Deal_Flow": ("Deal flow by month", "New pipeline created per month", (("Avg_Monthly_Deal_Flow", "UserAgg", "Avg Monthly Deal Flow"), "Avg deal flow per month", "currency", "")),
                   "CB_Winrate_By_Segment": ("Win rate by segment", "Share of deals won", (("Win_Rate", "UserAgg", "Win Rate"), "Avg win rate", "percent", "")),
                   "CB_Commitments_By_Industry": ("Commitments by industry", "Committed exposure, largest first"),
                   "CB_Utilization_By_Region": ("Utilization by region", "Average facility utilization")},
        "kpis": [],
        "kpi_tiles": [("pipe", "Deal Pipeline", ("Pipeline_Amount", "UserAgg", "Pipeline Amount"), "#2563EB", "UpIsGood", "currency", "", "dim:Deal_Month", None, "pipeline created per month"),
                      ("commit", "Total Commitments", ("Total_Commitments", "UserAgg", "Total Commitments"), "#16A34A", "UpIsGood", "currency", "", "dim:Deal_Month", ("Won_Amount", "UserAgg", "Won Amount", "currency"), "deals won per month"),
                      ("util", "Avg Utilization %", ("Avg_Utilization", "UserAgg", "Avg Utilization"), "#F59E0B", "UpIsBad", "number", "80", "dim:Maturity_Month", None, "by facility maturity month"),
                      ("onb", "Avg Onboarding Days", ("Avg_Onboarding_Days", "UserAgg", "Avg Onboarding Days"), "#EF4444", "UpIsBad", "number", "25", "dim:Onboarding_Month")],
        "charts": [("bar", "CB_Pipeline_By_Stage", "Pipeline by Stage", "CB_Deals.Stage", "CB_Deals.Amount", "CB_Deals.Product"),
                   ("bar", "CB_Onboarding_Treasury", "Onboarding Days by Treasury", "CB_Onboarding.OnboardingType", "CB_Onboarding.CycleTimeDays|Avg", "CB_Onboarding.HasTreasuryProducts"),
                   ("bar", "CB_Utilization_By_Rating", "Utilization by Rating", "CB_Credit_Facilities.RiskRating", "CB_Credit_Facilities.UtilizationPct|Avg", None),
                   ("donut", "CB_Treasury_Penetration", "Treasury Penetration", "CB_Business_Accounts.TreasuryProductCount", "CB_Business_Accounts.AnnualRevenue|Count"),
                   ("bar", "CB_Cases_By_Type", "Service Cases by Type", "CB_Service_Cases.CaseType", "CB_Service_Cases.HandleTimeMinutes|Count", None),
                   ("line", "CB_Deal_Flow", "Deal Flow by Month", "dim:Deal_Month", "CB_Deals.Amount", None),
                   ("bar", "CB_Winrate_By_Segment", "Win Rate by Segment", "CB_Deals.Segment", "calc:Win_Rate", None),
                   ("bar", "CB_Commitments_By_Industry", "Commitments by Industry", "CB_Credit_Facilities.Industry", "CB_Credit_Facilities.CommitmentAmount", None)],
    },
    "Cumulus_Advisors": {
        "title": "My Book of Business", "subtitle": "Advisor view — book growth, life events, follow-up discipline, referrals",
        "filters": [("FA_Life_Events.Region", "Region"), ("FA_Life_Events.LifeStage", "Life Stage")],
        "titles": {"FA_Life_Events_Followup": ("New-child events are the most often missed", "Life events by type, followed up within 14 days or not"),
                   "FA_Book_By_Stage": ("Accumulation clients hold 41% of the book", "Book AUM by life stage and risk profile"),
                   "FA_Activities_By_Advisor": ("Activity cadence varies 2× across advisors", "Activities by advisor and type"),
                   "FA_Referral_Funnel": ("A quarter of referrals convert", "Referrals by status"),
                   "FA_Life_Events_Source": ("Agentforce signals surface $19M of opportunity", "Life-event opportunity value by detection source"),
                   "FA_Activities_Trend": ("Activity cadence by type", "Activities per month by type"),
                   "FA_Opportunity_By_State": ("Biggest opportunity pools by state", "Life-event opportunity value by state")},
        "kpis": [],
        "kpi_tiles": [("aum", "Book AUM", ("Book_AUM", "UserAgg", "Book AUM"), "#15803D", "UpIsGood", "currency", "", "dim:Client_Since_Month", None, "AUM acquired per month"),
                      ("events", "Life Events Detected", ("Life_Events", "UserAgg", "Life Events"), "#7E22CE", "UpIsGood", "number", "", "dim:Event_Month"),
                      ("fu", "Followed Up in 14 Days", ("Followup_Rate", "UserAgg", "Follow-up Rate"), "#0E7490", "UpIsGood", "percent", "0.9", "dim:Event_Month"),
                      ("opp", "Life Event Opportunity", ("Life_Event_Opportunity", "UserAgg", "Opportunity Value"), "#B45309", "UpIsGood", "currency", "", "dim:Event_Month")],
        "charts": [("bar", "FA_Life_Events_Followup", "Life Events: Follow-up", "FA_Life_Events.EventType", "calc:Life_Events", "FA_Life_Events.FollowUpWithin14Days"),
                   ("bar", "FA_Book_By_Stage", "Book by Life Stage", "FA_Book_Of_Business.LifeStage", "FA_Book_Of_Business.AUM", "FA_Book_Of_Business.RiskProfile"),
                   ("bar", "FA_Activities_By_Advisor", "Activities by Advisor", "FA_Activities.AdvisorName", "calc:Activities", "FA_Activities.ActivityType"),
                   ("donut", "FA_Referral_Funnel", "Referrals by Status", "FA_Referrals.Status", "calc:Referral_Count"),
                   ("bar", "FA_Life_Events_Source", "Opportunity by Source", "FA_Life_Events.DetectedSource", "FA_Life_Events.OpportunityValue", None),
                   ("line", "FA_Activities_Trend", "Activities by Month", "dim:Activity_Month", "calc:Activities", "FA_Activities.ActivityType")],
    },
    "Cumulus_Lending": {
        "title": "Loan Operations Command Center", "subtitle": "Loan operations manager view — volume, pull-through, cycle time, stage bottlenecks",
        "filters": [("LN_Applications.Region", "Region"), ("LN_Applications.Channel", "Channel")],
        "titles": {"LN_Apps_Trend": ("Application volume holds steady month to month", "Applications submitted per month"),
                   "LN_Days_By_Stage": ("Document collection is 56% of the cycle", "Average days in each stage"),
                   "LN_Status_By_Channel": ("Pull-through is similar across channels (60–66%)", "Applications by channel and status"),
                   "LN_Volume_By_Product": ("30-year fixed is 57% of requested volume", "Requested volume by product"),
                   "LN_LO_Leaderboard": ("Top loan officers fund $26–39M each", "Requested volume by loan officer, funded vs not"),
                   "LN_Pull_Through_By_Channel": ("Pull-through by channel", "Share of applications funded"),
                   "LN_Time_To_Close_By_State": ("Slowest states to close", "Average days to close by state")},
        "kpis": [],
        "kpi_tiles": [("apps", "Applications", ("Applications", "UserAgg", "Applications"), "#0891B2", "UpIsGood", "number", "", "LN_Applications.SubmittedMonth"),
                      ("pt", "Pull-Through Rate", ("Pull_Through_Rate", "UserAgg", "Pull-Through Rate"), "#C026D3", "UpIsGood", "percent", "0.7", "LN_Applications.SubmittedMonth"),
                      ("ttc", "Avg Time to Close (days)", ("Avg_Time_To_Close", "UserAgg", "Avg Time to Close"), "#DB2777", "UpIsBad", "number", "30", "LN_Applications.SubmittedMonth"),
                      ("vol", "Requested Volume", ("Requested_Volume", "UserAgg", "Requested Volume"), "#0E7490", "UpIsGood", "currency", "", "LN_Applications.SubmittedMonth")],
        "charts": [("line", "LN_Apps_Trend", "Applications by Month", "LN_Applications.SubmittedMonth", "calc:Applications", None),
                   ("bar", "LN_Days_By_Stage", "Days in Stage", "LN_Stage_Events.StageName", "LN_Stage_Events.DaysInStage|Avg", None),
                   ("bar", "LN_Status_By_Channel", "Applications by Channel", "LN_Applications.Channel", "calc:Applications", "LN_Applications.Status"),
                   ("donut", "LN_Volume_By_Product", "Volume by Product", "LN_Applications.ProductName", "LN_Applications.RequestedAmount"),
                   ("bar", "LN_LO_Leaderboard", "Loan Officer Leaderboard", "LN_Applications.LoanOfficerName", "LN_Applications.RequestedAmount", "LN_Applications.IsFunded"),
                   ("bar", "LN_Pull_Through_By_Channel", "Pull-through by Channel", "LN_Applications.Channel", "calc:Pull_Through_Rate", None)],
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
    "Cumulus_Wealth": [("bars", "cumulusRankedBars", 10, {"dimensionField": dimension("WM_Households.AdvisorName", "Advisor Name"), "measureField": measure("WM_Households.AUM", "Sum", "AUM"),
                        "title": "AUM by advisor (click to filter)", "topN": 10, "format": "currency"})],
    "Cumulus_Asset_Management": [("bars", "cumulusRankedBars", 10, {"dimensionField": dimension("AM_Mandate_Flows.ClientName", "Client Name"), "measureField": measure("AM_Mandate_Flows.NetFlow", "Sum", "Net Flow"),
                                  "title": "Net flows by client (click to filter)", "topN": 10, "format": "currency"})],
    "Cumulus_Insurance": [("banner", "cumulusThresholdBanner", 3, {"measureField": measure("Loss_Ratio", "UserAgg", "Loss Ratio"), "threshold": "0.6", "alertMessage": "Loss ratio above 60% — review pricing and claims handling",
                           "okMessage": "Loss ratio within target", "format": "percent", "focusDimension": dimension("INS_Policies.LineOfBusiness", "Line Of Business"), "focusValue": "Renters"})],
    "Cumulus_Commercial": [("banner", "cumulusThresholdBanner", 3, {"measureField": measure("Over_Covenant_Facilities", "UserAgg", "Facilities Over Covenant"), "threshold": "0", "alertMessage": "Credit facilities are drawn beyond covenant — review with the RM",
                            "okMessage": "No facility is over its covenant", "format": "number", "focusDimension": dimension("CB_Credit_Facilities.RiskRating", "Risk Rating"), "focusValue": "4-Watch"})],
    "Cumulus_Advisors": [("nba", "cumulusNextBestActions", 12, {"entityField": dimension("FA_Life_Events.HouseholdName", "Household Name"), "contextField": dimension("FA_Life_Events.EventType", "Event Type"),
                          "scoreField": measure("FA_Life_Events.OpportunityValue", "Sum", "Opportunity Value"), "title": "Life events to follow up", "actionLabel": "Schedule", "lowestFirst": False, "topN": 8, "format": "currency"})],
    "Cumulus_Lending": [("banner", "cumulusThresholdBanner", 3, {"measureField": measure("Avg_Time_To_Close", "UserAgg", "Avg Time to Close"), "threshold": "30", "alertMessage": "Time to close above 30 days — document collection is the bottleneck",
                         "okMessage": "Time to close within target", "format": "number", "focusDimension": dimension("LN_Applications.Channel", "Channel"), "focusValue": "Branch"})],
}


def ext_widget(tname, wname, comp, props):
    p = dict(props); p["sdmName"] = SDM(tname)
    return {"actions": [], "name": wname, "label": comp, "parameters": {"fullyQualifiedName": f"c:{comp}", "properties": p,
            "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#E3E9F1", "borderEdges": [], "borderRadius": 16, "borderWidth": 1}},
            "source": {"name": f"c:{comp}", "namespace": "c", "type": "LightningWebComponent"}, "type": "extension"}


def dim_ref(ref):
    """'dim:Name' (calculated dimension) -> 'Name'; 'Obj.Field' stays as is (the SDK resolves table fields by dotted name)."""
    return ref[4:] if ref.startswith("dim:") else ref


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
    used_hues = []
    for (n, lab, m) in spec["kpis"]:
        m, fn = split_fn(m)
        json.dump(kpi(tname, n, lab, m, fn), open(os.path.join(vdir, n + ".json"), "w"), indent=2); names.append(n)
    for i, c in enumerate(spec["charts"]):
        kind, n, lab, dim, m = c[:5]
        color = c[5] if len(c) > 5 else None
        m, fn = split_fn(m)
        v = {"line": lambda: line(tname, n, lab, dim, m, fn, color), "bar": lambda: bar(tname, n, lab, dim, m, fn, color),
             "line2": lambda: line(tname, n, lab, dim, m, fn, None, second=color), "bartop": lambda: bar(tname, n, lab, dim, m, fn, None, top=color),
             "col": lambda: bar(tname, n, lab, dim, m, fn, color, horizontal=False), "donut": lambda: donut(tname, n, lab, dim, m, fn)}[kind]()
        hue = next_hue(tname, used_hues); used_hues.append(hue); CHART_COLOR[n] = hue
        if kind != "donut":
            paint(v, hue)
        json.dump(v, open(os.path.join(vdir, n + ".json"), "w"), indent=2); names.append(n)
    # Dashboard on the 96-column, 0-indexed grid Tableau Next uses (rowHeight 10px):
    #   title + filters | alert banner (extension) | 4 KPIs | list/tile extension + trend | charts, 3 per band
    W = 96
    widgets, layout = {}, []
    def vis(n, extra=None):
        w = {"actions": [], "name": f"w_{n}", "parameters": {"legendPosition": "Bottom", "receiveFilterSource": {"filterMode": "all", "widgetIds": []},
                                                                "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#E3E9F1", "borderEdges": [], "borderRadius": 16, "borderWidth": 1}},
             "source": {"id": f"${{App.Visualizations.{n}.Id}}", "name": f"${{App.Visualizations.{n}.Name}}"}, "type": "visualization"}
        if extra:
            w["parameters"].update(extra)
        widgets[w["name"]] = w
        return w["name"]
    def place(name, col, row, colspan, rowspan):
        layout.append({"name": name, "column": col, "row": row, "colspan": colspan, "rowspan": rowspan})
    titles = spec.get("titles", {})
    def place_chart(n, col, row, colspan, rowspan, label):
        """A centred headline block (cumulusChartHeadline extension) sits above every chart: short impactful title,
        subtitle and — when `titles[n]` carries a third element — a live summary statistic. The viz has no visible title."""
        entry = titles.get(n, (label, ""))
        t, sub = entry[0], entry[1]
        stat = entry[2] if len(entry) > 2 else None
        hue = CHART_COLOR.get(n, "#032D60")
        props = {"title": t, "subtitle": sub, "accentColor": hue}
        if stat:
            (sm_name, sm_agg, sm_lab), stat_label, stat_fmt, stat_suffix = stat
            props.update({"measureField": measure(sm_name, sm_agg, sm_lab), "statLabel": stat_label, "format": stat_fmt, "statSuffix": stat_suffix})
        w = ext_widget(tname, f"t_{n}", "cumulusChartHeadline", props)
        w["parameters"]["widgetStyle"]["borderWidth"] = 0; w["parameters"]["widgetStyle"]["borderColor"] = "#FFFFFF"
        widgets[f"t_{n}"] = w
        hrows = 7 if stat else 6
        place(f"t_{n}", col, row, colspan, hrows)
        place(vis(n), col, row + hrows, colspan, rowspan - hrows)
    row = 0
    # header band: title text + filters
    title = spec.get("title", f"{tname.replace('_', ' ')} Overview"); sub = spec.get("subtitle", "")
    th = THEMES.get(tname, {"bg": "#F1F5FB", "hdr": "#E3EDF9", "title": "#032D60", "sub": "#3B5577"})
    widgets["hdr"] = {"actions": [], "name": "hdr", "type": "text", "parameters": {"conditionalFormattingRules": [], "receiveFilterSource": {"filterMode": "all", "widgetIds": []},
                      "content": [{"attributes": {"color": th["title"], "size": "26px", "bold": True}, "insert": title, "rules": []}, {"attributes": {"align": "left"}, "insert": "\n", "rules": []},
                                  {"attributes": {"color": th["sub"], "size": "13px"}, "insert": sub, "rules": []}, {"attributes": {"align": "left"}, "insert": "\n", "rules": []}],
                      "widgetStyle": {"backgroundColor": th["hdr"], "borderColor": th["hdr"], "borderEdges": [], "borderRadius": 16, "borderWidth": 0}}}
    filters = spec.get("filters", [])
    fw = 16
    place("hdr", 0, row, W - fw * len(filters), 5)
    for i, (ref, lab) in enumerate(filters):
        obj, fld = ref.split(".", 1)
        wn = f"flt_{fld}"
        widgets[wn] = {"actions": [], "label": lab, "name": wn, "type": "filter", "source": {"name": SDM(tname)["apiName"], "id": SDM(tname)["id"]},
                       "parameters": {"filterOption": {"dataType": "Text", "fieldName": fld, "objectName": obj, "selectionType": "multiple"}, "isLabelHidden": False,
                                      "receiveFilterSource": {"filterMode": "all", "widgetIds": []}, "viewType": "list",
                                      "widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#E3E9F1", "borderEdges": [], "borderRadius": 16, "borderWidth": 1}}}
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
        for i, tile in enumerate(tiles):
            wn, title, (mname, magg, mlab), colour, sent, fmt, target, trend = tile[:8]
            trend_measure = tile[8] if len(tile) > 8 else None
            trend_label = tile[9] if len(tile) > 9 else ""
            props = {"measureField": measure(mname, magg, mlab), "title": title, "accentColor": colour, "sentiment": sent, "format": fmt, "target": target,
                     "strongThreshold": 10, "moderateThreshold": 3}
            if trend:
                props["trendDimension"] = dimension(dim_ref(trend), label_of(trend.split(".")[-1].replace("dim:", "")))
            if trend_measure:
                tm_name, tm_agg, tm_lab, tm_fmt = trend_measure
                props["trendMeasureField"] = measure(tm_name, tm_agg, tm_lab)
                if not trend_label:
                    trend_label = tm_lab.lower()
            if trend_label:
                props["trendLabel"] = trend_label
            widgets[f"k_{wn}"] = ext_widget(tname, f"k_{wn}", "cumulusKpiTile", props)
            place(f"k_{wn}", i * kw, row, kw, 16)
        row += 16
    # map band: cumulusStateMap extension (left ~60%) + a supporting ranked bar chart
    mp = MAPS.get(tname)
    if mp:
        mdim, (sm_name, sm_agg, sm_lab, sm_fmt), bub, mtitle, msub, side_chart = mp
        low, high, bubble = THEMES.get(tname, {}).get("map", ("#DBEAFE", "#1D4ED8", "#F59E0B"))
        props = {"dimensionField": dimension(dim_ref(mdim), label_of(mdim.split(".")[-1].replace("dim:", ""))), "measureField": measure(sm_name, sm_agg, sm_lab),
                 "title": mtitle, "subtitle": msub, "format": sm_fmt, "lowColor": low, "highColor": high, "bubbleColor": bubble, "showLabels": True}
        if bub:
            b_name, b_agg, b_lab, b_fmt = bub
            props["bubbleMeasureField"] = measure(b_name, b_agg, b_lab); props["bubbleFormat"] = b_fmt
        widgets["x_map"] = ext_widget(tname, "x_map", "cumulusStateMap", props)
        place("x_map", 0, row, 60, 38)
        kind, n, lab, dim, m, color = side_chart
        m, fn = split_fn(m)
        v = bar(tname, n, lab, dim, m, fn, color)
        hue = next_hue(tname, used_hues); used_hues.append(hue); CHART_COLOR[n] = hue
        paint(v, hue)
        json.dump(v, open(os.path.join(vdir, n + ".json"), "w"), indent=2); names.append(n)
        place_chart(n, 60, row, W - 60, 38, lab)
        row += 38
    elif spec["kpis"]:
        kw = W // len(spec["kpis"])
        for i, (n, _, _) in enumerate(spec["kpis"]):
            place(vis(n), i * kw, row, kw, 9)
        row += 9
    # trend band: side extension (left third) + first chart
    charts = list(spec["charts"])
    first_c = charts.pop(0); first, first_label = first_c[1], first_c[2]
    if sides:
        wname, comp, height, props = sides[0]
        widgets[f"x_{wname}"] = ext_widget(tname, f"x_{wname}", comp, props)
        place(f"x_{wname}", 0, row, 28, 34)
        place_chart(first, 28, row, W - 28, 34, first_label)
    else:
        place_chart(first, 0, row, W, 30, first_label)
    row += 34 if sides else 30
    # remaining charts, three per band
    per = 3
    for j, c in enumerate(charts):
        cw = W // per
        place_chart(c[1], (j % per) * cw, row + (j // per) * 30, cw, 30, c[2])
    dash = {"name": f"{tname}_Overview", "label": f"{tname.replace('_', ' ')} Overview ${{Variables.LabelSuffix}}",
            "description": f"{tname.replace('_', ' ')} — service and business KPIs for the Cumulus Financial Group demo.",
            "customConfig": {"queryCacheEnabled": True, "queryCacheStaleness": "30min"},
            "layouts": [{"columnCount": W, "maxWidth": 1600, "name": "default", "pages": [{"label": "Overview", "name": "overview", "widgets": layout}], "rowHeight": 10,
                         "style": {"backgroundColor": th["bg"], "cellSpacingX": 14, "cellSpacingY": 14, "gutterColor": th["bg"]}}],
            "style": {"widgetStyle": {"backgroundColor": "#FFFFFF", "borderColor": "#E3E9F1", "borderEdges": [], "borderRadius": 16, "borderWidth": 1}},
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
