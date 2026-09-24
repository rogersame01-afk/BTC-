"""Reference / dimension data: sales reps, products, marketing campaigns."""
import re
from datetime import date

import numpy as np
import pandas as pd

from .config import CAMPAIGN_CHANNELS, CAMPAIGN_THEMES, N_CAMPAIGNS, REGIONS, SEGMENTS
from .utils import END_ORD, START_ORD, fmt_id, growth_day_ordinals, ord_to_date

REGION_NAMES = list(REGIONS)
REGION_CODES = {"North America": "NA", "EMEA": "EMEA", "APAC": "APAC", "LATAM": "LATAM"}


# --------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------
PRODUCTS = [
    # id, sku, name, family, tier, pricing_model, list_price (monthly per seat/flat, or one-time), launch
    ("PRD-001", "NF-PLT-STR", "NovaFlow Analytics Starter", "Platform", "Starter", "per_seat", 20, date(2019, 3, 1)),
    ("PRD-002", "NF-PLT-PRO", "NovaFlow Analytics Professional", "Platform", "Professional", "per_seat", 45, date(2019, 3, 1)),
    ("PRD-003", "NF-PLT-ENT", "NovaFlow Analytics Enterprise", "Platform", "Enterprise", "per_seat", 85, date(2020, 1, 15)),
    ("PRD-004", "NF-ADD-AI", "NovaFlow AI Insights", "Add-on", None, "per_seat", 12, date(2023, 6, 1)),
    ("PRD-005", "NF-ADD-CONN", "Premium Connectors Pack", "Add-on", None, "flat", 500, date(2020, 6, 1)),
    ("PRD-006", "NF-ADD-EMB", "Embedded Analytics", "Add-on", None, "flat", 1500, date(2021, 4, 1)),
    ("PRD-007", "NF-ADD-GOV", "Governance & Security Suite", "Add-on", None, "flat", 900, date(2021, 9, 1)),
    ("PRD-008", "NF-ADD-SYNC", "FlowSync Reverse ETL", "Add-on", None, "flat", 700, date(2022, 9, 1)),
    ("PRD-009", "NF-ADD-RT", "Real-time Streaming", "Add-on", None, "flat", 1200, date(2024, 3, 1)),
    ("PRD-010", "NF-SUP-PRM", "Premium Support", "Add-on", None, "flat", 400, date(2020, 1, 1)),
    ("PRD-011", "NF-SVC-ONB", "Onboarding & Implementation", "Services", None, "one_time", 15000, date(2019, 3, 1)),
    ("PRD-012", "NF-SVC-TRN", "Analytics Training Workshop", "Services", None, "one_time", 4000, date(2019, 3, 1)),
]
PLATFORM_BY_TIER = {"Starter": "PRD-001", "Professional": "PRD-002", "Enterprise": "PRD-003"}
ADDONS_BY_SEGMENT = {  # which add-ons each segment realistically buys, with relative weights
    "SMB": {"PRD-004": 4, "PRD-005": 3, "PRD-010": 2, "PRD-008": 1},
    "Mid-Market": {"PRD-004": 4, "PRD-005": 3, "PRD-006": 2, "PRD-008": 2, "PRD-010": 2, "PRD-007": 1, "PRD-009": 1},
    "Enterprise": {"PRD-004": 3, "PRD-006": 3, "PRD-007": 3, "PRD-009": 2, "PRD-008": 2, "PRD-010": 2, "PRD-005": 1},
}


def build_products() -> pd.DataFrame:
    df = pd.DataFrame(PRODUCTS, columns=["product_id", "sku", "product_name", "product_family", "tier",
                                         "pricing_model", "list_price_usd", "launch_date"])
    df["billing_unit"] = df["pricing_model"].map(
        {"per_seat": "seat / month", "flat": "account / month", "one_time": "one-time"})
    df["launch_date"] = pd.to_datetime(df["launch_date"])
    df["is_active"] = True
    return df


# --------------------------------------------------------------------------
# Sales reps
# --------------------------------------------------------------------------
def build_sales_reps(rng, fake, n_reps: int):
    """Sales org: 1 VP, 4 regional directors, 4 managers per region, ICs."""
    rows = []
    skill = {}

    def person():
        first, last = fake.first_name(), fake.last_name()
        return first, last

    def hire(early_share):
        if rng.random() < early_share:
            return date(2017, 1, 1).toordinal() + int(rng.integers(0, (START_ORD - date(2017, 1, 1).toordinal())))
        return int(growth_day_ordinals(rng, 1, START_ORD, END_ORD - 60, growth=0.8)[0])

    def add(role, title, region, segment, team, manager_id, early_share, quota, can_leave=True):
        rid = fmt_id("REP", len(rows) + 1, 4)
        first, last = person()
        h = hire(early_share)
        term = -1
        if can_leave and rng.random() < 0.18:
            t = h + int(rng.integers(200, 1300))
            term = t if START_ORD + 120 < t < END_ORD else -1
        rows.append(dict(rep_id=rid, first_name=first, last_name=last, full_name=f"{first} {last}",
                         email=f"{first}.{last}".lower().replace("'", "") + "@novaflow.io",
                         role=role, title=title, region=region, segment=segment, team=team,
                         manager_id=manager_id, hire_ord=h, term_ord=term, annual_quota_usd=quota))
        skill[rid] = float(np.clip(rng.normal(1.0, 0.18), 0.6, 1.45))
        return rid

    vp = add("VP", "VP of Sales", "Global", None, "Leadership", None, 1.0, None, can_leave=False)
    n_ic = n_reps - 1 - 4 - 16
    region_w = np.array([REGIONS[r]["weight"] for r in REGION_NAMES])
    region_w = np.maximum(region_w, 0.08)
    region_w /= region_w.sum()
    for region in REGION_NAMES:
        d = add("Director", "Regional Sales Director", region, None, "Leadership", vp, 1.0, None, can_leave=False)
        mgr = {
            "SDR": add("Manager", "SDR Manager", region, None, "Sales Development", d, 0.9, None, False),
            "AE-COM": add("Manager", "Sales Manager, Commercial", region, None, "Commercial Sales", d, 0.9, None, False),
            "AE-ENT": add("Manager", "Sales Manager, Enterprise", region, None, "Enterprise Sales", d, 0.9, None, False),
            "AM": add("Manager", "Account Management Lead", region, None, "Account Management", d, 0.9, None, False),
        }
        n_region = int(round(n_ic * region_w[REGION_NAMES.index(region)]))
        roles = rng.choice(["SDR", "AE", "AM"], size=n_region, p=[0.34, 0.46, 0.20])
        for role in roles:
            if role == "SDR":
                add("SDR", "Sales Development Representative", region, None, "Sales Development", mgr["SDR"],
                    0.45, None)
            elif role == "AM":
                add("AM", "Account Manager", region, None, "Account Management", mgr["AM"], 0.5, 1_000_000)
            else:
                seg = rng.choice(list(SEGMENTS), p=[0.45, 0.33, 0.22])
                senior = rng.random() < 0.3
                quota = {"SMB": 500_000, "Mid-Market": 850_000, "Enterprise": 1_300_000}[seg]
                add("AE", ("Senior " if senior else "") + "Account Executive", region, seg,
                    "Enterprise Sales" if seg == "Enterprise" else "Commercial Sales",
                    mgr["AE-ENT" if seg == "Enterprise" else "AE-COM"], 0.5, int(quota * (1.2 if senior else 1)))
    # guarantee at least one long-tenured AE per region/segment and AM per region
    for region in REGION_NAMES:
        for seg in SEGMENTS:
            if not any(r["role"] == "AE" and r["region"] == region and r["segment"] == seg and r["term_ord"] < 0
                       and r["hire_ord"] < START_ORD for r in rows):
                add("AE", "Account Executive", region, seg,
                    "Enterprise Sales" if seg == "Enterprise" else "Commercial Sales", None, 1.0,
                    {"SMB": 500_000, "Mid-Market": 850_000, "Enterprise": 1_300_000}[seg], can_leave=False)
        for role, title in (("AM", "Account Manager"), ("SDR", "Sales Development Representative")):
            if not any(r["role"] == role and r["region"] == region and r["term_ord"] < 0
                       and r["hire_ord"] < START_ORD for r in rows):
                add(role, title, region, None, "Account Management" if role == "AM" else "Sales Development",
                    None, 1.0, 1_000_000 if role == "AM" else None, can_leave=False)
    # backfill manager for guaranteed hires
    df = pd.DataFrame(rows)
    mgr_lookup = df[df.role == "Manager"].set_index(["region", "team"])["rep_id"].to_dict()
    missing = df.manager_id.isna() & ~df.role.isin(["VP"])
    df.loc[missing, "manager_id"] = [mgr_lookup.get((r, t)) for r, t in zip(df.region[missing], df.team[missing])]
    return df, skill


def finalize_sales_reps(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["hire_date"] = ord_to_date(out.pop("hire_ord"))
    out["termination_date"] = ord_to_date(out.pop("term_ord"))
    out["is_active"] = out["termination_date"].isna()
    out["annual_quota_usd"] = out["annual_quota_usd"].astype("Int64")
    return out


class RepPicker:
    """Picks a rep of a given role/region/segment who is employed on a given day."""

    def __init__(self, reps: pd.DataFrame, py_rng):
        self.py = py_rng
        self.groups = {}
        for r in reps.itertuples():
            if r.role not in ("SDR", "AE", "AM"):
                continue
            seg = r.segment if r.role == "AE" else None
            self.groups.setdefault((r.role, r.region, seg), []).append((r.rep_id, r.hire_ord, r.term_ord))
        self.cache = {}

    def pick(self, role, region, segment, day):
        seg = segment if role == "AE" else None
        bucket = (day - START_ORD) // 30
        key = (role, region, seg, bucket)
        eligible = self.cache.get(key)
        if eligible is None:
            group = self.groups[(role, region, seg)]
            eligible = [rid for rid, h, t in group if h <= day and (t < 0 or t > day)] or [g[0] for g in group]
            self.cache[key] = eligible
        return eligible[self.py.randrange(len(eligible))]


# --------------------------------------------------------------------------
# Campaigns
# --------------------------------------------------------------------------
def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build_campaigns(rng, fake) -> pd.DataFrame:
    channels = list(CAMPAIGN_CHANNELS)
    w = np.array([CAMPAIGN_CHANNELS[c][0] for c in channels])
    ch = rng.choice(channels, size=N_CAMPAIGNS, p=w / w.sum())
    starts = np.sort(growth_day_ordinals(rng, N_CAMPAIGNS, START_ORD - 60, END_ORD - 20, growth=0.9,
                                         weekend_factor=0.1))
    marketers = [fake.name() for _ in range(14)]
    rows = []
    for i, (c, s) in enumerate(zip(ch, starts)):
        _, dur, budget_rng, ctype = CAMPAIGN_CHANNELS[c]
        s = int(s)
        e = s + int(rng.integers(dur[0], dur[1] + 1))
        region = "Global" if rng.random() < 0.2 else rng.choice(REGION_NAMES, p=[0.45, 0.3, 0.17, 0.08])
        segment = "Enterprise" if c == "ABM" else rng.choice(["All", "SMB", "Mid-Market", "Enterprise"],
                                                             p=[0.55, 0.2, 0.15, 0.1])
        theme = CAMPAIGN_THEMES[int(rng.integers(len(CAMPAIGN_THEMES)))]
        d = date.fromordinal(s)
        name = f"{d.year}-Q{(d.month - 1) // 3 + 1} {REGION_CODES.get(region, 'GLOBAL')} {c} - {theme}"
        budget = float(np.round(rng.uniform(*budget_rng) * (1 + 0.25 * (d.year - 2022)), -2))
        if e < END_ORD:
            status, spent_share = "Completed", 1.0
        else:
            status, spent_share = "Active", (END_ORD - s) / (e - s)
        actual = round(budget * spent_share * float(np.clip(rng.normal(0.94, 0.1), 0.6, 1.25)), 2)
        rows.append(dict(campaign_id=fmt_id("CMP", i + 1, 4), campaign_name=name, channel=c, campaign_type=ctype,
                         theme=theme, target_region=region, target_segment=segment,
                         start_ord=s, end_ord=e, budget_usd=budget, actual_cost_usd=actual, status=status,
                         owner_name=marketers[int(rng.integers(len(marketers)))],
                         utm_campaign=_slug(f"{d.year}q{(d.month - 1) // 3 + 1}-{c}-{theme}")[:60] + f"-{i + 1}"))
    return pd.DataFrame(rows)


def finalize_campaigns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["start_date"] = ord_to_date(out.pop("start_ord"))
    out["end_date"] = ord_to_date(out.pop("end_ord"))
    return out
