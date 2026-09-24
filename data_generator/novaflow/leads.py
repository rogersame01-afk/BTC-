"""Leads: converted leads that sourced New Business opportunities, plus the
much larger pool of leads that never converted."""
import numpy as np
import pandas as pd

from .config import BUYER_TITLES, INDUSTRIES, LEAD_ORIGIN_DEFAULT, LEAD_ORIGIN_SHARE, LEAD_SOURCES, SEGMENTS
from .customers import sample_geo, slugify_company
from .utils import DAY_SECONDS, END_ORD, business_seconds, growth_day_ordinals, make_ids

DISQUALIFY_REASONS = {"Not a Fit": 0.28, "No Budget": 0.2, "Too Small": 0.14, "Student / Personal": 0.1,
                      "Bad Contact Info": 0.1, "Competitor": 0.06, "Duplicate": 0.06, "No Authority": 0.06}


def segment_from_employees(emp):
    return np.where(emp < 200, "SMB", np.where(emp < 2000, "Mid-Market", "Enterprise")).astype(object)


def company_size_bucket(emp):
    bins = [0, 50, 200, 1000, 5000, np.inf]
    labels = ["1-50", "51-200", "201-1000", "1001-5000", "5000+"]
    return pd.cut(emp, bins=bins, labels=labels, right=True).astype(str)


def sample_sources(rng, segment):
    sources = list(LEAD_SOURCES)
    out = np.empty(len(segment), dtype=object)
    for i, s in enumerate(SEGMENTS):
        m = segment == s
        p = np.array([LEAD_SOURCES[k][0][i] for k in sources])
        out[m] = rng.choice(sources, size=m.sum(), p=p / p.sum())
    return out


def assign_campaigns(rng, ords, channels, regions, segments, campaigns):
    """Pick a campaign that was running (±14d) in the lead's region/segment for its channel."""
    ords = np.asarray(ords, dtype=np.int64)
    channels = np.asarray(channels, dtype=object)
    regions = np.asarray(regions, dtype=object)
    segments = np.asarray(segments, dtype=object)
    out = np.full(len(ords), None, dtype=object)
    for ch, camp in campaigns.groupby("channel"):
        idx = np.flatnonzero(channels == ch)
        if not len(idx):
            continue
        cs = camp.start_ord.values - 14
        ce = camp.end_ord.values + 14
        creg = camp.target_region.to_numpy(dtype=object)
        cseg = camp.target_segment.to_numpy(dtype=object)
        ids = camp.campaign_id.to_numpy(dtype=object)
        for chunk in np.array_split(idx, max(1, len(idx) // 20_000)):
            d = ords[chunk][:, None]
            m = (d >= cs) & (d <= ce)
            m &= (creg == "Global") | (creg == regions[chunk][:, None])
            m &= (cseg == "All") | (cseg == segments[chunk][:, None])
            score = np.where(m, rng.random(m.shape), -1)
            best = score.argmax(axis=1)
            has = score[np.arange(len(chunk)), best] >= 0
            out[chunk[has]] = ids[best[has]]
    return out


def _people(fake, rng, n, domains):
    first = [fake.first_name() for _ in range(n)]
    last = [fake.last_name() for _ in range(n)]
    style = rng.random(n)
    emails = []
    for f, l, d, s in zip(first, last, domains, style):
        f2, l2 = f.lower().replace("'", ""), l.lower().replace("'", "")
        local = f"{f2}.{l2}" if s < 0.6 else (f"{f2[0]}{l2}" if s < 0.85 else f2)
        emails.append(f"{local}@{d}")
    return first, last, emails


def build_leads(rng, fake, customers, opps, campaigns, picker, target):
    cust = customers.set_index("customer_id")

    # ---------------- converted leads (source of first New Business opp)
    nb = opps[opps.opportunity_type == "New Business"].drop_duplicates("customer_id")
    share = nb.lead_source.map(LEAD_ORIGIN_SHARE).fillna(LEAD_ORIGIN_DEFAULT).values
    nb = nb[rng.random(len(nb)) < share]
    c = cust.loc[nb.customer_id]
    opp_ord = nb.created_ord.values.astype(np.int64)
    c_ord = np.minimum(c.created_ord.values.astype(np.int64), opp_ord)
    lead_ord = c_ord + np.floor(rng.random(len(nb)) * (opp_ord - c_ord)).astype(np.int64)
    opp_sec = nb.created_sec.values
    lead_sec = np.where(lead_ord == opp_ord, (opp_sec * rng.uniform(0.2, 0.9, len(nb))).astype(np.int64),
                        business_seconds(rng, len(nb)))
    conv = pd.DataFrame({
        "company_name": c.company_name.values, "company_domain": c.domain.values,
        "industry": c.industry.values, "employee_count": c.employee_count.values,
        "country": c.country.values, "region": c.region.values, "segment": c.segment.values,
        "lead_source": nb.lead_source.values, "created_ord": lead_ord, "created_sec": lead_sec,
        "status": "Converted", "converted_customer_id": nb.customer_id.values,
        "converted_opportunity_id": nb.opportunity_id.values,
        "converted_ord": opp_ord, "converted_sec": opp_sec,
        "lead_score": np.clip(rng.normal(74, 11, len(nb)), 5, 99).round().astype(int),
    })

    # ---------------- unconverted leads
    n_fill = max(0, target - len(conv))
    from_cust = rng.random(n_fill) < 0.35
    k = int(from_cust.sum())
    pick = cust.iloc[rng.integers(0, len(cust), k)]
    n_new = n_fill - k
    region, country, _ = sample_geo(rng, n_new)
    inds = list(INDUSTRIES)
    emp_new = np.clip(np.round(rng.lognormal(np.log(90), 1.3, n_new)), 1, 200_000).astype(np.int64)
    names_new = [fake.company() for _ in range(n_new)]
    dom_new = [slugify_company(nm) + rng.choice([".com", ".com", ".io", ".co", ".net"]) for nm in names_new]
    fill = pd.DataFrame({
        "company_name": np.concatenate([pick.company_name.values, names_new]),
        "company_domain": np.concatenate([pick.domain.values, dom_new]),
        "industry": np.concatenate([pick.industry.values,
                                    rng.choice(inds, n_new, p=[INDUSTRIES[i][0] for i in inds])]),
        "employee_count": np.concatenate([pick.employee_count.values, emp_new]),
        "country": np.concatenate([pick.country.values, country]),
        "region": np.concatenate([pick.region.values, region]),
    })
    fill["segment"] = segment_from_employees(fill.employee_count.values)
    fill["lead_source"] = sample_sources(rng, fill.segment.values)
    fill["created_ord"] = growth_day_ordinals(rng, n_fill, growth=0.9, weekend_factor=0.35)
    fill["created_sec"] = business_seconds(rng, n_fill)
    age = END_ORD - fill.created_ord.values
    old_status = rng.choice(["Disqualified", "Nurturing", "Unresponsive", "Recycled"], n_fill,
                            p=[0.4, 0.3, 0.2, 0.1])
    fill["status"] = np.where(age < 21, np.where(rng.random(n_fill) < 0.5, "New", "Working"), old_status)
    fill["lead_score"] = np.clip(rng.normal(42, 18, n_fill), 1, 99).round().astype(int)
    for col in ("converted_customer_id", "converted_opportunity_id"):
        fill[col] = None
    fill["converted_ord"] = -1
    fill["converted_sec"] = 0

    leads = pd.concat([conv, fill], ignore_index=True)
    leads = leads.sort_values(["created_ord", "created_sec"], kind="stable").reset_index(drop=True)
    n = len(leads)
    leads.insert(0, "lead_id", make_ids("LEAD", n))

    first, last, emails = _people(fake, rng, n, leads.company_domain.values)
    leads["first_name"], leads["last_name"], leads["email"] = first, last, emails
    leads["phone"] = [fake.phone_number() for _ in range(n)]
    leads["title"] = rng.choice(BUYER_TITLES, n)
    leads["company_size"] = company_size_bucket(leads.employee_count.values)

    ch = np.array([LEAD_SOURCES[s][1] for s in leads.lead_source], dtype=object)
    leads["campaign_id"] = assign_campaigns(rng, leads.created_ord.values, ch, leads.region.values,
                                            leads.segment.values, campaigns)
    leads["owner_rep_id"] = [picker.pick("SDR", r, None, int(d)) for r, d in zip(leads.region, leads.created_ord)]

    # MQL: every converted lead, plus high-scoring unconverted ones
    is_mql = (leads.status == "Converted") | ((leads.lead_score >= 60) & ~leads.status.isin(["New"]))
    span = np.where(leads.converted_ord > 0, leads.converted_ord - leads.created_ord, 10)
    leads["mql_ord"] = np.where(is_mql, leads.created_ord + np.floor(rng.random(n) * (span + 1)), -1).astype(np.int64)
    leads["mql_sec"] = business_seconds(rng, n)
    same_day = (leads.mql_ord == leads.converted_ord) & (leads.mql_sec > leads.converted_sec)
    leads.loc[same_day, "mql_sec"] = leads.loc[same_day, "converted_sec"] - 60
    same_day = (leads.mql_ord == leads.created_ord) & (leads.mql_sec < leads.created_sec)
    leads.loc[same_day, "mql_sec"] = np.minimum(leads.loc[same_day, "created_sec"] + 600, DAY_SECONDS - 1)
    triple = (leads.mql_ord == leads.created_ord) & (leads.mql_ord == leads.converted_ord)
    leads.loc[triple, "mql_sec"] = (leads.loc[triple, "created_sec"] + leads.loc[triple, "converted_sec"]) // 2
    leads["disqualification_reason"] = np.where(
        leads.status == "Disqualified",
        rng.choice(list(DISQUALIFY_REASONS), n, p=list(DISQUALIFY_REASONS.values())), None)
    return leads
