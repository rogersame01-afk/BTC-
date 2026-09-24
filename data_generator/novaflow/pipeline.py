"""Orchestrates generation of every NovaFlow table and writes them to disk."""
import json
import time
from pathlib import Path
from random import Random

import numpy as np
import pandas as pd
from faker import Faker

from . import quality
from .activities import build_activities
from .billing import build_billing
from .config import END_DATE, N_SALES_REPS, START_DATE, TARGETS
from .customers import build_customers
from .leads import build_leads
from .lifecycle import Lifecycle
from .reference import (RepPicker, build_campaigns, build_products, build_sales_reps, finalize_campaigns,
                        finalize_sales_reps)
from .support import build_support
from .utils import business_seconds, ord_to_date, ord_to_ts
from .web import build_web


def _forecast(prob, closed, won):
    return np.select([closed & won, closed, prob <= 30, prob <= 60], ["Closed", "Omitted", "Pipeline", "Best Case"],
                     "Commit")


def generate(scale: float = 1.0, seed: int = 42, dirty: bool = True, log=print) -> dict:
    t0 = time.time()
    step = lambda msg: log(f"[{time.time() - t0:6.1f}s] {msg}")
    targets = {k: max(10, int(v * scale)) for k, v in TARGETS.items()}
    rng = np.random.default_rng(seed)
    fake = Faker("en_US")
    Faker.seed(seed)

    step("reference data: sales reps, products, campaigns")
    reps, skill = build_sales_reps(rng, fake, N_SALES_REPS)
    products = build_products()
    campaigns = build_campaigns(rng, fake)

    step(f"customers ({targets['customers']:,})")
    customers, hidden = build_customers(rng, fake, targets["customers"])
    health = pd.Series(hidden["health"], index=customers.customer_id.values)

    step("customer lifecycle: opportunities, accounts, subscriptions")
    lc = Lifecycle(customers, hidden, reps, skill, products, seed)
    owner, since, churned = lc.run()
    customers["owner_rep_id"] = owner
    customers["customer_since_ord"] = since
    customers["churned_ord"] = churned
    opps = pd.DataFrame(lc.opps)
    opps["created_sec"] = business_seconds(rng, len(opps))
    subs = pd.DataFrame(lc.subs)
    accounts = pd.DataFrame(lc.accounts)
    charges = pd.DataFrame(lc.charges)

    step(f"leads ({targets['leads']:,})")
    picker = RepPicker(reps, Random(seed + 1))
    leads = build_leads(rng, fake, customers, opps, campaigns, picker, targets["leads"])
    conv = leads.dropna(subset=["converted_opportunity_id"]).set_index("converted_opportunity_id")
    opps["lead_id"] = opps.opportunity_id.map(conv.lead_id)
    opps["campaign_id"] = opps.opportunity_id.map(conv.campaign_id)

    step(f"website sessions ({targets['website_sessions']:,}) and events ({targets['website_events']:,})")
    sessions, events = build_web(rng, leads, customers, subs, campaigns, targets["website_sessions"],
                                 targets["website_events"])

    step(f"sales activities ({targets['sales_activities']:,})")
    activities = build_activities(rng, opps, leads, customers, reps, targets["sales_activities"])

    step(f"support tickets ({targets['support_tickets']:,})")
    tickets = build_support(rng, fake, customers, accounts, subs, health, targets["support_tickets"])

    step("billing: invoices, invoice lines, payments")
    invoices, invoice_lines, payments = build_billing(rng, seed, subs, charges, accounts, customers, health)

    step("finalising tables")
    cust_final = _customers(customers)
    first_touch = pd.concat([
        pd.Series(ord_to_ts(opps.created_ord, opps.created_sec), index=opps.customer_id.values),
        pd.Series(ord_to_ts(leads.created_ord, leads.created_sec), index=leads.converted_customer_id.values),
    ]).dropna()
    first_touch = first_touch[first_touch.index.notna()].groupby(level=0).min()
    cust_final["created_at"] = np.minimum(cust_final.created_at.values,
                                          cust_final.customer_id.map(first_touch).fillna(cust_final.created_at).values)
    tables = {
        "sales_reps": finalize_sales_reps(reps),
        "products": products,
        "marketing_campaigns": finalize_campaigns(campaigns),
        "customers": cust_final,
        "accounts": _accounts(accounts),
        "leads": _leads(leads),
        "opportunities": _opps(opps),
        "subscriptions": _subs(subs, rng),
        "invoices": invoices,
        "invoice_line_items": invoice_lines,
        "payments": payments,
        "sales_activities": _activities(activities),
        "website_sessions": sessions,
        "website_events": events,
        "support_tickets": tickets,
    }
    if dirty:
        step("injecting documented data-quality issues")
        tables = quality.inject(np.random.default_rng(seed + 99), tables)
    step("done generating")
    return tables


# ---------------------------------------------------------------- finalisers
def _customers(c):
    stage = np.where(c.churned_ord > 0, "Churned", np.where(c.customer_since_ord > 0, "Customer", "Prospect"))
    sec = np.random.default_rng(0).integers(8 * 3600, 19 * 3600, len(c))
    return pd.DataFrame({
        "customer_id": c.customer_id, "company_name": c.company_name, "domain": c.domain, "website": c.website,
        "industry": c.industry, "segment": c.segment, "employee_count": c.employee_count,
        "annual_revenue_usd": c.annual_revenue_usd, "region": c.region, "country": c.country, "city": c.city,
        "phone": c.phone, "acquisition_source": c.acquisition_source, "owner_rep_id": c.owner_rep_id,
        "lifecycle_stage": stage, "created_at": ord_to_ts(c.created_ord, sec),
        "customer_since": ord_to_date(c.customer_since_ord), "churned_at": ord_to_date(c.churned_ord),
    })


def _accounts(a):
    out = a.copy()
    out["created_at"] = ord_to_date(out.pop("created_ord"))
    out["churned_at"] = ord_to_date(out.pop("churned_ord"))
    out.loc[out.account_type == "Trial", "health_score"] = np.nan
    out["health_score"] = out["health_score"].astype("Int64")
    return out[["account_id", "customer_id", "account_name", "account_type", "status", "created_at", "churned_at",
                "account_manager_id", "billing_country", "billing_currency", "health_score"]]


def _leads(l):
    return pd.DataFrame({
        "lead_id": l.lead_id, "first_name": l.first_name, "last_name": l.last_name, "email": l.email,
        "phone": l.phone, "title": l.title, "company_name": l.company_name, "company_domain": l.company_domain,
        "industry": l.industry, "employee_count": l.employee_count, "company_size": l.company_size,
        "country": l.country, "region": l.region, "lead_source": l.lead_source, "campaign_id": l.campaign_id,
        "owner_rep_id": l.owner_rep_id, "lead_score": l.lead_score, "status": l.status,
        "created_at": ord_to_ts(l.created_ord, l.created_sec), "mql_at": ord_to_ts(l.mql_ord, l.mql_sec),
        "converted_at": ord_to_ts(l.converted_ord, l.converted_sec),
        "converted_customer_id": l.converted_customer_id, "converted_opportunity_id": l.converted_opportunity_id,
        "disqualification_reason": l.disqualification_reason,
    })


def _opps(o):
    return pd.DataFrame({
        "opportunity_id": o.opportunity_id, "opportunity_name": o.opportunity_name, "customer_id": o.customer_id,
        "account_id": o.account_id, "lead_id": o.lead_id, "campaign_id": o.campaign_id,
        "owner_rep_id": o.owner_rep_id, "product_id": o.product_id, "opportunity_type": o.opportunity_type,
        "lead_source": o.lead_source, "stage_name": o.stage_name, "stage_before_close": o.last_stage,
        "probability": o.probability, "forecast_category": _forecast(o.probability, o.is_closed, o.is_won),
        "amount_usd": o.amount, "quantity": o.seats, "discount_pct": o.discount_pct,
        "created_at": ord_to_ts(o.created_ord, o.created_sec), "close_date": ord_to_date(o.close_ord),
        "is_closed": o.is_closed, "is_won": o.is_won, "loss_reason": o.loss_reason,
    })


def _subs(s, rng):
    active = s.end_ord < 0
    return pd.DataFrame({
        "subscription_id": s.subscription_id, "account_id": s.account_id, "customer_id": s.customer_id,
        "product_id": s.product_id, "opportunity_id": s.opportunity_id,
        "status": np.where(active, "Active", "Cancelled"), "billing_frequency": s.billing_frequency,
        "term_months": s.term_months, "start_date": ord_to_date(s.start_ord),
        "current_term_start": ord_to_date(s.current_term_start_ord),
        "current_term_end": ord_to_date(s.current_term_end_ord), "cancelled_at": ord_to_date(s.end_ord),
        "quantity": s.quantity, "list_unit_price_usd": s.list_unit_price, "discount_pct": s.discount_pct,
        "mrr_usd": s.mrr, "arr_usd": (s.mrr * 12).round(2),
        "auto_renew": np.where(s.billing_frequency == "Monthly", True, rng.random(len(s)) < 0.65),
        "churn_reason": s.churn_reason,
    })


def _activities(a):
    return pd.DataFrame({
        "activity_id": a.activity_id, "activity_type": a.activity_type, "activity_at": ord_to_ts(a.day, a.sec),
        "rep_id": a.rep_id, "customer_id": a.customer_id, "lead_id": a.lead_id, "opportunity_id": a.opportunity_id,
        "direction": a.direction, "subject": a.subject, "outcome": a.outcome, "duration_minutes": a.duration_minutes,
    })


# ---------------------------------------------------------------- output
def _dates_as_dates(df):
    """Columns whose values are all midnight are calendar dates, not timestamps."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            v = df[col].dropna()
            if len(v) and (v == v.dt.normalize()).all():
                df[col] = df[col].dt.date
    return df


def write(tables: dict, out_dir: Path, fmt: str = "csv", meta: dict | None = None, log=print):
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, df in tables.items():
        df = _dates_as_dates(df)
        path = out_dir / f"{name}.{fmt}"
        if fmt == "parquet":
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, index=False, date_format="%Y-%m-%d %H:%M:%S")
        counts[name] = len(df)
        log(f"  wrote {path} ({len(df):,} rows)")
    manifest = {"company": "NovaFlow", "data_start": str(START_DATE), "snapshot_date": str(END_DATE),
                "format": fmt, "row_counts": counts, **(meta or {})}
    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    return counts
