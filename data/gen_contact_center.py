#!/usr/bin/env python3
"""
Cumulus Contact Center: synthetic contact center data for a retail bank.

Standalone and seeded (does not touch data/generate.py or its random stream).
Writes data/out/contact_center/{cc_call_centers,cc_customers,cc_contacts}.csv

Window matches the rest of Cumulus: 2024-09-01 to 2026-08-31. Everything is fictional.

Storylines baked in (check data/out/contact_center after a run, the dashboard titles quote them):
  * Dallas misses its response-time SLA more often from March 2026 (staffing gap).
  * Fraud Alert and Card Dispute contacts are the most negative.
  * An online banking outage (14 to 18 Oct 2025) spikes Account Access contacts with negative sentiment.
  * Chatbot and Mobile App are mostly handled by Agentforce and answer fastest.

Usage: python3 data/gen_contact_center.py [--out data/out] [--seed 7]
"""
import argparse
import csv
import datetime as dt
import math
import os
import random

START = dt.date(2024, 9, 1)
TODAY = dt.date(2026, 8, 31)

CENTERS = [  # id, name, city, state, region, headcount, weight
    ("CC-01", "Charlotte Contact Center", "Charlotte", "NC", "Southeast", 120, 30),
    ("CC-02", "Dallas Contact Center", "Dallas", "TX", "Southwest", 105, 28),
    ("CC-03", "Phoenix Contact Center", "Phoenix", "AZ", "Mountain West", 70, 18),
    ("CC-04", "Columbus Contact Center", "Columbus", "OH", "Midwest", 55, 14),
    ("CC-05", "Tampa Contact Center", "Tampa", "FL", "Southeast", 40, 10),
]
# channel -> (weight, SLA target minutes, median handle minutes, agentforce share, response factor)
CHANNELS = {
    "Call Center": (36, 3, 11.0, 0.08, 1.00),
    "Chatbot": (26, 1, 4.0, 0.88, 0.80),
    "Email": (16, 240, 9.0, 0.06, 1.10),
    "Web Chat": (12, 5, 8.0, 0.30, 0.95),
    "Mobile App": (10, 5, 5.0, 0.82, 0.85),
}
# reason -> (weight, handle multiplier, resolve probability, sentiment shift (positive = happier))
REASONS = {
    "Billing and Fees": (17, 1.0, 0.74, -0.15),
    "Card Dispute": (13, 1.4, 0.58, -0.55),
    "Payments": (16, 0.9, 0.80, 0.10),
    "Account Access": (14, 0.8, 0.78, -0.10),
    "Fraud Alert": (9, 1.3, 0.60, -0.70),
    "Loan Status": (11, 1.2, 0.66, 0.00),
    "Wire Transfer": (7, 1.1, 0.70, -0.05),
    "Mortgage Servicing": (7, 1.5, 0.62, -0.10),
    "Balance and Statements": (6, 0.6, 0.92, 0.35),
}
# reason -> channel weight overrides (relative multipliers)
CHANNEL_TILT = {
    "Fraud Alert": {"Call Center": 2.4, "Chatbot": 0.3, "Email": 0.4, "Mobile App": 0.6},
    "Card Dispute": {"Call Center": 1.8, "Chatbot": 0.6},
    "Mortgage Servicing": {"Call Center": 1.6, "Email": 1.8, "Chatbot": 0.4, "Mobile App": 0.4},
    "Loan Status": {"Email": 1.4, "Call Center": 1.3},
    "Balance and Statements": {"Chatbot": 2.2, "Mobile App": 2.0, "Call Center": 0.4},
    "Payments": {"Chatbot": 1.5, "Mobile App": 1.5},
    "Account Access": {"Chatbot": 1.4, "Web Chat": 1.4},
}
SENTIMENTS = ["Very Positive", "Positive", "Neutral", "Negative", "Very Negative"]
CSAT_MEAN = {"Very Positive": 9.0, "Positive": 7.6, "Neutral": 5.8, "Negative": 3.8, "Very Negative": 2.2}
SEGMENTS = [("Mass Market", 55), ("Mass Affluent", 25), ("Premier", 10), ("Small Business", 10)]
STATE_W = [("CA", 14), ("TX", 13), ("FL", 11), ("NY", 8), ("NC", 6), ("VA", 5), ("GA", 5), ("OH", 5), ("PA", 5), ("IL", 5),
           ("AZ", 4), ("WA", 3), ("MA", 3), ("NJ", 3), ("MD", 3), ("CO", 3), ("TN", 2), ("MI", 2), ("MN", 1), ("OR", 1)]
FIRST = ["Alex", "Maria", "James", "Priya", "Sofia", "Daniel", "Aisha", "Tom", "Grace", "Wei", "Carlos", "Naomi", "Ethan", "Olivia", "Hannah",
         "Luis", "Maya", "Noah", "Isabella", "Jamal", "Chloe", "Ravi", "Emma", "Leo", "Zara", "Owen", "Fatima", "Henry", "Mei", "Andre"]
LAST = ["Brown", "Garcia", "Johnson", "Miller", "Davis", "Martinez", "Lopez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "White",
        "Harris", "Clark", "Lewis", "Walker", "Hall", "Allen", "Young", "King", "Wright", "Scott", "Green", "Adams", "Baker", "Nelson", "Carter", "Patel"]
OUTAGE = (dt.date(2025, 10, 14), dt.date(2025, 10, 18))


def months():
    out, d = [], dt.date(START.year, START.month, 1)
    while d <= TODAY:
        out.append(d)
        d = dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return out


def month_days(first):
    nxt = dt.date(first.year + (first.month // 12), (first.month % 12) + 1, 1)
    return [first + dt.timedelta(days=i) for i in range((nxt - first).days) if first + dt.timedelta(days=i) <= TODAY]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    R = random.Random(a.seed)
    pick = lambda seq, w=None: R.choices(seq, weights=w, k=1)[0]

    # ---- call centers
    centers = [{"CallCenterId": c[0], "CallCenterName": c[1], "City": c[2], "State": c[3], "Region": c[4], "Headcount": c[5]} for c in CENTERS]
    cweights = [c[6] for c in CENTERS]

    # ---- customers
    custs = []
    for i in range(1, 6001):
        st = pick([s for s, _ in STATE_W], [w for _, w in STATE_W])
        custs.append({"CustomerId": f"CU-{i:06d}", "CustomerName": f"{pick(FIRST)} {pick(LAST)}", "State": st,
                      "Segment": pick([s for s, _ in SEGMENTS], [w for _, w in SEGMENTS]), "CustomerSince": (START - dt.timedelta(days=R.randint(30, 4000))).isoformat()})
    cust_w = [3.0 if R.random() < 0.15 else 1.0 for _ in custs]  # a minority of repeat callers

    # ---- contacts
    contacts, seen = [], set()
    ms = months()
    for mi, m in enumerate(ms):
        days = month_days(m)
        base = 640 * (1 + 0.016 * mi)
        season = 1 + 0.08 * math.sin((m.month - 1) / 12 * 2 * math.pi)
        n_month = int(base * season)
        day_w = [0.45 if d.weekday() >= 5 else 1.0 for d in days]
        for d in days:
            if OUTAGE[0] <= d <= OUTAGE[1]:
                day_w[days.index(d)] *= 3.2
        for _ in range(n_month):
            d = pick(days, day_w)
            outage = OUTAGE[0] <= d <= OUTAGE[1]
            reason = "Account Access" if (outage and R.random() < 0.62) else pick(list(REASONS), [v[0] for v in REASONS.values()])
            tilt = CHANNEL_TILT.get(reason, {})
            channel = pick(list(CHANNELS), [CHANNELS[c][0] * tilt.get(c, 1.0) for c in CHANNELS])
            center = pick(centers, cweights)
            _, target, hmed, af_share, rfactor = CHANNELS[channel]
            _, hmult, resolve_p, sshift = REASONS[reason]
            # response time vs SLA target: lognormal ratio (median 0.77, sigma 0.38 gives ~12% faster, ~63% within, ~25% missed)
            ratio = math.exp(R.gauss(-0.256, 0.38)) * rfactor
            if center["CallCenterId"] == "CC-02" and d >= dt.date(2026, 3, 1):
                ratio *= 1.38
            if center["CallCenterId"] == "CC-03":
                ratio *= 0.90
            if outage:
                ratio *= 1.25
            response = max(0.1, round(ratio * target, 2))
            status = "Faster than SLA" if ratio <= 0.5 else ("Within SLA" if ratio <= 1.0 else "Missed SLA")
            duration = round(max(0.5, math.exp(R.gauss(math.log(hmed * hmult), 0.45))), 1)
            if center["CallCenterId"] == "CC-03":
                duration = round(duration * 0.93, 1)
            resolved = R.random() < min(0.97, max(0.2, resolve_p + (0.04 if status != "Missed SLA" else -0.08) + (0.05 if channel in ("Chatbot", "Mobile App") and hmult < 1 else 0)))
            # sentiment: base mix shifted by reason, SLA, resolution, outage
            score = R.gauss(0.0, 1.0) + sshift + (0.30 if resolved else -0.45) + (-0.55 if status == "Missed SLA" else (0.20 if status == "Faster than SLA" else 0.05))
            if outage and reason == "Account Access":
                score -= 0.9
            if channel == "Chatbot" and hmult > 1.0:
                score -= 0.25
            sentiment = SENTIMENTS[0] if score > 1.35 else SENTIMENTS[1] if score > 0.55 else SENTIMENTS[2] if score > -0.55 else SENTIMENTS[3] if score > -1.35 else SENTIMENTS[4]
            csat = min(10, max(1, round(R.gauss(CSAT_MEAN[sentiment], 1.0))))
            cust = pick(custs, cust_w)
            first = cust["CustomerId"] not in seen
            seen.add(cust["CustomerId"])
            ts = dt.datetime(d.year, d.month, d.day, R.randint(7, 20), R.randint(0, 59), R.randint(0, 59))
            contacts.append({
                "ContactId": "", "ContactDate": ts.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "ContactMonth": m.isoformat(), "CallCenterId": center["CallCenterId"],
                "CustomerId": cust["CustomerId"], "Channel": channel, "Reason": reason, "Sentiment": sentiment, "IsNegative": str(sentiment in ("Negative", "Very Negative")).lower(),
                "ResponseMinutes": response, "SLATargetMinutes": target, "SLAStatus": status, "SLAMet": str(status != "Missed SLA").lower(),
                "DurationMinutes": duration, "CSAT": csat, "FirstContactResolved": str(resolved).lower(),
                "AgentforceHandled": str(R.random() < af_share).lower(), "IsFirstContact": str(first).lower()})
    contacts.sort(key=lambda r: r["ContactDate"])
    for i, r in enumerate(contacts, 1):
        r["ContactId"] = f"CT-{i:07d}"

    d = os.path.join(a.out, "contact_center")
    os.makedirs(d, exist_ok=True)
    for name, rows, cols in (("cc_call_centers", centers, ["CallCenterId", "CallCenterName", "City", "State", "Region", "Headcount"]),
                             ("cc_customers", custs, ["CustomerId", "CustomerName", "State", "Segment", "CustomerSince"]),
                             ("cc_contacts", contacts, list(contacts[0].keys()))):
        with open(os.path.join(d, name + ".csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
