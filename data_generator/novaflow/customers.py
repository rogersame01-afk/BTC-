"""Customers: the company master (every company NovaFlow's CRM knows about).

A customer starts as a prospect; the lifecycle simulation later marks it as
a paying customer or churned.
"""
import re

import numpy as np
import pandas as pd

from .config import CITIES, INDUSTRIES, LEAD_SOURCES, REGIONS, SEGMENTS
from .utils import growth_day_ordinals, make_ids

TLDS = {"United States": ".com", "Canada": ".ca", "United Kingdom": ".co.uk", "Germany": ".de", "France": ".fr",
        "Netherlands": ".nl", "Spain": ".es", "Ireland": ".ie", "Sweden": ".se", "Australia": ".com.au",
        "Singapore": ".sg", "Japan": ".jp", "India": ".in", "New Zealand": ".co.nz", "Brazil": ".com.br",
        "Mexico": ".mx", "Colombia": ".co", "Chile": ".cl"}


def slugify_company(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().split(",")[0].replace(" and ", ""))[:24] or "company"


def unique_domains(names, countries, rng):
    seen = set()
    out = []
    for name, country in zip(names, countries):
        base = slugify_company(name)
        tld = TLDS.get(country, ".com") if rng.random() < 0.55 else rng.choice([".com", ".com", ".io", ".ai", ".co"])
        dom = base + tld
        k = 2
        while dom in seen:
            dom = f"{base}{k}{tld}"
            k += 1
        seen.add(dom)
        out.append(dom)
    return out


def sample_geo(rng, n):
    regions = list(REGIONS)
    region = rng.choice(regions, size=n, p=[REGIONS[r]["weight"] for r in regions])
    country = np.empty(n, dtype=object)
    city = np.empty(n, dtype=object)
    for r in regions:
        m = region == r
        cs = list(REGIONS[r]["countries"])
        country[m] = rng.choice(cs, size=m.sum(), p=[REGIONS[r]["countries"][c] for c in cs])
    for c, cities in CITIES.items():
        m = country == c
        city[m] = rng.choice(cities, size=m.sum())
    return region.astype(object), country, city


def build_customers(rng, fake, n: int) -> tuple[pd.DataFrame, dict]:
    segs = list(SEGMENTS)
    segment = rng.choice(segs, size=n, p=[SEGMENTS[s]["share"] for s in segs]).astype(object)

    employees = np.zeros(n, dtype=np.int64)
    for s in segs:
        m = segment == s
        lo, hi, med = SEGMENTS[s]["employees"]
        employees[m] = np.clip(np.round(rng.lognormal(np.log(med), 0.7, m.sum())), lo, hi).astype(np.int64)

    inds = list(INDUSTRIES)
    industry = rng.choice(inds, size=n, p=[INDUSTRIES[i][0] for i in inds]).astype(object)
    # revenue per employee varies by industry-ish noise
    revenue = np.round(employees * rng.lognormal(np.log(210_000), 0.45, n), -3)

    region, country, city = sample_geo(rng, n)

    sources = list(LEAD_SOURCES)
    source = np.empty(n, dtype=object)
    for i, s in enumerate(segs):
        m = segment == s
        p = np.array([LEAD_SOURCES[k][0][i] for k in sources])
        source[m] = rng.choice(sources, size=m.sum(), p=p / p.sum())

    created = growth_day_ordinals(rng, n, growth=0.9, weekend_factor=0.35)

    names = [fake.company() for _ in range(n)]
    domains = unique_domains(names, country, rng)

    df = pd.DataFrame({
        "customer_id": make_ids("CUS", n, width=6),
        "company_name": names,
        "domain": domains,
        "industry": industry,
        "segment": segment,
        "employee_count": employees,
        "annual_revenue_usd": revenue.astype(np.int64),
        "region": region,
        "country": country,
        "city": city,
        "phone": [fake.phone_number() for _ in range(n)],
        "acquisition_source": source,
        "created_ord": created,
    })
    df["website"] = "https://www." + df["domain"]
    # hidden simulation traits (not exported)
    hidden = {
        "health": rng.beta(5, 2, n),       # product fit / satisfaction once a customer
        "fit": np.clip(rng.lognormal(0, 0.3, n), 0.4, 2.2),  # propensity to buy
    }
    return df, hidden
