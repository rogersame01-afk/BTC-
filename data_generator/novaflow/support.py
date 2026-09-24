"""Support tickets. Volume, severity and satisfaction are driven by segment
and the customer's hidden health score (unhealthy customers file more
tickets, rate support lower, and churn more)."""
import numpy as np
import pandas as pd

from .config import N_SUPPORT_AGENTS, SEGMENTS
from .utils import DAY_SECONDS, END_ORD, EPOCH_ORD, business_seconds, make_ids, weekday_shift

CATEGORIES = {  # weight, median resolution hours
    "How-to / Usage": (0.24, 6), "Bug": (0.17, 48), "Integration / Connectors": (0.14, 30),
    "Data Quality": (0.10, 30), "Billing": (0.09, 12), "Account Access / SSO": (0.09, 4),
    "Performance": (0.08, 36), "Feature Request": (0.09, 120),
}
SUBJECTS = {
    "How-to / Usage": ["How do I schedule a dashboard?", "Question about calculated fields", "Sharing dashboards externally",
                       "Best practice for row-level security", "Filters not behaving as expected"],
    "Bug": ["Chart fails to render", "Export to PDF is blank", "Error 500 when saving dashboard",
            "Drill-down returns wrong results", "Alert emails not sent"],
    "Integration / Connectors": ["Snowflake connector timing out", "BigQuery sync failed", "Salesforce connector auth error",
                                 "HubSpot fields missing", "Postgres connector SSL error"],
    "Data Quality": ["Numbers don't match source", "Duplicate rows in dataset", "Timezone offset in reports",
                     "Stale data after refresh"],
    "Billing": ["Invoice question", "Update billing contact", "Seat count incorrect on invoice", "Request W-9 / VAT info",
                "Refund request"],
    "Account Access / SSO": ["Locked out of account", "Okta SSO misconfigured", "Add new admin", "2FA reset request"],
    "Performance": ["Dashboards loading slowly", "Query timeouts on large dataset", "Slow API responses"],
    "Feature Request": ["Request: dark mode", "Request: more chart types", "Request: Git integration",
                        "Request: custom fonts in embeds"],
}
PRIORITY_MIX = {"Enterprise": [0.08, 0.25, 0.45, 0.22], "Mid-Market": [0.04, 0.2, 0.48, 0.28],
                "SMB": [0.03, 0.15, 0.5, 0.32]}
PRIORITIES = ["Urgent", "High", "Medium", "Low"]
FIRST_RESPONSE_MED = {"Urgent": 25, "High": 90, "Medium": 240, "Low": 600}
SLA_MINUTES = {"Urgent": 60, "High": 240, "Medium": 480, "Low": 1440}


def build_support(rng, fake, customers, accounts, subs, health_by_customer, target):
    paying = customers[customers.customer_since_ord > 0].copy()
    start = paying.customer_since_ord.values.astype(np.int64)
    end = np.where(paying.churned_ord.values > 0, paying.churned_ord.values, END_ORD).astype(np.int64)
    months = np.maximum(end - start, 1) / 30.4
    health = paying.customer_id.map(health_by_customer).values
    lam = months * paying.segment.map({k: v["ticket_rate"] for k, v in SEGMENTS.items()}).values * (1.7 - health)
    n_t = rng.poisson(lam * target / lam.sum())
    ci = np.repeat(np.arange(len(paying)), n_t)
    n = len(ci)
    window = end[ci] - start[ci]
    early = rng.random(n) < 0.3  # onboarding bump
    day = start[ci] + np.floor(np.where(early, rng.random(n) * np.minimum(60, window), rng.random(n) * window)).astype(np.int64)
    day = np.minimum(weekday_shift(day, rng, keep_weekend=0.25), END_ORD)
    created = (day - EPOCH_ORD) * DAY_SECONDS + business_seconds(rng, n)

    cid = paying.customer_id.values[ci]
    seg = paying.segment.values[ci]
    h = health[ci]

    # account: production or business-unit account of the customer
    acc = accounts[accounts.account_type.isin(["Production", "Business Unit"])]
    acc_lists = acc.groupby("customer_id").account_id.apply(list)
    account_id = [a[0] if len(a) == 1 or r < 0.75 else a[int(r * 100) % len(a)]
                  for a, r in zip(acc_lists.loc[cid].values, rng.random(n))]
    prod_lists = subs.groupby("customer_id").product_id.apply(lambda s: list(dict.fromkeys(s)))
    product_id = [p[0] if len(p) == 1 or r < 0.6 else p[int(r * 1000) % len(p)]
                  for p, r in zip(prod_lists.loc[cid].values, rng.random(n))]

    priority = np.empty(n, dtype=object)
    for s, mix in PRIORITY_MIX.items():
        m = seg == s
        priority[m] = rng.choice(PRIORITIES, m.sum(), p=mix)
    cats = list(CATEGORIES)
    category = rng.choice(cats, n, p=[CATEGORIES[c][0] for c in cats])
    channel = rng.choice(["Email", "Chat", "Web Form", "Phone"], n, p=[0.38, 0.3, 0.2, 0.12])
    channel[(channel == "Phone") & (seg == "SMB")] = "Chat"

    fr_med = np.array([FIRST_RESPONSE_MED[p] for p in priority]) * \
        np.select([channel == "Chat", channel == "Phone"], [0.3, 0.1], 1.0)
    first_resp = np.maximum(1, np.round(rng.lognormal(np.log(fr_med), 0.8))).astype(np.int64)
    res_med = np.array([CATEGORIES[c][1] for c in category]) * \
        np.select([priority == "Urgent", priority == "High"], [0.5, 0.75], 1.0) * (1.4 - 0.5 * h)
    res_hours = np.maximum(first_resp / 60 + 0.1, rng.lognormal(np.log(res_med), 0.9))
    resolved = created + (res_hours * 3600).astype(np.int64)
    closed = resolved + rng.integers(1, 4, n) * DAY_SECONDS
    snap = (END_ORD - EPOCH_ORD + 1) * DAY_SECONDS
    first_resp_ts = created + first_resp * 60

    status = np.where(closed <= snap, "Closed", "Resolved").astype(object)
    unresolved = resolved > snap
    status[unresolved] = rng.choice(["Open", "Pending Customer", "In Progress"], unresolved.sum(), p=[0.35, 0.3, 0.35])
    no_first = first_resp_ts > snap
    status[no_first] = "New"

    sla_breached = first_resp > np.array([SLA_MINUTES[p] for p in priority])
    responded = (~unresolved) & (rng.random(n) < 0.55)
    score = 2.1 + 2.9 * h - 0.5 * (res_hours > 72) - 0.4 * sla_breached + rng.normal(0, 0.7, n)
    csat = np.where(responded, np.clip(np.round(score), 1, 5), np.nan)

    agents = [fake.name() for _ in range(N_SUPPORT_AGENTS)]
    tier2 = agents[: N_SUPPORT_AGENTS // 4]
    agent = np.where(np.isin(priority, ["Urgent", "High"]) & (rng.random(n) < 0.7),
                     np.array(tier2, dtype=object)[rng.integers(0, len(tier2), n)],
                     np.array(agents, dtype=object)[rng.integers(0, len(agents), n)])
    domain = paying.domain.values[ci]
    requester = [f"{fake.first_name().lower()}@{d}" for d in domain]
    subject = [SUBJECTS[c][k % len(SUBJECTS[c])] for c, k in zip(category, rng.integers(0, 100, n))]

    ts = lambda a: a.astype("datetime64[s]")
    t = pd.DataFrame({
        "customer_id": cid, "account_id": account_id, "product_id": product_id,
        "requester_email": requester, "subject": subject, "category": category, "priority": priority,
        "channel": channel, "status": status, "assigned_agent": agent,
        "created_at": ts(created),
        "first_response_at": np.where(no_first, np.datetime64("NaT"), ts(first_resp_ts)),
        "resolved_at": np.where(unresolved, np.datetime64("NaT"), ts(resolved)),
        "closed_at": np.where(status == "Closed", ts(closed), np.datetime64("NaT")),
        "first_response_minutes": pd.array(np.where(no_first, np.nan, first_resp), dtype="Int64"),
        "sla_breached": np.where(no_first, False, sla_breached),
        "csat_score": pd.array(csat, dtype="Int64"),
    })
    t = t.sort_values("created_at", kind="stable").reset_index(drop=True)
    t.insert(0, "ticket_id", make_ids("TKT", n, width=6))
    return t
