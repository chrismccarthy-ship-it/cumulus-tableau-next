#!/usr/bin/env python3
"""
Build seven App Template Framework (ATF) "CSV data templates" — one per Cumulus line of
business — from the normalized CSVs in data/out.

Each template installs bottom-up in ANY Tableau Next org with zero manual steps:
  CSV -> DataStreamUpsert (DLO) -> DataStreamRun -> WorkspaceUpsert -> SemanticModelUpsert
      -> VisualizationUpsert* -> DashboardUpsert        (* added in phase P3)

Output: force-app/main/default/appTemplates/Cumulus_<LOB>/
  template-info.json, template-policy.json, variables.json, layout.json,
  workspaces/, datastreams/, csvs/, sdms/, create-chain.json
  (+ visualizations/ and dashboards/ picked up automatically when present)

Design rules (from the field-verified ATF playbook):
  - <=5 data streams per template (ingestion is ~6 min per stream, serial)
  - denormalize lookups into fact tables; dates ISO yyyy-MM-dd; DateTime -> Date
  - never hardcode a physical __dll name: bind through ${App.DataLakeObjects.<node>.Name}
  - Boolean/Number/Text/Date only; camelCase `dataType`; PK on every DLO
  - serial ingestion; SDM sources the last DataStreamRun; dashboard sources vizzes

Usage: python3 atf/build_templates.py [--out force-app/main/default/appTemplates] [--lob retail_banking,...]
"""
import argparse
import csv
import json
import os
import re
import shutil
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "out")
DEFAULT_OUT = os.path.join(ROOT, "force-app", "main", "default", "appTemplates")
ASSET_VERSION = 67.0

# --------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------


def load(lob, table):
    with open(os.path.join(DATA, lob, table + ".csv"), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def index(rows, key):
    return {r[key]: r for r in rows}


def label_of(name):
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ")
    return s.replace("Pct", "%").replace("Id", "ID").replace("A U M", "AUM").replace("C S A T", "CSAT").replace("N P S", "NPS")


def to_date(v):
    return v[:10] if v else ""


def infer_type(col, values):
    """Text | Number | Date | Boolean from column name + sample values."""
    sample = [v for v in values[:500] if v != ""]
    if not sample:
        return "Text"
    if all(v in ("true", "false") for v in sample):
        return "Boolean"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in sample):
        return "Date"
    if col.endswith("Id") or col.endswith("Number") and not col.startswith("Annual"):
        return "Text"
    try:
        for v in sample:
            float(v)
        return "Number"
    except ValueError:
        return "Text"


# --------------------------------------------------------------------------------
# LOB template definitions: denormalized tables built from the normalized CSVs
# --------------------------------------------------------------------------------


def T(name, rows, pk, measures=None, hide=()):
    """A template table. `measures`: numeric columns that are measures (default: all Number columns)."""
    return {"name": name, "rows": rows, "pk": pk, "measures": measures, "hide": set(hide)}


def merge(rows, lookup, key, fields, prefix=""):
    """Copy `fields` (dict target->source) from lookup[row[key]] into each row."""
    out = []
    for r in rows:
        r = dict(r)
        l = lookup.get(r.get(key, ""), {})
        for tgt, src in fields.items():
            r[prefix + tgt] = l.get(src, "")
        out.append(r)
    return out


def dates_only(rows, cols):
    for r in rows:
        for c in cols:
            r[c] = to_date(r.get(c, ""))
    return rows


def lob_retail(shared):
    br, emp = shared
    hh = load("retail_banking", "rb_households")
    cu = load("retail_banking", "rb_customers")
    fa = load("retail_banking", "rb_financial_accounts")
    tx = load("retail_banking", "rb_financial_account_transactions")
    cs = load("retail_banking", "rb_service_cases")
    prim = {c["HouseholdId"]: c for c in cu if c["IsPrimary"] == "true"}
    hh = merge(hh, br, "BranchId", {"BranchName": "BranchName", "Region": "Region", "State": "State"})
    hh = merge(hh, emp, "PrimaryBankerId", {"PrimaryBankerName": "EmployeeName"})
    for r in hh:
        p = prim.get(r["HouseholdId"], {})
        r["PrimaryCustomerName"] = f"{p.get('FirstName', '')} {p.get('LastName', '')}".strip()
        r["PrimaryCustomerAge"] = p.get("Age", "")
        r["PreferredChannel"] = p.get("PreferredChannel", "")
        r["ProductCount"] = str(sum(1 for a in fa if a["HouseholdId"] == r["HouseholdId"] and a["Status"] == "Open"))
    hhi = index(hh, "HouseholdId")
    fa = merge(fa, hhi, "HouseholdId", {"HouseholdName": "HouseholdName", "Segment": "Segment", "Region": "Region", "BranchName": "BranchName"})
    cs = merge(cs, index(cu, "CustomerId"), "CustomerId", {"CustomerFirstName": "FirstName", "CustomerLastName": "LastName"})
    cs = merge(cs, br, "BranchId", {"BranchName": "BranchName", "Region": "Region"})
    cs = merge(cs, emp, "AgentId", {"AgentName": "EmployeeName", "AgentTeam": "Team"})
    for r in cs:
        r["CustomerName"] = f"{r.pop('CustomerFirstName')} {r.pop('CustomerLastName')}".strip()
        r["CreatedMonth"] = r["CreatedDate"][:7] + "-01"
    tx = merge(tx, index(fa, "FinancialAccountId"), "FinancialAccountId", {"FinancialAccountType": "FinancialAccountType", "HouseholdId": "HouseholdId", "BranchName": "BranchName", "Region": "Region"})
    dates_only(hh, ["RelationshipStartDate"]); dates_only(fa, ["OpenDate"]); dates_only(tx, ["TransactionDate"]); dates_only(cs, ["CreatedDate", "ClosedDate"])
    return {
        "label": "Cumulus Retail Banking", "description": "Branch service manager view: deposits, product penetration, service cases (channel, FCR, CSAT, Agentforce), transactions and disputes. Includes the Lauren Bailey storyline.",
        "tables": [T("RB_Households", hh, "HouseholdId", measures=["NPS", "PrimaryCustomerAge", "ProductCount"]),
                   T("RB_Financial_Accounts", fa, "FinancialAccountId", measures=["Balance"]),
                   T("RB_Transactions", tx, "TransactionId", measures=["Amount"]),
                   T("RB_Service_Cases", cs, "CaseId", measures=["CSAT", "HandleTimeMinutes"])],
        "relationships": [("RB_Financial_Accounts", "HouseholdId", "RB_Households", "HouseholdId"),
                          ("RB_Transactions", "FinancialAccountId", "RB_Financial_Accounts", "FinancialAccountId"),
                          ("RB_Service_Cases", "FinancialAccountId", "RB_Financial_Accounts", "FinancialAccountId")],
        "calcs": [("Case_Count", "Cases", "count([RB_Service_Cases])", "SentimentTypeUpIsBad"),
                  ("Total_Deposits", "Total Deposits", "SUM([RB_Financial_Accounts].[Balance])", "SentimentTypeUpIsGood"),
                  ("Avg_Handle_Time", "Avg Handle Time (min)", "AVG([RB_Service_Cases].[HandleTimeMinutes])", "SentimentTypeUpIsBad"),
                  ("Avg_CSAT", "Avg CSAT", "AVG([RB_Service_Cases].[CSAT])", "SentimentTypeUpIsGood"),
                  ("Card_Dispute_Cases", "Card Dispute Cases", "COUNT(IF [RB_Service_Cases].[CaseType] = 'Card Dispute' THEN [RB_Service_Cases].[CaseId] END)", "SentimentTypeUpIsBad"),
                  ("FCR_Rate", "First-Contact Resolution Rate", "COUNT(IF [RB_Service_Cases].[FirstContactResolution] = true THEN [RB_Service_Cases].[CaseId] END) / COUNT([RB_Service_Cases].[CaseId])", "SentimentTypeUpIsGood")],
        "metrics": [("Service_Cases", "Service Cases", "RB_Service_Cases", "calc:Case_Count", "UserAgg", "CreatedDate", ["Channel", "CaseType", "BranchName"], "SentimentTypeUpIsBad"),
                    ("Deposit_Balance", "Deposit Balance", "RB_Financial_Accounts", "Balance", "Sum", "OpenDate", ["Region", "Segment", "FinancialAccountType"], "SentimentTypeUpIsGood")],
    }


def lob_wealth(shared):
    br, emp = shared
    hh = load("wealth", "wm_households"); fa = load("wealth", "wm_financial_accounts"); hd = load("wealth", "wm_financial_holdings")
    gl = load("wealth", "wm_financial_goals"); it = load("wealth", "wm_interactions"); fl = load("wealth", "wm_net_flows")
    hh = merge(hh, emp, "AdvisorId", {"AdvisorName": "EmployeeName", "AdvisorTeam": "Team"})
    hh = merge(hh, br, "BranchId", {"BranchName": "BranchName", "Region": "Region"})
    for r in hh:
        r["InteractionCount"] = str(sum(1 for i in it if i["HouseholdId"] == r["HouseholdId"]))
    hhi = index(hh, "HouseholdId")
    fai = index(fa, "FinancialAccountId")
    hd = merge(hd, fai, "FinancialAccountId", {"HouseholdId": "HouseholdId", "FinancialAccountType": "FinancialAccountType", "Custodian": "Custodian"})
    hd = merge(hd, hhi, "HouseholdId", {"HouseholdName": "HouseholdName", "AdvisorName": "AdvisorName", "RiskProfile": "RiskProfile", "ServiceTier": "ServiceTier"})
    gl = merge(gl, hhi, "HouseholdId", {"HouseholdName": "HouseholdName", "AdvisorName": "AdvisorName"})
    it = merge(it, hhi, "HouseholdId", {"HouseholdName": "HouseholdName", "AdvisorName": "AdvisorName", "Churned": "Churned", "ServiceTier": "ServiceTier"})
    fl = merge(fl, hhi, "HouseholdId", {"HouseholdName": "HouseholdName", "AdvisorName": "AdvisorName", "ServiceTier": "ServiceTier", "Region": "Region"})
    dates_only(hh, ["RelationshipStartDate", "ChurnDate"]); dates_only(hd, ["AsOfDate"]); dates_only(gl, ["TargetDate"]); dates_only(it, ["InteractionDate"]); dates_only(fl, ["FlowMonth"])
    return {
        "label": "Cumulus Wealth Management", "description": "Advisor team lead view: AUM, net new assets, goal progress, interaction cadence vs retention. Includes the Ashford Family Office storyline.",
        "tables": [T("WM_Households", hh, "HouseholdId", measures=["AUM", "AnnualRevenue", "InteractionCount"]),
                   T("WM_Holdings", hd, "HoldingId", measures=["Shares", "Price", "MarketValue", "CostBasis"]),
                   T("WM_Goals", gl, "GoalId", measures=["TargetValue", "ActualValue"]),
                   T("WM_Interactions", it, "InteractionId", measures=["DurationMinutes"]),
                   T("WM_Net_Flows", fl, "FlowId", measures=["NetFlow", "Inflow", "Outflow"])],
        "relationships": [("WM_Holdings", "HouseholdId", "WM_Households", "HouseholdId"), ("WM_Goals", "HouseholdId", "WM_Households", "HouseholdId"),
                          ("WM_Interactions", "HouseholdId", "WM_Households", "HouseholdId"), ("WM_Net_Flows", "HouseholdId", "WM_Households", "HouseholdId")],
        "calcs": [("Total_AUM", "Total AUM", "SUM([WM_Households].[AUM])", "SentimentTypeUpIsGood"),
                  ("Net_New_Assets", "Net New Assets", "SUM([WM_Net_Flows].[NetFlow])", "SentimentTypeUpIsGood"),
                  ("Household_Count", "Households", "count([WM_Households])", "SentimentTypeUpIsGood"),
                  ("Interactions_Per_Household", "Interactions per Household", "count([WM_Interactions]) / count([WM_Households])", "SentimentTypeUpIsGood")],
        "metrics": [("Net_New_Assets_M", "Net New Assets", "WM_Net_Flows", "NetFlow", "Sum", "FlowMonth", ["AdvisorName", "ServiceTier", "Region"], "SentimentTypeUpIsGood"),
                    ("AUM_M", "Assets Under Management", "WM_Households", "AUM", "Sum", "RelationshipStartDate", ["AdvisorName", "RiskProfile", "ServiceTier"], "SentimentTypeUpIsGood")],
    }


def lob_asset_mgmt(shared):
    br, emp = shared
    cl = load("asset_management", "am_clients"); md = load("asset_management", "am_mandates"); fl = load("asset_management", "am_mandate_flows")
    dl = load("asset_management", "am_financial_deals"); sr = load("asset_management", "am_service_requests")
    cl = merge(cl, emp, "RelationshipManagerId", {"RelationshipManagerName": "EmployeeName"})
    cl = merge(cl, emp, "ServiceAssociateId", {"ServiceAssociateName": "EmployeeName"})
    cli = index(cl, "ClientId")
    cf = {"ClientName": "ClientName", "ClientType": "ClientType", "ClientTier": "ClientTier", "Region": "Region", "RelationshipManagerName": "RelationshipManagerName"}
    md = merge(md, cli, "ClientId", cf); fl = merge(fl, cli, "ClientId", cf); dl = merge(dl, cli, "ClientId", cf)
    sr = merge(sr, cli, "ClientId", dict(cf, ServiceAssociateName="ServiceAssociateName"))
    fl = merge(fl, index(md, "MandateId"), "MandateId", {"Strategy": "Strategy", "Vehicle": "Vehicle"})
    for r in sr:
        m = r["CreatedDate"][5:7]; d = int(r["CreatedDate"][8:10])
        r["IsQuarterEnd"] = "true" if m in ("01", "04", "07", "10") and d <= 12 else "false"
    dates_only(md, ["InceptionDate"]); dates_only(fl, ["FlowMonth"]); dates_only(dl, ["CreatedDate", "CloseDate"]); dates_only(sr, ["CreatedDate", "ClosedDate"])
    return {
        "label": "Cumulus Asset Management", "description": "Institutional client service view: AUM and flows by strategy, deal pipeline, SLA attainment and request cycle time (quarter-end reconciliation story).",
        "tables": [T("AM_Mandates", md, "MandateId", measures=["AUM", "FeeRateBps"]),
                   T("AM_Mandate_Flows", fl, "FlowId", measures=["NetFlow", "MarketReturnPct", "EndingAUM"]),
                   T("AM_Deals", dl, "DealId", measures=["Amount"]),
                   T("AM_Service_Requests", sr, "RequestId", measures=["SLADays", "CycleTimeDays"])],
        "relationships": [("AM_Mandate_Flows", "MandateId", "AM_Mandates", "MandateId")],
        "calcs": [("Total_AUM", "Total AUM", "SUM([AM_Mandates].[AUM])", "SentimentTypeUpIsGood"),
                  ("Request_Count", "Service Requests", "count([AM_Service_Requests])", "SentimentTypeUpIsBad"),
                  ("Avg_Cycle_Time", "Avg Cycle Time (days)", "AVG([AM_Service_Requests].[CycleTimeDays])", "SentimentTypeUpIsBad"),
                  ("Pipeline_Amount", "Pipeline Amount", "SUM([AM_Deals].[Amount])", "SentimentTypeUpIsGood")],
        "metrics": [("Net_Flows_M", "Net Flows", "AM_Mandate_Flows", "NetFlow", "Sum", "FlowMonth", ["Strategy", "ClientType", "Region"], "SentimentTypeUpIsGood"),
                    ("Requests_M", "Service Requests", "AM_Service_Requests", "calc:Request_Count", "UserAgg", "CreatedDate", ["RequestType", "ClientTier", "Priority"], "SentimentTypeUpIsBad")],
    }


def lob_insurance(shared):
    br, emp = shared
    pr = load("insurance", "ins_producers"); po = load("insurance", "ins_policies"); cl = load("insurance", "ins_claims"); cc = load("insurance", "ins_claim_cases")
    po = merge(po, index(pr, "ProducerId"), "ProducerId", {"ProducerName": "ProducerName", "ProducerType": "ProducerType", "ProducerRegion": "Region"})
    poi = index(po, "PolicyId")
    cl = merge(cl, poi, "PolicyId", {"LineOfBusiness": "LineOfBusiness", "PolicyType": "PolicyType", "State": "State", "Carrier": "Carrier", "AnnualPremium": "AnnualPremium", "NamedInsured": "NamedInsured", "ProducerName": "ProducerName"})
    cl = merge(cl, emp, "AdjusterId", {"AdjusterName": "EmployeeName"})
    for r in cl:
        r["IsCatastrophe"] = "true" if r["CatastropheCode"] else "false"
        r["LossMonth"] = r["LossDate"][:7] + "-01"
    cc = merge(cc, index(cl, "ClaimId"), "ClaimId", {"ClaimType": "ClaimType", "LineOfBusiness": "LineOfBusiness", "State": "State", "IsCatastrophe": "IsCatastrophe"})
    dates_only(po, ["EffectiveDate", "ExpirationDate"]); dates_only(cl, ["LossDate", "ReportDate", "FinalizedDate"]); dates_only(cc, ["CreatedDate"])
    return {
        "label": "Cumulus Insurance", "description": "Claims service manager view: loss ratio, claims cycle time, open claims aging, renewal rate by producer, catastrophe impact (June 2026 hail), Agentforce-handled claim cases. Includes the Elena Ruiz HO-3 storyline.",
        "tables": [T("INS_Policies", po, "PolicyId", measures=["AnnualPremium"]),
                   T("INS_Claims", cl, "ClaimId", measures=["ReserveAmount", "PaidAmount", "CycleTimeDays", "AnnualPremium"]),
                   T("INS_Claim_Cases", cc, "CaseId", measures=["HandleTimeMinutes", "CSAT"])],
        "relationships": [("INS_Claims", "PolicyId", "INS_Policies", "PolicyId"), ("INS_Claim_Cases", "ClaimId", "INS_Claims", "ClaimId")],
        "calcs": [("Claim_Count", "Claims", "count([INS_Claims])", "SentimentTypeUpIsBad"),
                  ("Total_Paid", "Total Paid", "SUM([INS_Claims].[PaidAmount])", "SentimentTypeUpIsBad"),
                  ("Written_Premium", "Written Premium", "SUM([INS_Policies].[AnnualPremium])", "SentimentTypeUpIsGood"),
                  ("Loss_Ratio", "Loss Ratio", "SUM([INS_Claims].[PaidAmount]) / SUM([INS_Policies].[AnnualPremium])", "SentimentTypeUpIsBad"),
                  ("Avg_Claim_Cycle_Time", "Avg Claim Cycle Time (days)", "AVG([INS_Claims].[CycleTimeDays])", "SentimentTypeUpIsBad")],
        "metrics": [("Claims_M", "Claims Reported", "INS_Claims", "calc:Claim_Count", "UserAgg", "ReportDate", ["LineOfBusiness", "State", "ClaimType"], "SentimentTypeUpIsBad"),
                    ("Premium_M", "Written Premium", "INS_Policies", "AnnualPremium", "Sum", "EffectiveDate", ["LineOfBusiness", "Carrier", "ProducerType"], "SentimentTypeUpIsGood")],
    }


def lob_commercial(shared):
    br, emp = shared
    ba = load("commercial", "cb_business_accounts"); dl = load("commercial", "cb_financial_deals"); fc = load("commercial", "cb_credit_facilities")
    tp = load("commercial", "cb_treasury_enrollments"); rf = load("commercial", "cb_referrals"); ob = load("commercial", "cb_onboarding"); cs = load("commercial", "cb_service_cases")
    ba = merge(ba, emp, "RelationshipManagerId", {"RelationshipManagerName": "EmployeeName"})
    for r in ba:
        mine = [t for t in tp if t["BusinessAccountId"] == r["BusinessAccountId"] and t["Status"] == "Active"]
        r["TreasuryProductCount"] = str(len(mine))
        r["TreasuryProducts"] = "; ".join(sorted(t["ProductName"] for t in mine))
        r["HasTreasuryProducts"] = "true" if mine else "false"
        refs = [x for x in rf if x["BusinessAccountId"] == r["BusinessAccountId"]]
        r["ReferralCount"] = str(len(refs)); r["ConvertedReferrals"] = str(sum(1 for x in refs if x["Status"] == "Converted"))
    bai = index(ba, "BusinessAccountId")
    bf = {"BusinessName": "BusinessName", "Industry": "Industry", "Segment": "Segment", "Region": "Region", "RelationshipManagerName": "RelationshipManagerName"}
    dl = merge(dl, bai, "BusinessAccountId", bf); fc = merge(fc, bai, "BusinessAccountId", bf); ob = merge(ob, bai, "BusinessAccountId", bf); cs = merge(cs, bai, "BusinessAccountId", bf)
    cs = merge(cs, emp, "AgentId", {"AgentName": "EmployeeName"})
    for r in fc:
        r["OverCovenant"] = "true" if float(r["UtilizationPct"]) > float(r["CovenantUtilizationMax"]) else "false"
    dates_only(ba, ["RelationshipStartDate"]); dates_only(dl, ["CreatedDate", "CloseDate"]); dates_only(fc, ["MaturityDate"]); dates_only(ob, ["StartDate", "CompletedDate"]); dates_only(cs, ["CreatedDate"])
    return {
        "label": "Cumulus Commercial Banking", "description": "Relationship manager desk view: deal pipeline, facility utilization vs covenants, treasury penetration, onboarding cycle time (2x longer without treasury), ACH/sFTP service cases. Includes the Meridian Logistics storyline.",
        "tables": [T("CB_Business_Accounts", ba, "BusinessAccountId", measures=["AnnualRevenue", "RelationshipProfitability", "TreasuryProductCount", "ReferralCount", "ConvertedReferrals"]),
                   T("CB_Deals", dl, "DealId", measures=["Amount"]),
                   T("CB_Credit_Facilities", fc, "FacilityId", measures=["CommitmentAmount", "OutstandingBalance", "UtilizationPct", "CovenantUtilizationMax"]),
                   T("CB_Onboarding", ob, "OnboardingId", measures=["CycleTimeDays", "DocumentsRequested"]),
                   T("CB_Service_Cases", cs, "CaseId", measures=["HandleTimeMinutes", "CSAT"])],
        "relationships": [(t, "BusinessAccountId", "CB_Business_Accounts", "BusinessAccountId") for t in ("CB_Deals", "CB_Credit_Facilities", "CB_Onboarding", "CB_Service_Cases")],
        "calcs": [("Pipeline_Amount", "Pipeline Amount", "SUM([CB_Deals].[Amount])", "SentimentTypeUpIsGood"),
                  ("Total_Commitments", "Total Commitments", "SUM([CB_Credit_Facilities].[CommitmentAmount])", "SentimentTypeUpIsGood"),
                  ("Avg_Utilization", "Avg Utilization %", "AVG([CB_Credit_Facilities].[UtilizationPct])", "SentimentTypeUpIsBad"),
                  ("Avg_Onboarding_Days", "Avg Onboarding Days", "AVG([CB_Onboarding].[CycleTimeDays])", "SentimentTypeUpIsBad")],
        "metrics": [("Pipeline_M", "Deal Pipeline", "CB_Deals", "Amount", "Sum", "CreatedDate", ["Stage", "Product", "Segment"], "SentimentTypeUpIsGood"),
                    ("Onboarding_Cycle_M", "Onboarding Cycle Time", "CB_Onboarding", "calc:Avg_Onboarding_Days", "UserAgg", "StartDate", ["OnboardingType", "HasTreasuryProducts", "Segment"], "SentimentTypeUpIsBad")],
    }


def lob_advisors(shared):
    br, emp = shared
    bk = load("advisors", "fa_book_of_business"); ac = load("advisors", "fa_activities"); rf = load("advisors", "fa_referrals"); le = load("advisors", "fa_life_events"); gl = load("advisors", "fa_financial_goals")
    bk = merge(bk, emp, "AdvisorId", {"AdvisorName": "EmployeeName", "AdvisorTeam": "Team"})
    bk = merge(bk, br, "BranchId", {"BranchName": "BranchName", "Region": "Region"})
    for r in bk:
        g = [x for x in gl if x["ClientHouseholdId"] == r["ClientHouseholdId"]]
        r["GoalCount"] = str(len(g)); r["GoalsAtRisk"] = str(sum(1 for x in g if x["Status"] in ("At Risk", "Off Track")))
        r["ActivityCount"] = str(sum(1 for a in ac if a["ClientHouseholdId"] == r["ClientHouseholdId"]))
    bki = index(bk, "ClientHouseholdId")
    hf = {"HouseholdName": "HouseholdName", "AdvisorName": "AdvisorName", "LifeStage": "LifeStage", "AUM": "AUM", "Region": "Region"}
    ac = merge(ac, bki, "ClientHouseholdId", hf); le = merge(le, bki, "ClientHouseholdId", hf)
    rf = merge(rf, emp, "AdvisorId", {"AdvisorName": "EmployeeName"})
    dates_only(bk, ["ClientSince", "LastReviewDate"]); dates_only(ac, ["ActivityDate"]); dates_only(rf, ["ReferralDate"]); dates_only(le, ["EventDate", "FollowUpDate"])
    return {
        "label": "Cumulus Financial Advisors", "description": "Advisor book-of-business view: AUM by life stage and risk, activity cadence, referral funnel, life-event follow-up (30% missed within 14 days), goal attainment.",
        "tables": [T("FA_Book_Of_Business", bk, "ClientHouseholdId", measures=["AUM", "ProductsHeld", "GoalCount", "GoalsAtRisk", "ActivityCount"]),
                   T("FA_Activities", ac, "ActivityId", measures=["DurationMinutes", "AUM"]),
                   T("FA_Referrals", rf, "ReferralId", measures=["EstimatedAUM", "DaysToFirstContact"]),
                   T("FA_Life_Events", le, "LifeEventId", measures=["OpportunityValue", "AUM"])],
        "relationships": [("FA_Activities", "ClientHouseholdId", "FA_Book_Of_Business", "ClientHouseholdId"), ("FA_Life_Events", "ClientHouseholdId", "FA_Book_Of_Business", "ClientHouseholdId")],
        "calcs": [("Book_AUM", "Book AUM", "SUM([FA_Book_Of_Business].[AUM])", "SentimentTypeUpIsGood"),
                  ("Activities", "Activities", "count([FA_Activities])", "SentimentTypeUpIsGood"),
                  ("Life_Events", "Life Events", "count([FA_Life_Events])", "SentimentTypeUpIsGood"),
                  ("Life_Event_Opportunity", "Life Event Opportunity Value", "SUM([FA_Life_Events].[OpportunityValue])", "SentimentTypeUpIsGood"),
                  ("Referral_Count", "Referrals", "count([FA_Referrals])", "SentimentTypeUpIsGood")],
        "metrics": [("Activities_M", "Client Activities", "FA_Activities", "calc:Activities", "UserAgg", "ActivityDate", ["ActivityType", "AdvisorName", "LifeStage"], "SentimentTypeUpIsGood"),
                    ("Referrals_M", "Referrals", "FA_Referrals", "calc:Referral_Count", "UserAgg", "ReferralDate", ["ReferralSource", "Status", "AdvisorName"], "SentimentTypeUpIsGood")],
    }


def lob_lending(shared):
    br, emp = shared
    ap = load("lending", "ln_applications"); se = load("lending", "ln_stage_events"); cs = load("lending", "ln_service_cases")
    ap = merge(ap, emp, "LoanOfficerId", {"LoanOfficerName": "EmployeeName"})
    ap = merge(ap, br, "BranchId", {"BranchName": "BranchName", "Region": "Region"})
    for r in ap:
        r["SubmittedMonth"] = r["SubmittedDate"][:7] + "-01"
    api = index(ap, "ApplicationId")
    af = {"ProductName": "ProductName", "Channel": "Channel", "LoanOfficerName": "LoanOfficerName", "Status": "Status", "Region": "Region"}
    se = merge(se, api, "ApplicationId", af); cs = merge(cs, api, "ApplicationId", af)
    cs = merge(cs, emp, "AgentId", {"AgentName": "EmployeeName"})
    dates_only(ap, ["SubmittedDate", "DecisionDate", "FundedDate", "SubmittedMonth"]); dates_only(se, ["EnteredDate", "ExitedDate"]); dates_only(cs, ["CreatedDate"])
    return {
        "label": "Cumulus Lending", "description": "Loan operations view: pull-through rate, time to close, stage funnel (document collection = 55% of cycle), digital abandonment, loan officer productivity, in-flight service cases.",
        "tables": [T("LN_Applications", ap, "ApplicationId", measures=["RequestedAmount", "CycleTimeDays", "CreditScore", "DTIRatio", "InterestRate", "DocumentsOutstanding"]),
                   T("LN_Stage_Events", se, "StageEventId", measures=["StageOrder", "DaysInStage"]),
                   T("LN_Service_Cases", cs, "CaseId", measures=["HandleTimeMinutes", "CSAT"])],
        "relationships": [("LN_Stage_Events", "ApplicationId", "LN_Applications", "ApplicationId"), ("LN_Service_Cases", "ApplicationId", "LN_Applications", "ApplicationId")],
        "calcs": [("Applications", "Applications", "count([LN_Applications])", "SentimentTypeUpIsGood"),
                  ("Requested_Volume", "Requested Volume", "SUM([LN_Applications].[RequestedAmount])", "SentimentTypeUpIsGood"),
                  ("Avg_Time_To_Close", "Avg Time to Close (days)", "AVG([LN_Applications].[CycleTimeDays])", "SentimentTypeUpIsBad"),
                  ("Avg_Days_In_Stage", "Avg Days in Stage", "AVG([LN_Stage_Events].[DaysInStage])", "SentimentTypeUpIsBad")],
        "metrics": [("Applications_M", "Loan Applications", "LN_Applications", "calc:Applications", "UserAgg", "SubmittedDate", ["ProductName", "Channel", "Status"], "SentimentTypeUpIsGood"),
                    ("Funded_Volume_M", "Requested Volume", "LN_Applications", "RequestedAmount", "Sum", "SubmittedDate", ["ProductName", "Channel", "LoanOfficerName"], "SentimentTypeUpIsGood")],
    }


LOBS = OrderedDict([("retail_banking", ("Cumulus_Retail_Banking", lob_retail)), ("wealth", ("Cumulus_Wealth", lob_wealth)),
                    ("asset_management", ("Cumulus_Asset_Management", lob_asset_mgmt)), ("insurance", ("Cumulus_Insurance", lob_insurance)),
                    ("commercial", ("Cumulus_Commercial", lob_commercial)), ("advisors", ("Cumulus_Advisors", lob_advisors)), ("lending", ("Cumulus_Lending", lob_lending))])

# --------------------------------------------------------------------------------
# emitters
# --------------------------------------------------------------------------------


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def emit_csv(path, rows, cols):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def build_table_meta(t):
    cols = list(t["rows"][0].keys())
    types = {c: infer_type(c, [r[c] for r in t["rows"]]) for c in cols}
    measures = set(t["measures"] or [c for c in cols if types[c] == "Number"])
    for c in measures:
        types[c] = "Number"
    return cols, types, measures


def datastream_json(t, cols, types, label_suffix="${Variables.LabelSuffix}"):
    return {
        "name": t["name"] + "_DS", "label": f"{label_of(t['name'])} DS {label_suffix}", "datastreamType": "CONNECTORSFRAMEWORK",
        "connectorInfo": {"connectorType": "DataConnector", "connectorDetails": {"name": "UploadedFiles"}},
        "sourceFields": [dict({"dataType": types[c], "name": c}, **({"format": "yyyy-MM-dd"} if types[c] == "Date" else {})) for c in cols],
        "dataLakeObjectInfo": {"name": f"${{App.DataLakeObjects.{t['name']}_DLO.Name}}", "label": f"{label_of(t['name'])} DLO {label_suffix}", "category": "OTHER",
                               "dataspaceInfo": [{"name": "default"}],
                               "fields": [{"dataType": types[c], "isPrimaryKey": c == t["pk"], "name": c, "label": label_of(c)} for c in cols]},
        "mappings": [{"sourceFieldLabel": c, "targetFieldName": c} for c in cols],
        "refreshConfig": {"refreshMode": "TOTAL_REPLACE", "frequency": {"frequencyType": "None"}},
        "advancedAttributes": {"importDirectory": f"${{App.CSVs.{t['name']}_CSV.ImportDirectory}}", "fileName": f"${{App.CSVs.{t['name']}_CSV.FileName}}", "delimiter": ",",
                               "parentDirectory": f"${{App.CSVs.{t['name']}_CSV.ParentDirectory}}", "fileType": f"${{App.CSVs.{t['name']}_CSV.FileType}}"},
    }


def sdm_json(name, lob, tables_meta):
    def dim(c, typ):
        return {"apiName": c, "dataObjectFieldName": c + "__c", "dataType": typ, "displayCategory": "Discrete", "isPrimaryKey": False, "isQueryable": "Queryable",
                "isVisible": True, "label": label_of(c), "overriddenProperties": [], "semanticDataType": "None", "sortOrder": "None", "storageDataType": typ}

    def msr(c):
        return {"aggregationType": "Sum", "apiName": c, "dataObjectFieldName": c + "__c", "dataType": "Number", "decimalPlace": 2, "displayCategory": "Continuous",
                "isAggregatable": True, "isPrimaryKey": False, "isQueryable": "Queryable", "isVisible": True, "label": label_of(c), "overriddenProperties": [], "semanticDataType": "None",
                "shouldTreatNullsAsZeros": False, "sortOrder": "None", "storageDataType": "Number"}
    objs = []
    for t, (cols, types, measures) in tables_meta:
        objs.append({"apiName": t["name"], "dataObjectName": f"${{App.DataLakeObjects.{t['name']}_DLO.Name}}", "dataObjectType": "Dlo", "description": f"{label_of(t['name'])} — one row per {label_of(t['pk']).replace(' ID', '').lower()}.",
                     "filters": [], "isQueryable": "Queryable", "label": label_of(t["name"]), "overriddenProperties": [], "primaryNameField": t["pk"],
                     "semanticDimensions": [dim(c, types[c]) for c in cols if c not in measures],
                     "semanticDimensionsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/data-objects/{t['name']}/dimensions",
                     "semanticMeasurements": [msr(c) for c in cols if c in measures],
                     "semanticMeasurementsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/data-objects/{t['name']}/measurements",
                     "shouldIncludeAllFields": True, "tableType": "Standard"})
    rels = [{"apiName": f"{l}_{r}", "cardinality": "ManyToOne", "criteria": [{"joinOperator": "Equals", "leftFieldType": "TableField", "leftSemanticFieldApiName": lf, "rightFieldType": "TableField", "rightSemanticFieldApiName": rf}],
             "isEnabled": True, "isQueryable": "Queryable", "joinType": "Auto", "label": f"{label_of(l)} : {label_of(r)}", "leftSemanticDefinitionApiName": l, "rightSemanticDefinitionApiName": r}
            for (l, lf, r, rf) in lob["relationships"]]
    calcs = [{"aggregationType": "UserAgg", "apiName": api, "dataType": "Number", "decimalPlace": 2, "directionality": "Up", "displayCategory": "Continuous", "expression": expr, "filters": [],
              "isOverrideBase": False, "isQueryable": "Queryable", "isVisible": True, "label": lab, "level": "AggregateFunction", "overriddenProperties": [], "semanticDataType": "None",
              "sentiment": sent, "shouldTreatNullsAsZeros": False, "sortOrder": "None", "totalAggregationType": "Sum"} for (api, lab, expr, sent) in lob["calcs"]]
    metrics = []
    for (api, lab, tbl, fld, agg, tdim, dims, sent) in lob["metrics"]:
        # fld = "calc:<CalculatedMeasureApiName>" references a calculated measure (aggregationType must be UserAgg);
        # otherwise a table measure with Sum/Average/Min/Max.
        if fld.startswith("calc:"):
            ref, agg = {"calculatedFieldApiName": fld[5:]}, "UserAgg"
        else:
            ref = {"tableFieldReference": {"fieldApiName": fld, "tableApiName": tbl}}
        metrics.append({"apiName": api, "label": lab, "description": f"{lab} over time, sliceable by {', '.join(label_of(d) for d in dims)}.",
                        "measurementReference": ref, "aggregationType": agg,
                        "timeDimensionReference": {"tableFieldReference": {"fieldApiName": tdim, "tableApiName": tbl}}, "timeGrains": ["Day", "Week", "Month", "Quarter"],
                        "additionalDimensions": [{"tableFieldReference": {"fieldApiName": d, "tableApiName": tbl}} for d in dims], "insightsSettings": {"sentiment": sent}})
    return {"label": f"{lob['label']} Model ${{Variables.LabelSuffix}}", "agentEnabled": True, "app": "${App.Name}", "dataspace": "default", "categories": [], "currency": {"useOrgDefault": True},
            "fieldsOverrides": [], "hasUnmapped": False, "isLocked": False, "lockedActions": {}, "queryUnrelatedDataObjects": "Union",
            "businessPreferences": f"# {lob['label']} semantic model for the Cumulus Financial Group demo. Synthetic data, 2024-09 to 2026-08.\n# {lob['description']}\n# Ratio measures that divide across objects (e.g. Loss Ratio) should be grouped by dimensions of the denominator object.",
            "semanticCalculatedDimensions": [], "semanticCalculatedDimensionsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/calculated-dimensions",
            "semanticCalculatedMeasurements": calcs, "semanticCalculatedMeasurementsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/calculated-measurements",
            "semanticDataObjects": objs, "semanticDataObjectsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/data-objects",
            "semanticGroupings": [], "semanticGroupingsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/groupings", "semanticLogicalViews": [],
            "semanticMetrics": metrics, "semanticModelFilters": [],
            "semanticModelInfo": {"definitionsCount": len(objs), "maxDefinitionCount": 5000, "modelHierarchyDepth": 1},
            "semanticParameters": [], "semanticParametersUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/parameters",
            "semanticRelationships": rels, "semanticRelationshipsUrl": f"/services/data/v67.0/ssot/semantic/models/{name}_SDM/relationships", "sourceCreation": "Workspace"}


def chain_json(name, lob, tables, viz_files, dash_files):
    nodes = OrderedDict()
    prev = None
    runs = []
    for t in tables:
        n = t["name"]
        nodes[f"upload_{n}"] = {"referenceId": f"upload_{n}", "sources": [prev] if prev else [], "parameters": {"name": f"{n}_CSV", "file": f"csvs/{n}.csv"},
                               "graphNodeType": {"name": "CSVUpsert", "label": "Upload a CSV file"}, "runAs": "CurrentUser"}
        nodes[f"upsert_{n}"] = {"referenceId": f"upsert_{n}", "sources": [f"upload_{n}"], "parameters": {"name": f"{n}_DS", "file": f"datastreams/{n}.json", "dataLakeObject": {"name": f"{n}_DLO"}},
                               "graphNodeType": {"name": "DataStreamUpsert", "label": "Create/Update a DataStream from a Template"}, "runAs": "CurrentUser"}
        nodes[f"run_{n}"] = {"referenceId": f"run_{n}", "sources": [f"upsert_{n}"], "parameters": {"name": f"{n}_DS"},
                            "graphNodeType": {"name": "DataStreamRun", "label": "Refresh a DataStream created from a Template"}, "runAs": "CurrentUser"}
        prev = f"run_{n}"
        runs.append(prev)
    # Settle step. A DataStreamRun reports complete when rows are loaded, but for several minutes afterwards the DLO's
    # field schema is not readable by the semantic-model service ("The [dataType] field is missing" on
    # SemanticModelUpsert). Field-verified: the same SDM body succeeds ~10 min after the last run. Re-running one of the
    # real streams does NOT help (it just makes that DLO fresh again). So the chain ingests a 1-row "clock" stream that
    # no semantic model reads, and runs it twice (~5-6 min each) purely as a delay before the SDM node.
    clock = f"{tables[0]['name'].split('_')[0]}_Clock"
    nodes[f"upload_{clock}"] = {"referenceId": f"upload_{clock}", "sources": [prev], "parameters": {"name": f"{clock}_CSV", "file": f"csvs/{clock}.csv"},
                               "graphNodeType": {"name": "CSVUpsert", "label": "Upload the settle clock CSV"}, "runAs": "CurrentUser"}
    nodes[f"upsert_{clock}"] = {"referenceId": f"upsert_{clock}", "sources": [f"upload_{clock}"], "parameters": {"name": f"{clock}_DS", "file": f"datastreams/{clock}.json", "dataLakeObject": {"name": f"{clock}_DLO"}},
                               "graphNodeType": {"name": "DataStreamUpsert", "label": "Create the settle clock stream"}, "runAs": "CurrentUser"}
    nodes[f"run_{clock}"] = {"referenceId": f"run_{clock}", "sources": [f"upsert_{clock}"], "parameters": {"name": f"{clock}_DS"},
                            "graphNodeType": {"name": "DataStreamRun", "label": "Settle 1: wait for DLO schemas to become readable"}, "runAs": "CurrentUser"}
    nodes[f"settle_{clock}"] = {"referenceId": f"settle_{clock}", "sources": [f"run_{clock}"], "parameters": {"name": f"{clock}_DS"},
                               "graphNodeType": {"name": "DataStreamRun", "label": "Settle 2: wait for DLO schemas to become readable"}, "runAs": "CurrentUser"}
    prev = f"settle_{clock}"
    ws, sdm = f"{name}_WS", f"{name}_SDM"
    nodes["upsert_workspace"] = {"referenceId": "upsert_workspace", "sources": [prev], "parameters": {"name": ws, "label": lob["label"], "file": "workspaces/workspace.json", "condition": "true",
                                                                                                    "assets": [{"name": sdm, "assetType": "SemanticModel", "usageType": "Referenced"}]},
                                 "graphNodeType": {"name": "WorkspaceUpsert", "label": "Create/Update a Workspace from a Template"}, "runAs": "CurrentUser"}
    nodes["upsert_sdm"] = {"referenceId": "upsert_sdm", "sources": ["upsert_workspace"], "parameters": {"name": sdm, "label": f"{lob['label']} Model", "file": "sdms/sdm.json", "condition": "true"},
                           "graphNodeType": {"name": "SemanticModelUpsert", "label": None}, "runAs": "CurrentUser"}
    viz_nodes = []
    for vf in viz_files:
        vn = os.path.splitext(os.path.basename(vf))[0]
        nodes[f"upsert_viz_{vn}"] = {"referenceId": f"upsert_viz_{vn}", "sources": ["upsert_sdm"], "parameters": {"name": vn, "file": f"visualizations/{vn}.json", "condition": "${Variables.CreateDashboard}"},
                                     "graphNodeType": {"name": "VisualizationUpsert", "label": "Create/Update a Visualization from a Template"}, "runAs": "CurrentUser"}
        viz_nodes.append(f"upsert_viz_{vn}")
    for df in dash_files:
        dn = os.path.splitext(os.path.basename(df))[0]
        nodes[f"upsert_dash_{dn}"] = {"referenceId": f"upsert_dash_{dn}", "sources": viz_nodes or ["upsert_sdm"], "parameters": {"name": dn, "label": label_of(dn), "file": f"dashboards/{dn}.json", "condition": "${Variables.CreateDashboard}"},
                                      "graphNodeType": {"name": "DashboardUpsert", "label": "Create/Update a Dashboard from a Template"}, "runAs": "CurrentUser"}
    return {"name": f"{name}_create", "label": f"Create {lob['label']}", "description": None, "parameters": {}, "dominoVariant": "sfdc_internal__UnifiedAnalyticsDominoVariant",
            "definition": {"nodes": nodes}, "finallyDefinition": {"nodes": {}}}


def build_lob(key, out_root):
    name, fn = LOBS[key]
    shared = (index(load("shared", "cumulus_branches"), "BranchId"), index(load("shared", "cumulus_employees"), "EmployeeId"))
    lob = fn(shared)
    out = os.path.join(out_root, name)
    for sub in ("csvs", "datastreams", "sdms", "workspaces"):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
    metas = []
    total_rows = 0
    for t in lob["tables"]:
        cols, types, measures = build_table_meta(t)
        emit_csv(os.path.join(out, "csvs", t["name"] + ".csv"), t["rows"], cols)
        write_json(os.path.join(out, "datastreams", t["name"] + ".json"), datastream_json(t, cols, types))
        metas.append((t, (cols, types, measures)))
        total_rows += len(t["rows"])
    clock = {"name": f"{lob['tables'][0]['name'].split('_')[0]}_Clock", "pk": "Tick", "measures": [], "rows": [{"Tick": "1", "Note": "settle delay for DLO schema propagation"}]}
    ccols, ctypes, _ = build_table_meta(clock)
    emit_csv(os.path.join(out, "csvs", clock["name"] + ".csv"), clock["rows"], ccols)
    write_json(os.path.join(out, "datastreams", clock["name"] + ".json"), datastream_json(clock, ccols, ctypes))
    write_json(os.path.join(out, "sdms", "sdm.json"), sdm_json(name, lob, metas))
    write_json(os.path.join(out, "workspaces", "workspace.json"), {"label": f"{lob['label']} ${{Variables.LabelSuffix}}", "name": f"{name}_WS"})
    write_json(os.path.join(out, "template-policy.json"), {"type": "AccessCheck", "parameters": {"hasTemplateAccess": "always"}})
    write_json(os.path.join(out, "variables.json"), {
        "LabelSuffix": {"label": "Asset Label Suffix", "description": "Appended to every created asset label (useful when installing more than once).", "defaultValue": "", "required": False, "variableType": {"type": "StringType"}},
        "CreateDashboard": {"label": "Create visualizations and dashboard", "description": "Turn off to install only the data and semantic model.", "defaultValue": True, "required": True, "variableType": {"type": "BooleanType"}}})
    write_json(os.path.join(out, "layout.json"), {"displayMessages": [], "pages": [{"type": "Configuration", "title": lob["label"], "layout": {"type": "TwoColumn",
                                                  "header": {"text": f"Installs the {lob['label']} data ({total_rows:,} rows in {len(lob['tables'])} tables), a semantic model with metrics, and the dashboard. Allow ~{6 * len(lob['tables']) + 15} minutes."},
                                                  "left": {"items": [{"type": "Variable", "name": "CreateDashboard", "visibility": "Visible"}]},
                                                  "right": {"items": [{"type": "Variable", "name": "LabelSuffix", "visibility": "Visible"}]}}}]})
    write_json(os.path.join(out, "template-info.json"), {"label": lob["label"], "description": lob["description"], "releaseInfo": {"templateVersion": "1.0", "notesFile": None}, "templateType": "App",
                                                         "templateSubtype": None, "name": name, "namespace": None, "assetVersion": ASSET_VERSION, "maxAppCount": None,
                                                         "icons": {"templatePreviews": [], "layoutImages": []}, "variableDefinition": "variables.json", "layoutDefinition": "layout.json", "tags": {},
                                                         "chainDefinitions": [{"type": "Create", "name": None, "file": "create-chain.json"}], "templateStatus": None})
    vizzes = sorted(os.listdir(os.path.join(out, "visualizations"))) if os.path.isdir(os.path.join(out, "visualizations")) else []
    dashes = sorted(os.listdir(os.path.join(out, "dashboards"))) if os.path.isdir(os.path.join(out, "dashboards")) else []
    write_json(os.path.join(out, "create-chain.json"), chain_json(name, lob, lob["tables"], vizzes, dashes))
    sizes = {t["name"]: os.path.getsize(os.path.join(out, "csvs", t["name"] + ".csv")) for t in lob["tables"]}
    print(f"{name:28s} {len(lob['tables'])} streams, {total_rows:>7,} rows, {sum(sizes.values()) / 1e6:5.1f} MB, {len(vizzes)} viz, {len(dashes)} dashboards")
    return {"name": name, "tables": [t["name"] for t in lob["tables"]], "rows": total_rows, "bytes": sum(sizes.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--lob", help="comma-separated keys (default all)")
    a = ap.parse_args()
    keys = a.lob.split(",") if a.lob else list(LOBS)
    summary = [build_lob(k, a.out) for k in keys]
    print(f"\n{len(summary)} templates → {a.out}")


if __name__ == "__main__":
    main()
