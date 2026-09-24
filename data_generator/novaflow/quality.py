"""Optional, documented data-quality issues so the staging layer has real
cleaning work to do. Every issue here is listed in data_generator/README.md."""
import numpy as np
import pandas as pd

from .utils import make_ids


def _pick(rng, n, rate):
    return rng.random(n) < rate


def inject(rng, t: dict) -> dict:
    # customers: messy industry labels, missing country
    c = t["customers"]
    m = _pick(rng, len(c), 0.02)
    c.loc[m, "industry"] = [s.lower() if r < 0.5 else f" {s} " for s, r in zip(c.loc[m, "industry"], rng.random(m.sum()))]
    c.loc[_pick(rng, len(c), 0.01), "country"] = None

    # leads: duplicate submissions, casing / null emails, inconsistent source labels
    l = t["leads"]
    dup = l[_pick(rng, len(l), 0.015)].copy()
    dup["created_at"] = dup["created_at"] + pd.to_timedelta(rng.integers(1, 10 * 86400, len(dup)), unit="s")
    dup["status"] = "New"
    for col in ("converted_at", "converted_customer_id", "converted_opportunity_id", "mql_at", "disqualification_reason"):
        dup[col] = None
    dup["lead_id"] = make_ids("LEAD", len(dup), start=len(l) + 1)
    l = pd.concat([l, dup], ignore_index=True)
    m = _pick(rng, len(l), 0.03)
    l.loc[m, "email"] = l.loc[m, "email"].str.upper()
    l.loc[_pick(rng, len(l), 0.01), "email"] = None
    m = _pick(rng, len(l), 0.01)
    l.loc[m, "lead_source"] = l.loc[m, "lead_source"].str.lower().str.replace(" ", "_")
    t["leads"] = l

    # opportunities: open deals not yet priced
    o = t["opportunities"]
    o.loc[(~o.is_closed) & _pick(rng, len(o), 0.05), "amount_usd"] = np.nan

    # sessions: country code variants
    s = t["website_sessions"]
    us = (s.country == "United States").values
    s.loc[us & _pick(rng, len(s), 0.03), "country"] = rng.choice(["US", "USA", "united states"], 1)[0]

    # events: tracker double-fires (exact duplicate rows)
    e = t["website_events"]
    t["website_events"] = pd.concat([e, e[_pick(rng, len(e), 0.004)]]).sort_values(
        ["event_timestamp", "event_id"], kind="stable").reset_index(drop=True)

    # support: inconsistent priority casing
    k = t["support_tickets"]
    m = _pick(rng, len(k), 0.01)
    k.loc[m, "priority"] = k.loc[m, "priority"].str.upper()
    return t
