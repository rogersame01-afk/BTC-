#!/usr/bin/env python3
"""Validate a generated NovaFlow dataset: keys, relationships, temporal logic,
plus a quick KPI summary so you can sanity-check the business story.

    python data_generator/validate.py [--data data/raw]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

PKS = {
    "sales_reps": "rep_id", "products": "product_id", "marketing_campaigns": "campaign_id",
    "customers": "customer_id", "accounts": "account_id", "leads": "lead_id", "opportunities": "opportunity_id",
    "subscriptions": "subscription_id", "invoices": "invoice_id", "invoice_line_items": "invoice_line_id",
    "payments": "payment_id", "sales_activities": "activity_id", "website_sessions": "session_id",
    "website_events": "event_id", "support_tickets": "ticket_id",
}
FKS = [  # table, column, parent table
    ("sales_reps", "manager_id", "sales_reps"),
    ("customers", "owner_rep_id", "sales_reps"),
    ("accounts", "customer_id", "customers"), ("accounts", "account_manager_id", "sales_reps"),
    ("leads", "campaign_id", "marketing_campaigns"), ("leads", "owner_rep_id", "sales_reps"),
    ("leads", "converted_customer_id", "customers"), ("leads", "converted_opportunity_id", "opportunities"),
    ("opportunities", "customer_id", "customers"), ("opportunities", "account_id", "accounts"),
    ("opportunities", "lead_id", "leads"), ("opportunities", "campaign_id", "marketing_campaigns"),
    ("opportunities", "owner_rep_id", "sales_reps"), ("opportunities", "product_id", "products"),
    ("subscriptions", "account_id", "accounts"), ("subscriptions", "customer_id", "customers"),
    ("subscriptions", "product_id", "products"), ("subscriptions", "opportunity_id", "opportunities"),
    ("invoices", "account_id", "accounts"), ("invoices", "customer_id", "customers"),
    ("invoice_line_items", "invoice_id", "invoices"), ("invoice_line_items", "subscription_id", "subscriptions"),
    ("invoice_line_items", "product_id", "products"), ("invoice_line_items", "opportunity_id", "opportunities"),
    ("payments", "invoice_id", "invoices"), ("payments", "account_id", "accounts"),
    ("sales_activities", "rep_id", "sales_reps"), ("sales_activities", "customer_id", "customers"),
    ("sales_activities", "lead_id", "leads"), ("sales_activities", "opportunity_id", "opportunities"),
    ("website_sessions", "lead_id", "leads"), ("website_sessions", "customer_id", "customers"),
    ("website_sessions", "campaign_id", "marketing_campaigns"),
    ("website_events", "session_id", "website_sessions"),
    ("support_tickets", "customer_id", "customers"), ("support_tickets", "account_id", "accounts"),
    ("support_tickets", "product_id", "products"),
]
# (table, description, pandas query that selects *violating* rows)
LOGIC = [
    ("opportunities", "close_date before created date", "close_date < created_at.dt.normalize()"),
    ("opportunities", "closed-won New Business without account",
     "is_won and opportunity_type == 'New Business' and account_id.isna()"),
    ("leads", "converted before created", "converted_at < created_at"),
    ("leads", "MQL outside created..converted", "mql_at < created_at or mql_at > converted_at"),
    ("subscriptions", "cancelled before start", "cancelled_at < start_date"),
    ("subscriptions", "term end before term start", "current_term_end <= current_term_start"),
    ("invoices", "due before invoice date", "due_date < invoice_date"),
    ("invoices", "paid before invoiced", "paid_date < invoice_date"),
    ("support_tickets", "first response before created", "first_response_at < created_at"),
    ("support_tickets", "resolved before first response", "resolved_at < first_response_at"),
    ("website_sessions", "session ends before it starts", "session_end < session_start"),
]
DATES = {
    "opportunities": ["created_at", "close_date"], "leads": ["created_at", "mql_at", "converted_at"],
    "subscriptions": ["start_date", "cancelled_at", "current_term_start", "current_term_end"],
    "invoices": ["invoice_date", "due_date", "paid_date"], "payments": ["payment_date"],
    "support_tickets": ["created_at", "first_response_at", "resolved_at"],
    "website_sessions": ["session_start", "session_end"], "website_events": ["event_timestamp"],
    "customers": ["created_at", "customer_since", "churned_at"],
}
EXPECTED_DUPLICATE_PKS = {"website_events"}  # tracker double-fires injected on purpose


def load(data: Path):
    fmt = "parquet" if (data / "customers.parquet").exists() else "csv"
    t = {}
    for name in PKS:
        path = data / f"{name}.{fmt}"
        df = pd.read_parquet(path) if fmt == "parquet" else pd.read_csv(path, low_memory=False)
        for c in DATES.get(name, []):
            df[c] = pd.to_datetime(df[c])
        t[name] = df
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=REPO_ROOT / "data" / "raw")
    t = load(ap.parse_args().data)
    failures = 0

    print("== Row counts")
    for k, v in t.items():
        print(f"  {k:<22}{len(v):>12,}")

    print("\n== Primary keys")
    for name, pk in PKS.items():
        dups = t[name][pk].duplicated().sum()
        exact = t[name].duplicated().sum()
        ok = dups == 0 or (name in EXPECTED_DUPLICATE_PKS and dups == exact)
        failures += not ok
        note = f" ({dups:,} exact duplicate rows, expected)" if dups and ok else (f" {dups:,} DUPLICATES" if dups else "")
        print(f"  {'OK ' if ok else 'FAIL'} {name}.{pk}{note}")

    print("\n== Foreign keys")
    for child, col, parent in FKS:
        vals = t[child][col].dropna()
        orphans = (~vals.isin(t[parent][PKS[parent]])).sum()
        failures += orphans > 0
        print(f"  {'OK ' if not orphans else 'FAIL'} {child}.{col} -> {parent} ({len(vals):,} refs, {orphans:,} orphans)")

    print("\n== Business logic")
    for name, desc, q in LOGIC:
        bad = len(t[name].query(q, engine="python"))
        failures += bad > 0
        print(f"  {'OK ' if not bad else 'FAIL'} {name}: {desc} ({bad:,})")
    ev = t["website_events"].merge(t["website_sessions"][["session_id", "session_start", "session_end"]], on="session_id")
    bad = ((ev.event_timestamp < ev.session_start) | (ev.event_timestamp > ev.session_end)).sum()
    failures += bad > 0
    print(f"  {'OK ' if not bad else 'FAIL'} website_events: event outside its session window ({bad:,})")
    o = t["opportunities"][["opportunity_id", "created_at", "customer_id"]]
    act = t["sales_activities"].merge(o[["opportunity_id", "created_at"]], on="opportunity_id")
    bad = (pd.to_datetime(act.activity_at).dt.normalize() < act.created_at.dt.normalize()).sum()
    failures += bad > 0
    print(f"  {'OK ' if not bad else 'FAIL'} sales_activities: activity before its opportunity was created ({bad:,})")
    first = o.groupby("customer_id").created_at.min()
    c = t["customers"].set_index("customer_id")
    bad = (c.created_at.reindex(first.index) > first).sum()
    failures += bad > 0
    print(f"  {'OK ' if not bad else 'FAIL'} customers: created after their first opportunity ({bad:,})")
    inv, pay = t["invoices"], t["payments"]
    net = pay[pay.status == "Succeeded"].query("payment_type == 'charge'").groupby("invoice_id").amount.sum()
    paid = inv[inv.status == "Paid"].set_index("invoice_id").total_amount
    bad = ((net.reindex(paid.index).fillna(0) - paid).abs() > 0.02).sum()
    failures += bad > 0
    print(f"  {'OK ' if not bad else 'FAIL'} invoices: paid invoices fully covered by payments ({bad:,})")

    print("\n== KPI snapshot")
    o = t["opportunities"]
    closed = o[o.is_closed]
    seg = t["customers"].set_index("customer_id").segment
    closed = closed.assign(segment=closed.customer_id.map(seg))
    wr = closed.groupby(["opportunity_type", "segment"]).is_won.mean().unstack().round(3)
    print("  Win rate by type x segment:\n" + "\n".join("    " + l for l in wr.to_string().splitlines()))
    s = t["subscriptions"]
    print(f"  Active ARR: ${s[s.status == 'Active'].arr_usd.sum() / 1e6:,.1f}M across "
          f"{s[s.status == 'Active'].customer_id.nunique():,} customers")
    print("  Lifecycle stages: " + ", ".join(f"{k}={v:,}" for k, v in t["customers"].lifecycle_stage.value_counts().items()))
    l = t["leads"]
    print(f"  Lead -> opportunity conversion: {l.converted_opportunity_id.notna().mean():.1%}")
    ws = t["website_sessions"]
    print(f"  Website: {ws.converted.mean():.1%} session conversion, {ws.is_bounce.mean():.1%} bounce rate")
    cs = t["support_tickets"]
    churn = t["customers"].set_index("customer_id").lifecycle_stage
    print("  Avg CSAT (churned vs retained): " +
          ", ".join(f"{k}={v:.2f}" for k, v in cs.groupby(cs.customer_id.map(churn)).csat_score.mean().items()))
    print(f"  Payments collected: ${pay[pay.status == 'Succeeded'].amount_usd.sum() / 1e6:,.1f}M")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{failures} CHECK(S) FAILED'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
