#!/usr/bin/env python3
"""
Cumulus Financial Group — synthetic data generator for Tableau Next demos.

Deterministic (seeded). Writes one CSV per table into data/out/<lob>/, a data
dictionary (data/DATA_DICTIONARY.md) and a Data 360 Ingestion API schema
(data/ingestion/cumulus_schema.yaml).

Seven lines of business, one fictional group, storylines aligned with the
A4S Guided FinServ demo (Lauren Bailey, Jonathan Ashford III, PayCadence,
Elena Ruiz, Meridian Logistics).

Usage:  python3 data/generate.py [--seed 42] [--scale 1.0] [--out data/out]
"""
import argparse
import csv
import datetime as dt
import math
import os
import random
from collections import OrderedDict

# --------------------------------------------------------------------------
# Globals / helpers
# --------------------------------------------------------------------------
TODAY = dt.date(2026, 8, 31)                # last day of the 24-month window
START = dt.date(2024, 9, 1)
DAYS = (TODAY - START).days + 1
R = random.Random(42)
SCALE = 1.0

SCHEMA = OrderedDict()   # table -> OrderedDict(column -> type)   (types: text|number|dateTime|date|boolean)
LOB_OF = {}              # table -> lob folder
PRIMARY_KEYS = {}        # table -> pk column


def reg(lob, table, columns, pk):
    """Register a table schema. columns = [(name, type), ...]"""
    SCHEMA[table] = OrderedDict(columns)
    LOB_OF[table] = lob
    PRIMARY_KEYS[table] = pk


def n(x):
    return max(1, int(round(x * SCALE)))


def rdate(a=START, b=TODAY):
    return a + dt.timedelta(days=R.randint(0, (b - a).days))


def rdt(date):
    return dt.datetime(date.year, date.month, date.day, R.randint(7, 19), R.randint(0, 59), R.randint(0, 59))


def iso(d):
    if isinstance(d, dt.datetime):
        return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return d.isoformat()


def months():
    m = []
    d = dt.date(START.year, START.month, 1)
    while d <= TODAY:
        m.append(d)
        d = dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return m


MONTHS = months()


def month_end(d):
    nxt = dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return nxt - dt.timedelta(days=1)


def pick(seq, weights=None):
    if weights:
        return R.choices(seq, weights=weights, k=1)[0]
    return R.choice(seq)


def money(lo, hi, dec=2):
    return round(R.uniform(lo, hi), dec)


def lognorm(mean, sigma, lo=None, hi=None):
    v = R.lognormvariate(math.log(mean), sigma)
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


FIRST = ["Lauren", "Derek", "Jonathan", "Elena", "Marcus", "Priya", "Sofia", "Daniel", "Aisha", "Tom", "Grace", "Wei",
         "Carlos", "Naomi", "Ethan", "Olivia", "Hannah", "Luis", "Maya", "Noah", "Isabella", "Jamal", "Chloe", "Ravi",
         "Emma", "Leo", "Zara", "Owen", "Fatima", "Henry", "Mei", "Andre", "Nora", "Samuel", "Ines", "Kenji", "Ava",
         "Mateo", "Layla", "Julian", "Rosa", "Victor", "Amara", "Felix", "Iris", "Diego", "Sara", "Ben", "Yuki", "Nina"]
LAST = ["Bailey", "Vaughn", "Ashford", "Ruiz", "Chen", "Patel", "Nguyen", "Okafor", "Kim", "Silva", "Brown", "Garcia",
        "Johnson", "Miller", "Davis", "Martinez", "Lopez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson",
        "White", "Harris", "Clark", "Lewis", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Scott", "Green",
        "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Roberts", "Turner", "Phillips", "Campbell", "Parker",
        "Evans", "Edwards", "Collins", "Stewart", "Morris"]
REGIONS = ["Northeast", "Southeast", "Midwest", "Mountain West", "Pacific"]
STATES = {"Northeast": ["NY", "MA", "CT"], "Southeast": ["FL", "GA", "NC"], "Midwest": ["IL", "OH", "MN"],
          "Mountain West": ["CO", "UT", "AZ"], "Pacific": ["CA", "WA", "OR"]}


def person():
    return pick(FIRST), pick(LAST)


def writer(out_root, table, rows):
    lob = LOB_OF[table]
    d = os.path.join(out_root, lob)
    os.makedirs(d, exist_ok=True)
    cols = list(SCHEMA[table].keys())
    path = os.path.join(d, f"{table}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return path, len(rows)


# --------------------------------------------------------------------------
# Shared reference: Cumulus org structure
# --------------------------------------------------------------------------
def gen_shared():
    branches = []
    bid = 1
    for reg_ in REGIONS:
        for st in STATES[reg_]:
            for k in range(2):
                branches.append({"BranchId": f"BR-{bid:03d}", "BranchName": f"Cumulus {st} Branch {k + 1}",
                                 "Region": reg_, "State": st, "BranchType": pick(["Full Service", "Full Service", "Advisory", "Digital Hub"])})
                bid += 1
    reg("shared", "cumulus_branches", [("BranchId", "text"), ("BranchName", "text"), ("Region", "text"), ("State", "text"), ("BranchType", "text")], "BranchId")

    employees = []
    roles = [("Banker", 60), ("Service Agent", 80), ("Advisor", 40), ("Relationship Manager", 25), ("Loan Officer", 30),
             ("Claims Adjuster", 30), ("Client Service Associate", 25), ("Supervisor", 20)]
    eid = 1
    for role, cnt in roles:
        for _ in range(n(cnt)):
            f, l = person()
            employees.append({"EmployeeId": f"E-{eid:04d}", "EmployeeName": f"{f} {l}", "Role": role,
                              "BranchId": pick(branches)["BranchId"], "HireDate": iso(rdate(dt.date(2015, 1, 1), dt.date(2026, 3, 1))),
                              "Team": pick(["Team Alpha", "Team Bravo", "Team Charlie", "Team Delta"])})
            eid += 1
    reg("shared", "cumulus_employees", [("EmployeeId", "text"), ("EmployeeName", "text"), ("Role", "text"), ("BranchId", "text"), ("HireDate", "date"), ("Team", "text")], "EmployeeId")
    return branches, employees


def by_role(employees, role):
    return [e for e in employees if e["Role"] == role]


# --------------------------------------------------------------------------
# 1. Retail Banking
# --------------------------------------------------------------------------
def gen_retail(branches, employees):
    lob = "retail_banking"
    bankers = by_role(employees, "Banker")
    agents = by_role(employees, "Service Agent")
    households, customers, accounts, txns, cases = [], [], [], [], []

    # Story anchor: Lauren Bailey
    hh_count = n(2500)
    for i in range(1, hh_count + 1):
        br = pick(branches)
        seg = pick(["Mass Market", "Mass Affluent", "Premier", "Student"], [55, 28, 12, 5])
        hh = {"HouseholdId": f"RB-HH-{i:05d}", "HouseholdName": "", "Segment": seg, "BranchId": br["BranchId"],
              "PrimaryBankerId": pick(bankers)["EmployeeId"], "RelationshipStartDate": iso(rdate(dt.date(2012, 1, 1), dt.date(2026, 6, 30))),
              "DigitalActive": pick(["true", "false"], [68, 32]), "NPS": R.randint(-100, 100) if R.random() < 0.4 else ""}
        members = 1 if R.random() < 0.55 else 2
        lastname = pick(LAST)
        for m in range(members):
            f = pick(FIRST)
            cid = f"RB-C-{i:05d}-{m + 1}"
            if i == 1:
                f, lastname = "Lauren", "Bailey"
            customers.append({"CustomerId": cid, "HouseholdId": hh["HouseholdId"], "FirstName": f, "LastName": lastname,
                              "Age": R.randint(19, 82), "IsPrimary": "true" if m == 0 else "false",
                              "PreferredChannel": pick(["Mobile App", "Web", "Phone", "Branch"], [45, 25, 18, 12])})
        hh["HouseholdName"] = f"{lastname} Household"
        households.append(hh)
        # accounts: 1-4 per household
        n_acc = pick([1, 2, 3, 4], [25, 40, 25, 10])
        types = R.sample(["Checking", "Savings", "Credit Card", "CD", "Money Market"], n_acc) if n_acc <= 5 else []
        if "Checking" not in types:
            types[0] = "Checking"
        for t in types:
            aid = f"RB-FA-{len(accounts) + 1:06d}"
            bal = {"Checking": lognorm(4200, 0.9, 0, 250000), "Savings": lognorm(12000, 1.0, 0, 900000),
                   "Credit Card": -lognorm(1800, 0.8, 0, 25000), "CD": lognorm(25000, 0.6, 1000, 500000),
                   "Money Market": lognorm(40000, 0.7, 2500, 1500000)}[t]
            if seg == "Premier":
                bal *= 3.5
            accounts.append({"FinancialAccountId": aid, "HouseholdId": hh["HouseholdId"], "PrimaryOwnerId": customers[-members]["CustomerId"],
                             "FinancialAccountType": t, "Status": pick(["Open", "Open", "Open", "Closed", "On Hold"], [80, 10, 5, 4, 1]),
                             "OpenDate": iso(rdate(dt.date(2012, 1, 1), dt.date(2026, 7, 31))), "Balance": round(bal, 2),
                             "BranchId": br["BranchId"], "ProductName": f"Cumulus {t}"})
    # Lauren's checking account is the dispute account
    lauren_acc = [a for a in accounts if a["HouseholdId"] == "RB-HH-00001" and a["FinancialAccountType"] == "Checking"][0]

    # transactions (~ 8 per open account)
    merchants = [("Amazon Marketplace", "Retail"), ("Whole Foods", "Grocery"), ("Shell", "Fuel"), ("Netflix", "Subscriptions"),
                 ("Delta Air Lines", "Travel"), ("Starbucks", "Dining"), ("Home Depot", "Home"), ("Payroll Deposit", "Income"),
                 ("Zelle Transfer", "Transfer"), ("Cumulus Mortgage Pmt", "Loan Payment"), ("Uber", "Transport"), ("CVS", "Health")]
    tid = 1
    for a in accounts:
        if a["Status"] != "Open":
            continue
        for _ in range(R.randint(3, 14)):
            m, cat = pick(merchants)
            amt = lognorm(60, 1.1, 1, 5000)
            ttype = "Credit" if cat in ("Income", "Transfer") and R.random() < 0.7 else "Debit"
            txns.append({"TransactionId": f"RB-TX-{tid:07d}", "FinancialAccountId": a["FinancialAccountId"], "TransactionDate": iso(rdt(rdate())),
                         "Amount": round(amt if ttype == "Credit" else -amt, 2), "TransactionType": ttype, "Merchant": m,
                         "Category": cat, "Channel": pick(["Card", "ACH", "Wire", "ATM", "Mobile"], [55, 20, 5, 10, 10]), "IsDisputed": "false"})
            tid += 1
    # Lauren's $75 Amazon charge that overdrafted the account (2026-08-18)
    txns.append({"TransactionId": f"RB-TX-{tid:07d}", "FinancialAccountId": lauren_acc["FinancialAccountId"], "TransactionDate": "2026-08-18T14:22:10.000Z",
                 "Amount": -75.00, "TransactionType": "Debit", "Merchant": "Amazon Marketplace", "Category": "Retail", "Channel": "Card", "IsDisputed": "true"})
    tid += 1

    # cases — story: card-dispute spike in BR-003 and BR-011 from May 2026 (fee change)
    case_types = [("Card Dispute", ["Unrecognized Charge", "Duplicate Charge", "Merchant Refund"]),
                  ("Fee Inquiry", ["Overdraft Fee", "Monthly Maintenance", "ATM Fee"]),
                  ("Account Access", ["Password Reset", "Locked Account", "MFA"]),
                  ("Fraud", ["Card Compromised", "Account Takeover"]),
                  ("Product Question", ["Rates", "Eligibility"]),
                  ("Payments", ["Failed Transfer", "Wire Status", "Bill Pay"])]
    spike_branches = {"BR-003", "BR-011"}
    cid_n = 1
    for a in accounts:
        cust = a["PrimaryOwnerId"]
        k = R.random()
        n_cases = 0 if k < 0.45 else (1 if k < 0.8 else R.randint(2, 4))
        for _ in range(n_cases):
            d = rdate()
            ctype, subs = pick(case_types, [22, 20, 25, 8, 12, 13])
            if a["BranchId"] in spike_branches and d >= dt.date(2026, 5, 1) and R.random() < 0.55:
                ctype, subs = case_types[0]
                if R.random() < 0.5:
                    ctype, subs = case_types[1]
            channel = pick(["Voice", "Chat", "Email", "Mobile App", "Branch"], [35, 28, 15, 15, 7])
            handle = lognorm(11 if channel != "Email" else 25, 0.5, 2, 120)
            fcr = "true" if R.random() < (0.72 if ctype != "Card Dispute" else 0.48) else "false"
            closed = d + dt.timedelta(days=(0 if fcr == "true" else R.randint(1, 21)))
            status = "Closed" if closed <= TODAY and R.random() < 0.9 else pick(["Open", "In Progress", "Escalated"])
            csat = R.randint(1, 5) if R.random() < 0.55 else ""
            if csat and fcr == "true" and csat < 3 and R.random() < 0.7:
                csat = R.randint(4, 5)
            cases.append({"CaseId": f"RB-CS-{cid_n:06d}", "CustomerId": cust, "FinancialAccountId": a["FinancialAccountId"],
                          "CreatedDate": iso(rdt(d)), "ClosedDate": iso(rdt(closed)) if status == "Closed" else "",
                          "Channel": channel, "CaseType": ctype, "SubType": pick(subs), "Status": status, "Priority": pick(["Low", "Medium", "High"], [50, 38, 12]),
                          "FirstContactResolution": fcr, "CSAT": csat, "HandleTimeMinutes": round(handle, 1),
                          "BranchId": a["BranchId"], "AgentId": pick(agents)["EmployeeId"], "AgentforceHandled": pick(["true", "false"], [38, 62])})
            cid_n += 1
    # Lauren's dispute case (the A4S storyline), handled by Agentforce Voice then warm-transferred
    cases.append({"CaseId": f"RB-CS-{cid_n:06d}", "CustomerId": "RB-C-00001-1", "FinancialAccountId": lauren_acc["FinancialAccountId"],
                  "CreatedDate": "2026-08-19T09:14:00.000Z", "ClosedDate": "2026-08-19T09:41:00.000Z", "Channel": "Voice", "CaseType": "Card Dispute",
                  "SubType": "Unrecognized Charge", "Status": "Closed", "Priority": "High", "FirstContactResolution": "true", "CSAT": 5,
                  "HandleTimeMinutes": 27.0, "BranchId": lauren_acc["BranchId"], "AgentId": pick(agents)["EmployeeId"], "AgentforceHandled": "true"})

    reg(lob, "rb_households", [("HouseholdId", "text"), ("HouseholdName", "text"), ("Segment", "text"), ("BranchId", "text"), ("PrimaryBankerId", "text"),
                               ("RelationshipStartDate", "date"), ("DigitalActive", "boolean"), ("NPS", "number")], "HouseholdId")
    reg(lob, "rb_customers", [("CustomerId", "text"), ("HouseholdId", "text"), ("FirstName", "text"), ("LastName", "text"), ("Age", "number"),
                              ("IsPrimary", "boolean"), ("PreferredChannel", "text")], "CustomerId")
    reg(lob, "rb_financial_accounts", [("FinancialAccountId", "text"), ("HouseholdId", "text"), ("PrimaryOwnerId", "text"), ("FinancialAccountType", "text"),
                                       ("Status", "text"), ("OpenDate", "date"), ("Balance", "number"), ("BranchId", "text"), ("ProductName", "text")], "FinancialAccountId")
    reg(lob, "rb_financial_account_transactions", [("TransactionId", "text"), ("FinancialAccountId", "text"), ("TransactionDate", "dateTime"), ("Amount", "number"),
                                                   ("TransactionType", "text"), ("Merchant", "text"), ("Category", "text"), ("Channel", "text"), ("IsDisputed", "boolean")], "TransactionId")
    reg(lob, "rb_service_cases", [("CaseId", "text"), ("CustomerId", "text"), ("FinancialAccountId", "text"), ("CreatedDate", "dateTime"), ("ClosedDate", "dateTime"),
                                  ("Channel", "text"), ("CaseType", "text"), ("SubType", "text"), ("Status", "text"), ("Priority", "text"), ("FirstContactResolution", "boolean"),
                                  ("CSAT", "number"), ("HandleTimeMinutes", "number"), ("BranchId", "text"), ("AgentId", "text"), ("AgentforceHandled", "boolean")], "CaseId")
    return {"rb_households": households, "rb_customers": customers, "rb_financial_accounts": accounts,
            "rb_financial_account_transactions": txns, "rb_service_cases": cases}


# --------------------------------------------------------------------------
# 2. Wealth Management
# --------------------------------------------------------------------------
SECURITIES = [("VTI", "Vanguard Total Stock Market ETF", "Equity", 275.0), ("BND", "Vanguard Total Bond ETF", "Fixed Income", 73.0),
              ("VXUS", "Vanguard Intl Stock ETF", "Equity", 64.0), ("VNQ", "Vanguard Real Estate ETF", "Real Assets", 90.0),
              ("SGOV", "iShares 0-3 Mo Treasury", "Cash", 100.5), ("AAPL", "Apple Inc.", "Equity", 232.0), ("MSFT", "Microsoft Corp.", "Equity", 445.0),
              ("CUMX", "Cumulus Balanced Fund", "Multi-Asset", 18.4), ("CUMI", "Cumulus Income Fund", "Fixed Income", 11.2),
              ("GLD", "SPDR Gold Shares", "Alternatives", 250.0), ("PRIV1", "Cumulus Private Credit I", "Alternatives", 1000.0)]


def gen_wealth(branches, employees):
    lob = "wealth"
    advisors = by_role(employees, "Advisor")
    hh, accts, holdings, goals, inter, flows, secs = [], [], [], [], [], [], []
    for i, (sym, name, cls, px) in enumerate(SECURITIES, 1):
        secs.append({"SecurityId": f"SEC-{i:03d}", "Symbol": sym, "SecurityName": name, "AssetClass": cls, "CurrentPrice": px})
    hh_count = n(900)
    for i in range(1, hh_count + 1):
        adv = pick(advisors)
        risk = pick(["Conservative", "Moderate", "Growth", "Aggressive"], [20, 40, 30, 10])
        tier = pick(["Core", "Premier", "Private Wealth"], [60, 30, 10])
        aum = lognorm({"Core": 350000, "Premier": 1800000, "Private Wealth": 9000000}[tier], 0.7, 50000, 60000000)
        f, l = person()
        if i == 1:
            f, l, tier, aum, risk = "Jonathan", "Ashford", "Private Wealth", 40000000, "Growth"
        start = rdate(dt.date(2010, 1, 1), dt.date(2026, 7, 1)) if i != 1 else dt.date(2026, 7, 14)
        churned = "true" if R.random() < 0.06 and i != 1 else "false"
        h = {"HouseholdId": f"WM-HH-{i:05d}", "HouseholdName": f"{l} Family" if i != 1 else "Ashford Family Office", "PrimaryClientName": f"{f} {l}" + (" III" if i == 1 else ""),
             "AdvisorId": adv["EmployeeId"], "BranchId": adv["BranchId"], "ServiceTier": tier, "RiskProfile": risk, "RelationshipStartDate": iso(start),
             "AUM": round(aum, 2), "Churned": churned, "ChurnDate": iso(rdate(dt.date(2025, 6, 1))) if churned == "true" else "",
             "AnnualRevenue": round(aum * R.uniform(0.006, 0.011), 2)}
        hh.append(h)
        n_acc = pick([1, 2, 3], [40, 40, 20]) if i != 1 else 3
        acct_types = R.sample(["Brokerage", "Traditional IRA", "Roth IRA", "Trust", "529 Plan"], n_acc)
        if i == 1:
            acct_types = ["Brokerage", "Traditional IRA", "Trust"]
        split = [R.random() for _ in acct_types]
        tot = sum(split)
        for t, s in zip(acct_types, split):
            aid = f"WM-FA-{len(accts) + 1:06d}"
            val = aum * s / tot
            accts.append({"FinancialAccountId": aid, "HouseholdId": h["HouseholdId"], "FinancialAccountType": t, "Custodian": pick(["Cumulus Custody", "Fidelity", "Schwab", "JP Morgan"], [70, 10, 10, 10]) if i != 1 else pick(["Fidelity", "Schwab", "JP Morgan"]),
                          "Status": "Open" if churned == "false" else "Closed", "OpenDate": iso(start), "MarketValue": round(val, 2), "ProductName": f"Cumulus {t}"})
            # holdings snapshot (as of TODAY)
            weights = {"Conservative": [15, 45, 10, 5, 15, 2, 2, 3, 3, 0, 0], "Moderate": [30, 30, 12, 5, 5, 4, 4, 5, 3, 2, 0],
                       "Growth": [38, 15, 15, 5, 2, 8, 8, 4, 0, 3, 2], "Aggressive": [40, 5, 18, 5, 0, 12, 12, 2, 0, 2, 4]}[risk]
            for (sec, w) in zip(secs, weights):
                if w == 0 or R.random() < 0.25:
                    continue
                mv = val * w / 100 * R.uniform(0.7, 1.3)
                shares = mv / sec["CurrentPrice"]
                holdings.append({"HoldingId": f"WM-HD-{len(holdings) + 1:07d}", "FinancialAccountId": aid, "SecurityId": sec["SecurityId"], "Symbol": sec["Symbol"],
                                 "AssetClass": sec["AssetClass"], "Shares": round(shares, 3), "Price": sec["CurrentPrice"], "MarketValue": round(mv, 2),
                                 "CostBasis": round(mv * R.uniform(0.6, 1.1), 2), "AsOfDate": iso(TODAY)})
        # goals
        for _ in range(pick([0, 1, 2, 3], [20, 40, 30, 10])):
            gt = pick(["Retirement", "Education", "Home Purchase", "Legacy", "Major Purchase"])
            target = lognorm(600000 if gt == "Retirement" else 150000, 0.7, 10000)
            prog = R.uniform(0.05, 1.1)
            goals.append({"GoalId": f"WM-GL-{len(goals) + 1:06d}", "HouseholdId": h["HouseholdId"], "GoalType": gt, "GoalName": f"{gt} — {l}",
                          "TargetValue": round(target, 2), "ActualValue": round(target * prog, 2), "TargetDate": iso(rdate(dt.date(2027, 1, 1), dt.date(2045, 12, 31))),
                          "Status": "Completed" if prog >= 1 else pick(["On Track", "At Risk", "Off Track"], [55, 30, 15])})
        # interactions — story: households with < 2 interactions/quarter churn ~3x more
        base = 1.2 if churned == "true" else 4.5
        for _ in range(int(max(0, R.gauss(base * 8, 4)))):
            d = rdate()
            inter.append({"InteractionId": f"WM-IN-{len(inter) + 1:07d}", "HouseholdId": h["HouseholdId"], "AdvisorId": adv["EmployeeId"], "InteractionDate": iso(rdt(d)),
                          "InteractionType": pick(["Review Meeting", "Call", "Email", "Event", "Planning Session"], [25, 35, 25, 5, 10]),
                          "DurationMinutes": R.randint(5, 90), "Sentiment": pick(["Positive", "Neutral", "Negative"], [60, 32, 8]),
                          "SummaryGeneratedByAI": pick(["true", "false"], [45, 55])})
        # monthly net flows
        for m in MONTHS:
            if m < dt.date(start.year, start.month, 1):
                continue
            if churned == "true" and R.random() < 0.3:
                fl = -aum * R.uniform(0.02, 0.1)
            else:
                fl = R.gauss(aum * 0.004, aum * 0.02)
            if i == 1 and m == dt.date(2026, 7, 1):
                fl = 40000000
            flows.append({"FlowId": f"WM-FL-{len(flows) + 1:07d}", "HouseholdId": h["HouseholdId"], "AdvisorId": adv["EmployeeId"], "FlowMonth": iso(m),
                          "NetFlow": round(fl, 2), "Inflow": round(max(fl, 0) + abs(R.gauss(0, aum * 0.005)), 2), "Outflow": round(max(-fl, 0) + abs(R.gauss(0, aum * 0.005)), 2)})
    reg(lob, "wm_securities", [("SecurityId", "text"), ("Symbol", "text"), ("SecurityName", "text"), ("AssetClass", "text"), ("CurrentPrice", "number")], "SecurityId")
    reg(lob, "wm_households", [("HouseholdId", "text"), ("HouseholdName", "text"), ("PrimaryClientName", "text"), ("AdvisorId", "text"), ("BranchId", "text"), ("ServiceTier", "text"),
                               ("RiskProfile", "text"), ("RelationshipStartDate", "date"), ("AUM", "number"), ("Churned", "boolean"), ("ChurnDate", "date"), ("AnnualRevenue", "number")], "HouseholdId")
    reg(lob, "wm_financial_accounts", [("FinancialAccountId", "text"), ("HouseholdId", "text"), ("FinancialAccountType", "text"), ("Custodian", "text"), ("Status", "text"),
                                       ("OpenDate", "date"), ("MarketValue", "number"), ("ProductName", "text")], "FinancialAccountId")
    reg(lob, "wm_financial_holdings", [("HoldingId", "text"), ("FinancialAccountId", "text"), ("SecurityId", "text"), ("Symbol", "text"), ("AssetClass", "text"), ("Shares", "number"),
                                       ("Price", "number"), ("MarketValue", "number"), ("CostBasis", "number"), ("AsOfDate", "date")], "HoldingId")
    reg(lob, "wm_financial_goals", [("GoalId", "text"), ("HouseholdId", "text"), ("GoalType", "text"), ("GoalName", "text"), ("TargetValue", "number"), ("ActualValue", "number"),
                                    ("TargetDate", "date"), ("Status", "text")], "GoalId")
    reg(lob, "wm_interactions", [("InteractionId", "text"), ("HouseholdId", "text"), ("AdvisorId", "text"), ("InteractionDate", "dateTime"), ("InteractionType", "text"),
                                 ("DurationMinutes", "number"), ("Sentiment", "text"), ("SummaryGeneratedByAI", "boolean")], "InteractionId")
    reg(lob, "wm_net_flows", [("FlowId", "text"), ("HouseholdId", "text"), ("AdvisorId", "text"), ("FlowMonth", "date"), ("NetFlow", "number"), ("Inflow", "number"), ("Outflow", "number")], "FlowId")
    return {"wm_securities": secs, "wm_households": hh, "wm_financial_accounts": accts, "wm_financial_holdings": holdings,
            "wm_financial_goals": goals, "wm_interactions": inter, "wm_net_flows": flows}


# --------------------------------------------------------------------------
# 3. Asset Management (institutional)
# --------------------------------------------------------------------------
def gen_asset_mgmt(branches, employees):
    lob = "asset_management"
    csas = by_role(employees, "Client Service Associate")
    rms = by_role(employees, "Relationship Manager")
    strategies = [("Core Fixed Income", 0.0035), ("US Large Cap Equity", 0.0045), ("Global Equity", 0.006), ("Private Credit", 0.012),
                  ("Real Assets", 0.009), ("Multi-Asset Balanced", 0.005), ("Liability-Driven Investing", 0.003), ("ESG Equity", 0.0055)]
    clients, mandates, flows, deals, reqs = [], [], [], [], []
    for i in range(1, n(140) + 1):
        ctype = pick(["Public Pension", "Corporate Pension", "Endowment", "Foundation", "Insurance GA", "Sovereign", "Sub-Advisory", "Family Office"])
        name = pick(["Northfield", "Harbor", "Summit", "Granite", "Blue Ridge", "Lakeshore", "Meridian", "Ironwood", "Silverline", "Cascade"]) + " " + \
            pick(["Teachers Retirement", "Employees Pension", "University Endowment", "Community Foundation", "Mutual Insurance", "Capital Partners", "Sovereign Fund"])
        clients.append({"ClientId": f"AM-CL-{i:04d}", "ClientName": f"{name} {i}", "ClientType": ctype, "Region": pick(REGIONS + ["EMEA", "APAC"]),
                        "RelationshipManagerId": pick(rms)["EmployeeId"], "ServiceAssociateId": pick(csas)["EmployeeId"],
                        "OnboardedDate": iso(rdate(dt.date(2008, 1, 1), dt.date(2026, 6, 1))), "ClientTier": pick(["Strategic", "Key", "Standard"], [15, 35, 50])})
        for _ in range(pick([1, 2, 3, 4], [40, 35, 18, 7])):
            strat, fee = pick(strategies)
            aum = lognorm(180e6, 1.0, 5e6, 6e9)
            mid = f"AM-MD-{len(mandates) + 1:05d}"
            mandates.append({"MandateId": mid, "ClientId": clients[-1]["ClientId"], "Strategy": strat, "Vehicle": pick(["Separate Account", "Commingled Fund", "Mutual Fund", "LP"]),
                             "AUM": round(aum, 2), "FeeRateBps": round(fee * 10000, 1), "InceptionDate": iso(rdate(dt.date(2008, 1, 1), dt.date(2026, 6, 1))),
                             "Benchmark": pick(["Bloomberg US Agg", "S&P 500", "MSCI ACWI", "CPI+4%", "60/40 Blend"]), "Status": pick(["Active", "Active", "Active", "In Transition", "Terminated"])})
            for m in MONTHS:
                nf = R.gauss(aum * 0.002, aum * 0.015)
                perf = R.gauss(0.004, 0.025)
                flows.append({"FlowId": f"AM-FL-{len(flows) + 1:07d}", "MandateId": mid, "ClientId": clients[-1]["ClientId"], "FlowMonth": iso(m), "NetFlow": round(nf, 2),
                              "MarketReturnPct": round(perf * 100, 3), "EndingAUM": round(aum * (1 + perf) + nf, 2)})
    stages = ["Prospecting", "RFP Received", "Finals Presentation", "Due Diligence", "Closed Won", "Closed Lost"]
    for i in range(1, n(220) + 1):
        c = pick(clients)
        st = pick(stages, [20, 22, 15, 13, 18, 12])
        created = rdate(dt.date(2025, 1, 1))
        deals.append({"DealId": f"AM-DL-{i:05d}", "DealName": f"{c['ClientName']} — {pick(strategies)[0]}", "ClientId": c["ClientId"], "Stage": st,
                      "Amount": round(lognorm(120e6, 0.9, 5e6, 3e9), 2), "CreatedDate": iso(created), "CloseDate": iso(created + dt.timedelta(days=R.randint(60, 400))),
                      "OwnerId": pick(rms)["EmployeeId"], "Source": pick(["Consultant", "Direct", "Existing Client", "RFP Database"]), "IsWon": "true" if st == "Closed Won" else "false"})
    rtypes = [("Performance Report", 5), ("Reconciliation", 3), ("Cash Movement", 1), ("Compliance Attestation", 10), ("Fee Invoice Question", 5), ("Data Feed Issue", 2), ("Onboarding Document", 7)]
    for i in range(1, n(3200) + 1):
        c = pick(clients)
        rt, sla = pick(rtypes, [30, 22, 12, 8, 12, 8, 8])
        created = rdate()
        qe = created.month in (1, 4, 7, 10) and created.day <= 12
        dur = lognorm(sla * 0.75, 0.6, 0.1)
        if rt == "Reconciliation" and qe:
            dur *= 2.4   # story: quarter-end reconciliation breaches SLA
        closed = created + dt.timedelta(days=dur)
        status = "Closed" if closed <= TODAY else pick(["Open", "In Progress"])
        reqs.append({"RequestId": f"AM-SR-{i:06d}", "ClientId": c["ClientId"], "AssociateId": c["ServiceAssociateId"], "RequestType": rt, "CreatedDate": iso(rdt(created)),
                     "ClosedDate": iso(rdt(closed)) if status == "Closed" else "", "Status": status, "SLADays": sla, "CycleTimeDays": round(dur, 2) if status == "Closed" else "",
                     "SLABreached": "true" if dur > sla else "false", "Channel": pick(["Email", "Portal", "Phone"], [55, 35, 10]), "Priority": pick(["Low", "Medium", "High"], [40, 45, 15])})
    reg(lob, "am_clients", [("ClientId", "text"), ("ClientName", "text"), ("ClientType", "text"), ("Region", "text"), ("RelationshipManagerId", "text"), ("ServiceAssociateId", "text"), ("OnboardedDate", "date"), ("ClientTier", "text")], "ClientId")
    reg(lob, "am_mandates", [("MandateId", "text"), ("ClientId", "text"), ("Strategy", "text"), ("Vehicle", "text"), ("AUM", "number"), ("FeeRateBps", "number"), ("InceptionDate", "date"), ("Benchmark", "text"), ("Status", "text")], "MandateId")
    reg(lob, "am_mandate_flows", [("FlowId", "text"), ("MandateId", "text"), ("ClientId", "text"), ("FlowMonth", "date"), ("NetFlow", "number"), ("MarketReturnPct", "number"), ("EndingAUM", "number")], "FlowId")
    reg(lob, "am_financial_deals", [("DealId", "text"), ("DealName", "text"), ("ClientId", "text"), ("Stage", "text"), ("Amount", "number"), ("CreatedDate", "date"), ("CloseDate", "date"), ("OwnerId", "text"), ("Source", "text"), ("IsWon", "boolean")], "DealId")
    reg(lob, "am_service_requests", [("RequestId", "text"), ("ClientId", "text"), ("AssociateId", "text"), ("RequestType", "text"), ("CreatedDate", "dateTime"), ("ClosedDate", "dateTime"), ("Status", "text"), ("SLADays", "number"), ("CycleTimeDays", "number"), ("SLABreached", "boolean"), ("Channel", "text"), ("Priority", "text")], "RequestId")
    return {"am_clients": clients, "am_mandates": mandates, "am_mandate_flows": flows, "am_financial_deals": deals, "am_service_requests": reqs}


# --------------------------------------------------------------------------
# 4. Insurance (P&C, with brokerage angle)
# --------------------------------------------------------------------------
def gen_insurance(branches, employees):
    lob = "insurance"
    adjusters = by_role(employees, "Claims Adjuster")
    producers, policies, claims, ccases = [], [], [], []
    for i in range(1, n(60) + 1):
        f, l = person()
        producers.append({"ProducerId": f"INS-PR-{i:03d}", "ProducerName": f"{f} {l}", "ProducerType": pick(["Captive Agent", "Independent Broker", "Direct"], [45, 40, 15]),
                          "Region": pick(REGIONS), "AppointedDate": iso(rdate(dt.date(2012, 1, 1), dt.date(2026, 1, 1)))})
    lines = [("Homeowners (HO-3)", 1800, 0.62), ("Personal Auto", 1400, 0.71), ("Renters", 320, 0.45), ("Umbrella", 450, 0.35), ("Small Commercial Package", 6500, 0.66), ("Commercial Auto", 3900, 0.74)]
    for i in range(1, n(9000) + 1):
        line, prem, base_lr = pick(lines, [30, 34, 12, 6, 12, 6])
        eff = rdate(dt.date(2023, 9, 1), TODAY)
        exp = eff + dt.timedelta(days=365)
        f, l = person()
        if i == 1:
            f, l, line, prem = "Elena", "Ruiz", "Homeowners (HO-3)", 2100
        status = "Active" if exp >= TODAY else pick(["Renewed", "Renewed", "Lapsed", "Cancelled"], [62, 10, 18, 10])
        pol = {"PolicyId": f"INS-PL-{i:06d}", "PolicyNumber": f"CUM-{R.randint(1000000, 9999999)}", "NamedInsured": f"{f} {l}", "LineOfBusiness": line,
               "PolicyType": "Personal" if "Commercial" not in line else "Commercial", "ProducerId": pick(producers)["ProducerId"], "State": pick(sum(STATES.values(), [])),
               "EffectiveDate": iso(eff), "ExpirationDate": iso(exp), "Status": status, "AnnualPremium": round(lognorm(prem, 0.35, prem * 0.4, prem * 4), 2),
               "Carrier": pick(["Cumulus Mutual", "Cumulus Mutual", "Northwind Assurance", "Atlas P&C", "Beacon National"]),
               "RenewalOfferSent": pick(["true", "false"], [80, 20]), "IsRenewed": "true" if status == "Renewed" else "false"}
        policies.append(pol)
        # claims — story: hail event June 2026 in CO/UT/AZ homeowners & auto → cycle time +40%
        p_claim = 0.12 if "Auto" in line else (0.08 if "Home" in line else 0.05)
        if pol["State"] in ("CO", "UT", "AZ") and line in ("Homeowners (HO-3)", "Personal Auto") and eff <= dt.date(2026, 6, 15) <= exp:
            p_claim += 0.35
        if R.random() < p_claim:
            hail = pol["State"] in ("CO", "UT", "AZ") and line in ("Homeowners (HO-3)", "Personal Auto") and R.random() < 0.7 and eff <= dt.date(2026, 6, 15) <= exp
            loss = dt.date(2026, 6, R.randint(14, 18)) if hail else rdate(max(eff, START), min(exp, TODAY))
            report = loss + dt.timedelta(days=R.randint(0, 6))
            ctype = "Hail Damage" if hail else pick(["Collision", "Water Damage", "Theft", "Fire", "Liability", "Wind", "Glass"])
            cycle = lognorm(18, 0.5, 1, 180) * (1.4 if hail else 1)
            fin = report + dt.timedelta(days=cycle)
            status = "Closed" if fin <= TODAY else pick(["Open", "Under Review", "Awaiting Documents"])
            reserve = lognorm(pol["AnnualPremium"] * (3.5 if ("Auto" in line or "Home" in line) else 2.0), 0.9, 200, 400000)
            claims.append({"ClaimId": f"INS-CL-{len(claims) + 1:06d}", "ClaimNumber": f"CLM-{R.randint(100000, 999999)}", "PolicyId": pol["PolicyId"], "ClaimType": ctype,
                           "LossDate": iso(loss), "ReportDate": iso(report), "FinalizedDate": iso(fin) if status == "Closed" else "", "Status": status,
                           "ReserveAmount": round(reserve, 2), "PaidAmount": round(reserve * R.uniform(0.5, 1.05), 2) if status == "Closed" else 0,
                           "CycleTimeDays": round(cycle, 1) if status == "Closed" else "", "AdjusterId": pick(adjusters)["EmployeeId"],
                           "CatastropheCode": "CAT-2026-HAIL-MW" if hail else "", "FNOLChannel": pick(["Mobile App", "Phone", "Agent", "Web"], [35, 35, 20, 10]), "IsLitigated": pick(["true", "false"], [3, 97])})
            for _ in range(pick([0, 1, 2], [40, 45, 15])):
                cd = report + dt.timedelta(days=R.randint(0, int(cycle) + 1))
                ccases.append({"CaseId": f"INS-CS-{len(ccases) + 1:06d}", "ClaimId": claims[-1]["ClaimId"], "PolicyId": pol["PolicyId"], "CreatedDate": iso(rdt(cd)),
                               "CaseType": pick(["Claim Status", "Document Request", "Payment Question", "Adjuster Contact", "Rental/Repair"]), "Channel": pick(["Phone", "Chat", "Email", "Mobile App"]),
                               "Status": pick(["Closed", "Closed", "Open"]), "HandleTimeMinutes": round(lognorm(9, 0.5, 1, 60), 1), "CSAT": R.randint(1, 5) if R.random() < 0.5 else "",
                               "AgentforceHandled": pick(["true", "false"], [42, 58])})
    reg(lob, "ins_producers", [("ProducerId", "text"), ("ProducerName", "text"), ("ProducerType", "text"), ("Region", "text"), ("AppointedDate", "date")], "ProducerId")
    reg(lob, "ins_policies", [("PolicyId", "text"), ("PolicyNumber", "text"), ("NamedInsured", "text"), ("LineOfBusiness", "text"), ("PolicyType", "text"), ("ProducerId", "text"), ("State", "text"),
                              ("EffectiveDate", "date"), ("ExpirationDate", "date"), ("Status", "text"), ("AnnualPremium", "number"), ("Carrier", "text"), ("RenewalOfferSent", "boolean"), ("IsRenewed", "boolean")], "PolicyId")
    reg(lob, "ins_claims", [("ClaimId", "text"), ("ClaimNumber", "text"), ("PolicyId", "text"), ("ClaimType", "text"), ("LossDate", "date"), ("ReportDate", "date"), ("FinalizedDate", "date"), ("Status", "text"),
                            ("ReserveAmount", "number"), ("PaidAmount", "number"), ("CycleTimeDays", "number"), ("AdjusterId", "text"), ("CatastropheCode", "text"), ("FNOLChannel", "text"), ("IsLitigated", "boolean")], "ClaimId")
    reg(lob, "ins_claim_cases", [("CaseId", "text"), ("ClaimId", "text"), ("PolicyId", "text"), ("CreatedDate", "dateTime"), ("CaseType", "text"), ("Channel", "text"), ("Status", "text"), ("HandleTimeMinutes", "number"), ("CSAT", "number"), ("AgentforceHandled", "boolean")], "CaseId")
    return {"ins_producers": producers, "ins_policies": policies, "ins_claims": claims, "ins_claim_cases": ccases}


# --------------------------------------------------------------------------
# 5. Commercial Banking
# --------------------------------------------------------------------------
def gen_commercial(branches, employees):
    lob = "commercial"
    rms = by_role(employees, "Relationship Manager")
    agents = by_role(employees, "Service Agent")
    accounts, deals, facilities, treasury, referrals, onboarding, cases = [], [], [], [], [], [], []
    industries = ["Logistics", "Healthcare", "Manufacturing", "Technology", "Hospitality", "Construction", "Professional Services", "Retail", "Agriculture"]
    tprods = ["ACH Origination", "sFTP File Delivery", "Positive Pay", "Lockbox", "Wire Services", "Commercial Card", "Merchant Services", "Sweep Account"]
    for i in range(1, n(600) + 1):
        name = pick(["Meridian", "Summit", "Harbor", "Ironwood", "Bluewater", "Granite", "PayCadence", "Northwind", "Redwood", "Keystone"]) + " " + pick(["Logistics", "Health", "Industries", "Systems", "Group", "Holdings", "Builders", "Foods", "Partners"])
        if i == 1:
            name = "Meridian Logistics"
        seg = pick(["Small Business", "Middle Market", "Corporate"], [55, 35, 10])
        rev = lognorm({"Small Business": 4e6, "Middle Market": 80e6, "Corporate": 900e6}[seg], 0.7, 5e5)
        acc = {"BusinessAccountId": f"CB-BA-{i:05d}", "BusinessName": f"{name}" + ("" if i == 1 else f" {i}"), "Industry": pick(industries), "Segment": seg, "AnnualRevenue": round(rev, 2),
               "RelationshipManagerId": pick(rms)["EmployeeId"], "Region": pick(REGIONS), "RelationshipStartDate": iso(rdate(dt.date(2012, 1, 1), dt.date(2026, 7, 1))),
               "PrimaryOperatingAccount": pick(["true", "false"], [70, 30]), "RelationshipProfitability": round(rev * R.uniform(0.0008, 0.004), 2)}
        accounts.append(acc)
        n_t = pick([0, 1, 2, 3, 4], [25, 30, 25, 14, 6])
        for tp in R.sample(tprods, n_t):
            treasury.append({"EnrollmentId": f"CB-TP-{len(treasury) + 1:05d}", "BusinessAccountId": acc["BusinessAccountId"], "ProductName": tp, "EnrolledDate": iso(rdate(dt.date(2018, 1, 1))),
                             "MonthlyVolume": round(lognorm(150000, 1.2, 1000), 2), "Status": pick(["Active", "Active", "Active", "Pending", "Cancelled"])})
        for _ in range(pick([0, 1, 2], [40, 45, 15])):
            limit = lognorm(rev * 0.15, 0.6, 50000)
            util = R.betavariate(2, 3)
            facilities.append({"FacilityId": f"CB-FC-{len(facilities) + 1:05d}", "BusinessAccountId": acc["BusinessAccountId"], "FacilityType": pick(["Revolving Line of Credit", "Term Loan", "Equipment Finance", "CRE Mortgage", "Letter of Credit"]),
                               "CommitmentAmount": round(limit, 2), "OutstandingBalance": round(limit * util, 2), "UtilizationPct": round(util * 100, 1),
                               "RiskRating": pick(["1-Pass", "2-Pass", "3-Pass", "4-Watch", "5-Substandard"], [25, 35, 25, 10, 5]), "MaturityDate": iso(rdate(dt.date(2026, 9, 1), dt.date(2031, 12, 31))),
                               "CovenantUtilizationMax": pick([75, 80, 85, 90])})
        # onboarding — story: clients without treasury products take 2x longer
        if R.random() < 0.6:
            start = rdate(dt.date(2025, 1, 1))
            base = 21 if n_t > 0 else 42
            dur = lognorm(base, 0.4, 3)
            onboarding.append({"OnboardingId": f"CB-OB-{len(onboarding) + 1:05d}", "BusinessAccountId": acc["BusinessAccountId"], "OnboardingType": pick(["New Relationship", "sFTP / ACH Setup", "Treasury Add-On", "Credit Facility"], [35, 30, 20, 15]),
                               "StartDate": iso(start), "CompletedDate": iso(start + dt.timedelta(days=dur)) if start + dt.timedelta(days=dur) <= TODAY else "",
                               "CycleTimeDays": round(dur, 1), "HasTreasuryProducts": "true" if n_t > 0 else "false", "DocumentsRequested": R.randint(3, 14), "Status": "Complete" if start + dt.timedelta(days=dur) <= TODAY else "In Progress"})
        for _ in range(pick([0, 1, 2, 3], [45, 35, 15, 5])):
            cd = rdate()
            cases.append({"CaseId": f"CB-CS-{len(cases) + 1:06d}", "BusinessAccountId": acc["BusinessAccountId"], "CreatedDate": iso(rdt(cd)), "CaseType": pick(["ACH File Rejection", "sFTP Connectivity", "Wire Inquiry", "Positive Pay Exception", "Statement Request", "Access Management"]),
                          "Channel": pick(["Phone", "Email", "Portal", "Chat"]), "Status": pick(["Closed", "Closed", "Closed", "Open", "Escalated"]), "HandleTimeMinutes": round(lognorm(14, 0.6, 2, 180), 1),
                          "AgentId": pick(agents)["EmployeeId"], "CSAT": R.randint(1, 5) if R.random() < 0.45 else "", "AgentforceHandled": pick(["true", "false"], [30, 70])})
    stages = ["Qualification", "Proposal", "Credit Approval", "Documentation", "Closed Won", "Closed Lost"]
    for i in range(1, n(500) + 1):
        a = pick(accounts)
        st = pick(stages, [22, 20, 15, 10, 22, 11])
        created = rdate(dt.date(2025, 1, 1))
        deals.append({"DealId": f"CB-DL-{i:05d}", "DealName": f"{a['BusinessName']} — {pick(['Revolver', 'Term Loan', 'Treasury Bundle', 'Equipment', 'CRE'])}", "BusinessAccountId": a["BusinessAccountId"], "Stage": st,
                      "Amount": round(lognorm(1.8e6, 1.0, 50000, 250e6), 2), "Product": pick(["Credit", "Treasury", "Credit + Treasury"]), "CreatedDate": iso(created), "CloseDate": iso(created + dt.timedelta(days=R.randint(20, 240))),
                      "OwnerId": a["RelationshipManagerId"], "IsWon": "true" if st == "Closed Won" else "false"})
    for i in range(1, n(400) + 1):
        a = pick(accounts)
        referrals.append({"ReferralId": f"CB-RF-{i:05d}", "BusinessAccountId": a["BusinessAccountId"], "ReferralSource": pick(["Retail Branch", "Wealth Advisor", "Existing Client", "CPA Partner", "Digital"]),
                          "ReferredProduct": pick(["Treasury", "Credit Facility", "Merchant Services", "Commercial Card"]), "ReferralDate": iso(rdate()), "Status": pick(["Converted", "In Progress", "Declined", "New"], [38, 22, 25, 15]),
                          "EstimatedValue": round(lognorm(45000, 0.9, 1000), 2)})
    reg(lob, "cb_business_accounts", [("BusinessAccountId", "text"), ("BusinessName", "text"), ("Industry", "text"), ("Segment", "text"), ("AnnualRevenue", "number"), ("RelationshipManagerId", "text"), ("Region", "text"), ("RelationshipStartDate", "date"), ("PrimaryOperatingAccount", "boolean"), ("RelationshipProfitability", "number")], "BusinessAccountId")
    reg(lob, "cb_financial_deals", [("DealId", "text"), ("DealName", "text"), ("BusinessAccountId", "text"), ("Stage", "text"), ("Amount", "number"), ("Product", "text"), ("CreatedDate", "date"), ("CloseDate", "date"), ("OwnerId", "text"), ("IsWon", "boolean")], "DealId")
    reg(lob, "cb_credit_facilities", [("FacilityId", "text"), ("BusinessAccountId", "text"), ("FacilityType", "text"), ("CommitmentAmount", "number"), ("OutstandingBalance", "number"), ("UtilizationPct", "number"), ("RiskRating", "text"), ("MaturityDate", "date"), ("CovenantUtilizationMax", "number")], "FacilityId")
    reg(lob, "cb_treasury_enrollments", [("EnrollmentId", "text"), ("BusinessAccountId", "text"), ("ProductName", "text"), ("EnrolledDate", "date"), ("MonthlyVolume", "number"), ("Status", "text")], "EnrollmentId")
    reg(lob, "cb_referrals", [("ReferralId", "text"), ("BusinessAccountId", "text"), ("ReferralSource", "text"), ("ReferredProduct", "text"), ("ReferralDate", "date"), ("Status", "text"), ("EstimatedValue", "number")], "ReferralId")
    reg(lob, "cb_onboarding", [("OnboardingId", "text"), ("BusinessAccountId", "text"), ("OnboardingType", "text"), ("StartDate", "date"), ("CompletedDate", "date"), ("CycleTimeDays", "number"), ("HasTreasuryProducts", "boolean"), ("DocumentsRequested", "number"), ("Status", "text")], "OnboardingId")
    reg(lob, "cb_service_cases", [("CaseId", "text"), ("BusinessAccountId", "text"), ("CreatedDate", "dateTime"), ("CaseType", "text"), ("Channel", "text"), ("Status", "text"), ("HandleTimeMinutes", "number"), ("AgentId", "text"), ("CSAT", "number"), ("AgentforceHandled", "boolean")], "CaseId")
    return {"cb_business_accounts": accounts, "cb_financial_deals": deals, "cb_credit_facilities": facilities, "cb_treasury_enrollments": treasury,
            "cb_referrals": referrals, "cb_onboarding": onboarding, "cb_service_cases": cases}


# --------------------------------------------------------------------------
# 6. Financial Advisors (retail advisory book of business)
# --------------------------------------------------------------------------
def gen_advisors(branches, employees):
    lob = "advisors"
    advisors = by_role(employees, "Advisor")
    book, activities, referrals, life_events, goals = [], [], [], [], []
    for i in range(1, n(1400) + 1):
        adv = pick(advisors)
        f, l = person()
        aum = lognorm(280000, 0.9, 20000, 15000000)
        book.append({"ClientHouseholdId": f"FA-HH-{i:05d}", "HouseholdName": f"{l} Household", "PrimaryContactName": f"{f} {l}", "AdvisorId": adv["EmployeeId"], "BranchId": adv["BranchId"],
                     "AUM": round(aum, 2), "RiskProfile": pick(["Conservative", "Moderate", "Growth", "Aggressive"], [25, 40, 25, 10]), "LifeStage": pick(["Accumulation", "Pre-Retirement", "Retirement", "Legacy"], [40, 25, 25, 10]),
                     "ClientSince": iso(rdate(dt.date(2010, 1, 1), dt.date(2026, 8, 1))), "LastReviewDate": iso(rdate(dt.date(2025, 6, 1))), "ProductsHeld": R.randint(1, 6)})
        for _ in range(int(max(0, R.gauss(7, 4)))):
            d = rdate()
            activities.append({"ActivityId": f"FA-AC-{len(activities) + 1:07d}", "ClientHouseholdId": book[-1]["ClientHouseholdId"], "AdvisorId": adv["EmployeeId"], "ActivityDate": iso(rdt(d)),
                               "ActivityType": pick(["Call", "Meeting", "Email", "Task", "Annual Review"], [35, 20, 30, 10, 5]), "Outcome": pick(["Completed", "Completed", "No Answer", "Rescheduled"]), "DurationMinutes": R.randint(3, 75)})
        for _ in range(pick([0, 1, 2], [70, 24, 6])):
            goals.append({"GoalId": f"FA-GL-{len(goals) + 1:06d}", "ClientHouseholdId": book[-1]["ClientHouseholdId"], "GoalType": pick(["Retirement", "Education", "Home Purchase", "Emergency Fund", "Travel"]),
                          "TargetValue": round(lognorm(250000, 0.9, 5000), 2), "ProgressPct": round(R.uniform(2, 110), 1), "TargetDate": iso(rdate(dt.date(2027, 1, 1), dt.date(2050, 1, 1))), "Status": pick(["On Track", "At Risk", "Off Track", "Completed"], [50, 25, 12, 13])})
        # life events — story: 30% have no follow-up within 14 days
        for _ in range(pick([0, 1, 2], [65, 28, 7])):
            d = rdate(dt.date(2025, 6, 1))
            followed = R.random() < 0.70
            fu = d + dt.timedelta(days=R.randint(1, 13)) if followed else (d + dt.timedelta(days=R.randint(15, 60)) if R.random() < 0.5 else None)
            life_events.append({"LifeEventId": f"FA-LE-{len(life_events) + 1:06d}", "ClientHouseholdId": book[-1]["ClientHouseholdId"], "AdvisorId": adv["EmployeeId"], "EventType": pick(["New Child", "Job Change", "Inheritance", "Retirement", "Home Purchase", "Marriage", "Business Sale"]),
                               "EventDate": iso(d), "DetectedSource": pick(["Advisor", "Agentforce Signal", "Client Portal", "Transaction Pattern"], [40, 30, 20, 10]),
                               "FollowUpDate": iso(fu) if fu else "", "FollowUpWithin14Days": "true" if followed else "false", "OpportunityValue": round(lognorm(80000, 1.0, 2000), 2)})
    for i in range(1, n(900) + 1):
        adv = pick(advisors)
        f, l = person()
        st = pick(["New", "Contacted", "Meeting Set", "Converted", "Lost"], [20, 25, 15, 25, 15])
        referrals.append({"ReferralId": f"FA-RF-{i:05d}", "AdvisorId": adv["EmployeeId"], "ProspectName": f"{f} {l}", "ReferralSource": pick(["Existing Client", "Retail Branch", "Center of Influence", "Digital Lead", "Event"]),
                          "ReferralDate": iso(rdate()), "Status": st, "EstimatedAUM": round(lognorm(300000, 1.0, 10000), 2), "DaysToFirstContact": R.randint(0, 21) if st != "New" else ""})
    reg(lob, "fa_book_of_business", [("ClientHouseholdId", "text"), ("HouseholdName", "text"), ("PrimaryContactName", "text"), ("AdvisorId", "text"), ("BranchId", "text"), ("AUM", "number"), ("RiskProfile", "text"), ("LifeStage", "text"), ("ClientSince", "date"), ("LastReviewDate", "date"), ("ProductsHeld", "number")], "ClientHouseholdId")
    reg(lob, "fa_activities", [("ActivityId", "text"), ("ClientHouseholdId", "text"), ("AdvisorId", "text"), ("ActivityDate", "dateTime"), ("ActivityType", "text"), ("Outcome", "text"), ("DurationMinutes", "number")], "ActivityId")
    reg(lob, "fa_referrals", [("ReferralId", "text"), ("AdvisorId", "text"), ("ProspectName", "text"), ("ReferralSource", "text"), ("ReferralDate", "date"), ("Status", "text"), ("EstimatedAUM", "number"), ("DaysToFirstContact", "number")], "ReferralId")
    reg(lob, "fa_life_events", [("LifeEventId", "text"), ("ClientHouseholdId", "text"), ("AdvisorId", "text"), ("EventType", "text"), ("EventDate", "date"), ("DetectedSource", "text"), ("FollowUpDate", "date"), ("FollowUpWithin14Days", "boolean"), ("OpportunityValue", "number")], "LifeEventId")
    reg(lob, "fa_financial_goals", [("GoalId", "text"), ("ClientHouseholdId", "text"), ("GoalType", "text"), ("TargetValue", "number"), ("ProgressPct", "number"), ("TargetDate", "date"), ("Status", "text")], "GoalId")
    return {"fa_book_of_business": book, "fa_activities": activities, "fa_referrals": referrals, "fa_life_events": life_events, "fa_financial_goals": goals}


# --------------------------------------------------------------------------
# 7. Lending / Mortgage (Digital Lending vocabulary)
# --------------------------------------------------------------------------
def gen_lending(branches, employees):
    lob = "lending"
    los = by_role(employees, "Loan Officer")
    agents = by_role(employees, "Service Agent")
    apps, stage_events, cases = [], [], []
    products = [("30-Year Fixed Mortgage", 420000, 0.62), ("15-Year Fixed Mortgage", 310000, 0.66), ("HELOC", 85000, 0.7), ("Auto Loan", 32000, 0.78), ("Personal Loan", 14000, 0.6), ("Refinance", 380000, 0.55)]
    stage_defs = [("Application Submitted", 0.5), ("Document Collection", 9.0), ("Underwriting", 5.0), ("Appraisal", 6.0), ("Conditional Approval", 2.0), ("Clear to Close", 2.5), ("Funded", 0.5)]
    for i in range(1, n(4200) + 1):
        prod, amt, pull = pick(products, [30, 12, 15, 20, 13, 10])
        lo = pick(los)
        created = rdate(dt.date(2024, 10, 1))
        chan = pick(["Digital", "Branch", "Loan Officer", "Broker"], [42, 25, 23, 10])
        f, l = person()
        # outcome
        r = R.random()
        if r < pull:
            outcome = "Funded"
        elif r < pull + 0.15:
            outcome = "Withdrawn"
        elif r < pull + 0.25:
            outcome = "Denied"
        else:
            outcome = "In Progress"
        if chan == "Digital" and outcome == "Withdrawn" and R.random() < 0.3:
            outcome = "Abandoned"
        amount = lognorm(amt, 0.5, amt * 0.2, amt * 4)
        cur = created
        total = 0
        last_stage = stage_defs[0][0]
        n_stages = len(stage_defs) if outcome == "Funded" else R.randint(1, 5)
        for si, (sname, sdur) in enumerate(stage_defs[:n_stages]):
            dur = lognorm(sdur, 0.45, 0.1)
            if sname == "Document Collection":
                dur *= 2.2   # story: document collection = ~55% of cycle
                if chan == "Digital":
                    dur *= 0.75
            end = cur + dt.timedelta(days=dur)
            stage_events.append({"StageEventId": f"LN-SE-{len(stage_events) + 1:07d}", "ApplicationId": f"LN-AP-{i:06d}", "StageName": sname, "StageOrder": si + 1, "EnteredDate": iso(rdt(cur)),
                                 "ExitedDate": iso(rdt(end)) if end <= TODAY else "", "DaysInStage": round(dur, 2) if end <= TODAY else ""})
            cur = end
            total += dur
            last_stage = sname
        if cur > TODAY and outcome in ("Funded", "Withdrawn", "Denied", "Abandoned"):
            outcome = "In Progress"
        apps.append({"ApplicationId": f"LN-AP-{i:06d}", "ApplicantName": f"{f} {l}", "ProductName": prod, "RequestedAmount": round(amount, 2), "Channel": chan, "LoanOfficerId": lo["EmployeeId"], "BranchId": lo["BranchId"],
                     "SubmittedDate": iso(created), "DecisionDate": iso(cur) if outcome in ("Funded", "Denied") else "", "FundedDate": iso(cur) if outcome == "Funded" else "",
                     "Status": outcome, "CurrentStage": last_stage, "CycleTimeDays": round(total, 1) if outcome == "Funded" else "", "CreditScore": R.randint(560, 830), "DTIRatio": round(R.uniform(0.12, 0.52), 3),
                     "InterestRate": round(R.uniform(5.1, 8.9), 3), "IsFunded": "true" if outcome == "Funded" else "false", "DocumentsOutstanding": R.randint(0, 6) if outcome == "In Progress" else 0})
        for _ in range(pick([0, 1, 2], [55, 35, 10])):
            cases.append({"CaseId": f"LN-CS-{len(cases) + 1:06d}", "ApplicationId": f"LN-AP-{i:06d}", "CreatedDate": iso(rdt(rdate(created, min(cur, TODAY)))), "CaseType": pick(["Status Inquiry", "Document Upload Issue", "Rate Lock Question", "Appraisal Scheduling", "Payoff Request"]),
                          "Channel": pick(["Phone", "Chat", "Email", "Mobile App"]), "Status": pick(["Closed", "Closed", "Open"]), "HandleTimeMinutes": round(lognorm(8, 0.5, 1, 60), 1), "AgentId": pick(agents)["EmployeeId"],
                          "CSAT": R.randint(1, 5) if R.random() < 0.5 else "", "AgentforceHandled": pick(["true", "false"], [40, 60])})
    reg(lob, "ln_applications", [("ApplicationId", "text"), ("ApplicantName", "text"), ("ProductName", "text"), ("RequestedAmount", "number"), ("Channel", "text"), ("LoanOfficerId", "text"), ("BranchId", "text"), ("SubmittedDate", "date"), ("DecisionDate", "date"), ("FundedDate", "date"),
                                 ("Status", "text"), ("CurrentStage", "text"), ("CycleTimeDays", "number"), ("CreditScore", "number"), ("DTIRatio", "number"), ("InterestRate", "number"), ("IsFunded", "boolean"), ("DocumentsOutstanding", "number")], "ApplicationId")
    reg(lob, "ln_stage_events", [("StageEventId", "text"), ("ApplicationId", "text"), ("StageName", "text"), ("StageOrder", "number"), ("EnteredDate", "dateTime"), ("ExitedDate", "dateTime"), ("DaysInStage", "number")], "StageEventId")
    reg(lob, "ln_service_cases", [("CaseId", "text"), ("ApplicationId", "text"), ("CreatedDate", "dateTime"), ("CaseType", "text"), ("Channel", "text"), ("Status", "text"), ("HandleTimeMinutes", "number"), ("AgentId", "text"), ("CSAT", "number"), ("AgentforceHandled", "boolean")], "CaseId")
    return {"ln_applications": apps, "ln_stage_events": stage_events, "ln_service_cases": cases}


# --------------------------------------------------------------------------
# Emit: Data 360 Ingestion API schema (OpenAPI 3.0.3) + data dictionary
# --------------------------------------------------------------------------
TYPE_MAP = {"text": ("string", None), "number": ("number", None), "dateTime": ("string", "date-time"), "date": ("string", "date"), "boolean": ("boolean", None)}


def emit_schema(path):
    lines = ["openapi: 3.0.3", "components:", "  schemas:"]
    for table, cols in SCHEMA.items():
        lines.append(f"    {table}:")
        lines.append("      type: object")
        lines.append("      properties:")
        for c, t in cols.items():
            typ, fmt = TYPE_MAP[t]
            lines.append(f"        {c}:")
            lines.append(f"          type: {typ}")
            if fmt:
                lines.append(f"          format: {fmt}")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def emit_dictionary(path, counts):
    out = ["# Cumulus Financial Group — Data Dictionary", "",
           f"Generated by `data/generate.py` (seed 42, scale {SCALE}). Window: {START} → {TODAY}. Types follow Data 360 Ingestion API schema types.", "",
           "Primary keys are the first column of each table; every `*Id` column referencing another table is a foreign key to that table's primary key (validated by `data/validate.py`).", ""]
    cur = None
    for table, cols in SCHEMA.items():
        if LOB_OF[table] != cur:
            cur = LOB_OF[table]
            out.append(f"## {cur}")
            out.append("")
        out.append(f"### `{table}` — {counts.get(table, 0):,} rows (pk `{PRIMARY_KEYS[table]}`)")
        out.append("")
        out.append("| Column | Type |")
        out.append("|---|---|")
        for c, t in cols.items():
            out.append(f"| {c} | {t} |")
        out.append("")
    out += ["## Story anomalies (for talk tracks)", "",
            "- Retail: Card Dispute / Fee Inquiry cases spike in branches BR-003 and BR-011 from May 2026 (fee change). Lauren Bailey (RB-C-00001-1) has the $75 Amazon Marketplace disputed charge on 2026-08-18 and an Agentforce-handled Voice case on 2026-08-19.",
            "- Wealth: churned households average ~1.2 interactions/quarter vs ~4.5 for retained. Jonathan Ashford III (WM-HH-00001) onboarded 2026-07-14 with a $40M inflow in July 2026.",
            "- Asset Management: Reconciliation requests created in the first 12 days of a quarter run ~2.4x their normal cycle time and breach SLA.",
            "- Insurance: CAT-2026-HAIL-MW (June 14–18, 2026) hits CO/UT/AZ Homeowners and Auto; hail claims carry ~1.4x cycle time. Elena Ruiz (INS-PL-000001) is the HO-3 policy from the brokerage storyline.",
            "- Commercial: onboarding without treasury products takes ~2x longer (42 vs 21 day base). Meridian Logistics (CB-BA-00001) is the sFTP/ACH storyline client.",
            "- Advisors: ~30% of life events have no follow-up within 14 days; 30% of life events are detected by Agentforce signals.",
            "- Lending: Document Collection carries ~55% of total cycle time; digital channel is 25% faster in that stage and has extra abandonment.", ""]
    with open(path, "w") as f:
        f.write("\n".join(out))


def main():
    global R, SCALE
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "out"))
    a = ap.parse_args()
    R = random.Random(a.seed)
    SCALE = a.scale
    branches, employees = gen_shared()
    tables = {"cumulus_branches": branches, "cumulus_employees": employees}
    for fn in (gen_retail, gen_wealth, gen_asset_mgmt, gen_insurance, gen_commercial, gen_advisors, gen_lending):
        tables.update(fn(branches, employees))
    counts = {}
    for t, rows in tables.items():
        p, c = writer(a.out, t, rows)
        counts[t] = c
        print(f"{c:>8,}  {p}")
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, "ingestion"), exist_ok=True)
    emit_schema(os.path.join(here, "ingestion", "cumulus_schema.yaml"))
    emit_dictionary(os.path.join(here, "DATA_DICTIONARY.md"), counts)
    print(f"\n{len(tables)} tables, {sum(counts.values()):,} rows. Schema + dictionary written.")


if __name__ == "__main__":
    main()
