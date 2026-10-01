#!/usr/bin/env python3
"""Validate generated Cumulus data: referential integrity + story anomalies.
Usage: python3 data/validate.py [--out data/out]   (exit 1 on failure)"""
import argparse
import csv
import glob
import os
import statistics
import sys
from collections import defaultdict

FK = {  # (table, column) -> (parent table, pk)
    ("rb_households", "BranchId"): ("cumulus_branches", "BranchId"),
    ("rb_households", "PrimaryBankerId"): ("cumulus_employees", "EmployeeId"),
    ("rb_customers", "HouseholdId"): ("rb_households", "HouseholdId"),
    ("rb_financial_accounts", "HouseholdId"): ("rb_households", "HouseholdId"),
    ("rb_financial_accounts", "PrimaryOwnerId"): ("rb_customers", "CustomerId"),
    ("rb_financial_account_transactions", "FinancialAccountId"): ("rb_financial_accounts", "FinancialAccountId"),
    ("rb_service_cases", "CustomerId"): ("rb_customers", "CustomerId"),
    ("rb_service_cases", "FinancialAccountId"): ("rb_financial_accounts", "FinancialAccountId"),
    ("rb_service_cases", "AgentId"): ("cumulus_employees", "EmployeeId"),
    ("wm_households", "AdvisorId"): ("cumulus_employees", "EmployeeId"),
    ("wm_financial_accounts", "HouseholdId"): ("wm_households", "HouseholdId"),
    ("wm_financial_holdings", "FinancialAccountId"): ("wm_financial_accounts", "FinancialAccountId"),
    ("wm_financial_holdings", "SecurityId"): ("wm_securities", "SecurityId"),
    ("wm_financial_goals", "HouseholdId"): ("wm_households", "HouseholdId"),
    ("wm_interactions", "HouseholdId"): ("wm_households", "HouseholdId"),
    ("wm_net_flows", "HouseholdId"): ("wm_households", "HouseholdId"),
    ("am_mandates", "ClientId"): ("am_clients", "ClientId"),
    ("am_mandate_flows", "MandateId"): ("am_mandates", "MandateId"),
    ("am_financial_deals", "ClientId"): ("am_clients", "ClientId"),
    ("am_service_requests", "ClientId"): ("am_clients", "ClientId"),
    ("ins_policies", "ProducerId"): ("ins_producers", "ProducerId"),
    ("ins_claims", "PolicyId"): ("ins_policies", "PolicyId"),
    ("ins_claims", "AdjusterId"): ("cumulus_employees", "EmployeeId"),
    ("ins_claim_cases", "ClaimId"): ("ins_claims", "ClaimId"),
    ("cb_financial_deals", "BusinessAccountId"): ("cb_business_accounts", "BusinessAccountId"),
    ("cb_credit_facilities", "BusinessAccountId"): ("cb_business_accounts", "BusinessAccountId"),
    ("cb_treasury_enrollments", "BusinessAccountId"): ("cb_business_accounts", "BusinessAccountId"),
    ("cb_referrals", "BusinessAccountId"): ("cb_business_accounts", "BusinessAccountId"),
    ("cb_onboarding", "BusinessAccountId"): ("cb_business_accounts", "BusinessAccountId"),
    ("cb_service_cases", "BusinessAccountId"): ("cb_business_accounts", "BusinessAccountId"),
    ("fa_activities", "ClientHouseholdId"): ("fa_book_of_business", "ClientHouseholdId"),
    ("fa_life_events", "ClientHouseholdId"): ("fa_book_of_business", "ClientHouseholdId"),
    ("fa_financial_goals", "ClientHouseholdId"): ("fa_book_of_business", "ClientHouseholdId"),
    ("fa_referrals", "AdvisorId"): ("cumulus_employees", "EmployeeId"),
    ("ln_stage_events", "ApplicationId"): ("ln_applications", "ApplicationId"),
    ("ln_service_cases", "ApplicationId"): ("ln_applications", "ApplicationId"),
    ("ln_applications", "LoanOfficerId"): ("cumulus_employees", "EmployeeId"),
}


def load(out):
    t = {}
    for p in glob.glob(os.path.join(out, "*", "*.csv")):
        name = os.path.splitext(os.path.basename(p))[0]
        with open(p, newline="", encoding="utf-8") as f:
            t[name] = list(csv.DictReader(f))
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    a = ap.parse_args()
    T = load(a.out)
    fails = 0

    def check(cond, msg):
        nonlocal fails
        print(("PASS  " if cond else "FAIL  ") + msg)
        if not cond:
            fails += 1

    # 1. primary keys unique
    for name, rows in T.items():
        pk = list(rows[0].keys())[0]
        check(len({r[pk] for r in rows}) == len(rows), f"{name}: pk {pk} unique ({len(rows):,} rows)")
    # 2. foreign keys
    for (tbl, col), (ptbl, ppk) in FK.items():
        parents = {r[ppk] for r in T[ptbl]}
        bad = sum(1 for r in T[tbl] if r[col] and r[col] not in parents)
        check(bad == 0, f"{tbl}.{col} -> {ptbl}.{ppk} ({bad} orphans)")
    # 3. story anomalies
    cs = T["rb_service_cases"]
    spike = [r for r in cs if r["BranchId"] in ("BR-003", "BR-011") and r["CreatedDate"] >= "2026-05"]
    other = [r for r in cs if r["BranchId"] not in ("BR-003", "BR-011") and r["CreatedDate"] >= "2026-05"]
    share = lambda rows: sum(1 for r in rows if r["CaseType"] in ("Card Dispute", "Fee Inquiry")) / max(1, len(rows))
    check(share(spike) > share(other) * 1.3, f"Retail dispute/fee share spike: {share(spike):.0%} vs {share(other):.0%}")
    check(any(r["CustomerId"] == "RB-C-00001-1" and r["CaseType"] == "Card Dispute" for r in cs), "Lauren Bailey dispute case present")
    wh = {r["HouseholdId"]: r for r in T["wm_households"]}
    ic = defaultdict(int)
    for r in T["wm_interactions"]:
        ic[r["HouseholdId"]] += 1
    churn = statistics.mean(ic[h] for h, r in wh.items() if r["Churned"] == "true")
    keep = statistics.mean(ic[h] for h, r in wh.items() if r["Churned"] == "false")
    check(keep > churn * 2, f"Wealth churned households interact less: {churn:.1f} vs {keep:.1f} per 2y")
    check(any(r["HouseholdId"] == "WM-HH-00001" and float(r["NetFlow"]) == 40000000 for r in T["wm_net_flows"]), "Ashford $40M inflow present")
    sr = [r for r in T["am_service_requests"] if r["RequestType"] == "Reconciliation" and r["CycleTimeDays"]]
    qe = [float(r["CycleTimeDays"]) for r in sr if r["CreatedDate"][5:7] in ("01", "04", "07", "10") and int(r["CreatedDate"][8:10]) <= 12]
    nq = [float(r["CycleTimeDays"]) for r in sr if not (r["CreatedDate"][5:7] in ("01", "04", "07", "10") and int(r["CreatedDate"][8:10]) <= 12)]
    check(statistics.mean(qe) > statistics.mean(nq) * 1.5, f"AM quarter-end reconciliation cycle time: {statistics.mean(qe):.1f}d vs {statistics.mean(nq):.1f}d")
    cl = [r for r in T["ins_claims"] if r["CycleTimeDays"]]
    hail = [float(r["CycleTimeDays"]) for r in cl if r["CatastropheCode"]]
    non = [float(r["CycleTimeDays"]) for r in cl if not r["CatastropheCode"]]
    check(len(hail) > 50 and statistics.mean(hail) > statistics.mean(non) * 1.2, f"Insurance hail CAT cycle time: {statistics.mean(hail):.1f}d ({len(hail)} claims) vs {statistics.mean(non):.1f}d")
    ob = T["cb_onboarding"]
    wt = statistics.mean(float(r["CycleTimeDays"]) for r in ob if r["HasTreasuryProducts"] == "true")
    wo = statistics.mean(float(r["CycleTimeDays"]) for r in ob if r["HasTreasuryProducts"] == "false")
    check(wo > wt * 1.6, f"Commercial onboarding without treasury: {wo:.1f}d vs {wt:.1f}d")
    le = T["fa_life_events"]
    miss = sum(1 for r in le if r["FollowUpWithin14Days"] == "false") / len(le)
    check(0.22 <= miss <= 0.38, f"Advisors life events without 14-day follow-up: {miss:.0%}")
    se = [r for r in T["ln_stage_events"] if r["DaysInStage"]]
    tot = sum(float(r["DaysInStage"]) for r in se)
    doc = sum(float(r["DaysInStage"]) for r in se if r["StageName"] == "Document Collection")
    check(0.45 <= doc / tot <= 0.65, f"Lending document collection share of cycle: {doc / tot:.0%}")
    print(f"\n{'ALL CHECKS PASSED' if fails == 0 else str(fails) + ' CHECK(S) FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
