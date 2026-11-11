# Talk track: Cumulus Tableau Next demos

A fresh draft written from the sample query results in [SAMPLE_QUESTIONS.md](SAMPLE_QUESTIONS.md). It is not based on any earlier talk track. Every number below came from queries run on 2026-11-09 against the Cumulus semantic models in org `sdo1010`. Dollar amounts are written as USD.

**Google Doc version:** [Cumulus Tableau Next: talk track, questions and results](https://docs.google.com/document/d/1Pztv5_-NQVt2l8yb9eHrE31YpOmTTZkRNqrQLegepos/edit)

## How to use it

- Lead with Wealth and Commercial Banking. Their stories show up clearly in the data.
- Use Asset Management and Insurance as supporting stories, with the caveats noted.
- Use Retail Banking to show how the agent answers questions, not to claim an insight.
- Do not claim numbers for Financial Advisors or Lending yet. Both are built, but no queries have been run against them.
- The numbers come from the semantic layer, not from the analytics agent itself. Before presenting live, run each question through the agent and check it gives the same answer.

## Opening (1 minute)

"Cumulus Financial Group is a fictional financial services company with seven lines of business. Each one has its own data, semantic model and dashboards in Tableau Next. I'll show how a business person can ask a plain-English question and get an answer that is grounded in governed data, using three of them."

## Story 1: Wealth (4 minutes)

**Persona:** advisor team lead.

**Ask:** "Compare interaction frequency for churned versus retained households."

**What the data shows:** churned households averaged 9.1 interactions. Retained households averaged 35.0. That is about 3.8 times fewer.

**Say:** "The households that left had a quarter of the contact. If an advisor sees a household going quiet, that is the warning sign."

**Follow-up ask:** "Which households have had fewer than two interactions in the last quarter and more than 1M USD AUM?"

**Also available:** total AUM by advisor ranges from 7M USD to 115M USD across the top 20, with two advisors above 100M USD. Use it to show where an advisor's attention is concentrated.

**Land it:** "This turns a retention problem into a list of households to call this week."

## Story 2: Commercial Banking (4 minutes)

**Persona:** relationship manager desk lead.

**Ask:** "Do clients without treasury products take longer to onboard?"

**What the data shows:** 43.8 days without treasury products, 22.3 days with them. That is about twice as long.

**Say:** "Clients who have treasury products set up onboard in half the time. That is a reason to lead with treasury in the first conversation."

**Follow-up ask:** "Which credit facilities are above 80% utilization or over their covenant maximum?"

**Also available:** outstanding credit by risk rating. Watch and Substandard together are about 630M USD of roughly 5.0B USD outstanding, around 12.5%. The deal pipeline is largest at Closed Won (433M USD), then Qualification (367M USD).

**Land it:** "The same model answers a sales question, a risk question and an operations question."

## Story 3: Asset Management (2 minutes)

**Persona:** institutional client service lead.

**Ask:** "What is AUM by strategy?"

**What the data shows:** Private Credit leads at 16.3B USD, then Liability-Driven Investing at 14.9B USD.

**Second ask:** "Show the pipeline by stage with total amount." RFP Received holds the most at 14.0B USD, then Finals Presentation at 7.6B USD.

**Caveat:** the SLA question is only partly answered. Performance Report requests breached SLA 294 times out of 995 (30%). The demo's quarter-end Reconciliation story has not been tested, so do not state it as fact.

## Story 4: Insurance (2 minutes)

**Persona:** claims service manager.

**Ask:** "How did the June 2026 hail catastrophe affect claims cycle time?"

**What the data shows:** hail catastrophe claims took 25.8 days on average against 20.5 for all other claims. That is about 26% longer.

**Say:** "The catastrophe added about a quarter to claim cycle time."

**Do not say 40%.** Earlier demo notes used +40% and three states. The data supports about 26%, and the state split has not been run.

**Also available:** paid claims are led by Personal Auto (2.6M USD) and Homeowners (2.2M USD). Mobile App is the top first-notice-of-loss channel with 353 claims, ahead of Phone with 313.

## Retail Banking: show how the agent answers (2 minutes)

Use it to show the experience, not to claim a finding.

- "What is total deposit balance by region?" Regions are close together, 21.4M USD to 24.0M USD.
- "Show CSAT by case type, Agentforce versus human." The two are within 0.12 points on every case type. Agentforce is higher on Fraud, Fee Inquiry and Payments, and lower on the other three.
- **Do not claim** that card disputes spiked at BR-003 and BR-011 after the May 2026 fee change. Without a date filter the top branches sit between 42 and 54 cases. The date-filtered query failed and has not been re-run.

## Close (1 minute)

"Seven lines of business, each installed from a template with its own data. Everything I showed comes from the semantic model, so the answers match the dashboards. The next step is to connect this to your own data."

## What has not been verified

- The analytics agent has not been tested. The External Client App it needs is not set up.
- Dashboards have not been opened in the Tableau Next UI, so rendering and the custom components are unchecked.
- Financial Advisors and Lending have not been queried.
- Questions that name a person or account (Lauren Bailey, Ashford Family Office, Elena Ruiz, Meridian Logistics) have not been run.
- Date-filtered questions have not been run because the filter syntax failed.
