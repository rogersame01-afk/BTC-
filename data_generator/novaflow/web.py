"""Website sessions and clickstream events.

Three kinds of traffic:
  * prospects who become leads (pre-conversion anonymous visits, the
    converting session with a form submit, and identified follow-up visits)
  * logged-in customers (app login, docs)
  * anonymous visitors who never convert
"""
import numpy as np
import pandas as pd

from .config import LEAD_SOURCES, WEB_TRACKING_COVERAGE
from .customers import sample_geo
from .leads import assign_campaigns
from .utils import DAY_SECONDS, END_ORD, EPOCH_ORD, START_ORD, business_seconds, growth_day_ordinals, make_ids

# traffic source: utm_source, utm_medium, referrer, channel grouping, landing pages, bounce rate
TRAFFIC = {
    "Organic Search": (None, None, "google.com", "Organic Search",
                       ["/", "/blog/what-is-a-semantic-layer", "/blog/self-serve-bi-guide", "/blog/data-governance-101",
                        "/product", "/integrations", "/blog/ai-dashboards"], 0.48),
    "Paid Search": ("google", "cpc", "google.com", "Paid Search",
                    ["/lp/analytics-platform", "/lp/bi-tool-comparison", "/pricing"], 0.52),
    "Paid Social": ("linkedin", "paid_social", "linkedin.com", "Paid Social",
                    ["/lp/ai-insights", "/lp/analytics-platform"], 0.58),
    "Content Syndication": ("techtarget", "content", "techtarget.com", "Referral",
                            ["/resources/ebook-modern-data-stack", "/resources/state-of-analytics-report"], 0.40),
    "Webinar": ("hubspot", "email", None, "Email", ["/webinars/register"], 0.30),
    "Email Nurture": ("hubspot", "email", None, "Email",
                      ["/resources/ebook-modern-data-stack", "/blog/ai-dashboards", "/customers"], 0.45),
    "Free Trial": (None, None, "google.com", "Organic Search", ["/free-trial", "/pricing"], 0.30),
    "Direct": (None, None, None, "Direct", ["/", "/pricing", "/product"], 0.38),
    "Referral": (None, None, "g2.com", "Referral", ["/", "/customers", "/compare/novaflow-vs-tableau"], 0.40),
}
ANON_MIX = {"Organic Search": 0.42, "Direct": 0.2, "Paid Search": 0.12, "Paid Social": 0.08, "Referral": 0.08,
            "Email Nurture": 0.05, "Content Syndication": 0.05}
SITE_PAGES = {"/": 10, "/pricing": 9, "/product": 8, "/product/ai-insights": 5, "/product/connectors": 4,
              "/product/embedded-analytics": 3, "/solutions/finance": 3, "/solutions/retail": 3,
              "/solutions/saas": 3, "/customers": 5, "/integrations": 4, "/security": 2, "/about": 2,
              "/careers": 2, "/blog": 4, "/blog/what-is-a-semantic-layer": 2, "/blog/ai-dashboards": 2,
              "/demo": 3, "/free-trial": 3, "/compare/novaflow-vs-tableau": 2, "/compare/novaflow-vs-looker": 2,
              "/docs": 3}
DOC_PAGES = {"/app/home": 10, "/app/dashboards": 9, "/app/explore": 7, "/app/admin/users": 2,
             "/docs/getting-started": 5, "/docs/connectors/snowflake": 4, "/docs/connectors/bigquery": 3,
             "/docs/semantic-layer": 4, "/docs/ai-insights": 3, "/docs/api-reference": 3, "/docs/sso-setup": 1,
             "/docs/embedding": 2, "/status": 1}
PROSPECT_EVENTS = {"page_view": 0.55, "click": 0.17, "scroll": 0.12, "cta_click": 0.06, "video_play": 0.04,
                   "form_start": 0.03, "site_search": 0.03}
CUSTOMER_EVENTS = {"page_view": 0.45, "click": 0.2, "scroll": 0.1, "docs_search": 0.12, "dashboard_view": 0.1,
                   "export": 0.03}
DETAILS = {
    "click": ["nav:product", "nav:pricing", "nav:customers", "footer:security", "logo_carousel", "case_study_card"],
    "cta_click": ["Book a demo", "Start free trial", "Talk to sales", "See pricing"],
    "video_play": ["Product tour (3 min)", "AI Insights demo", "Customer story: logistics"],
    "form_start": ["demo_request", "contact_sales", "content_download"],
    "site_search": ["pricing", "snowflake", "sso", "embedding", "api"],
    "docs_search": ["snowflake connector", "row level security", "scheduled reports", "api token", "sso okta"],
    "dashboard_view": ["Revenue Overview", "Pipeline Health", "Marketing Funnel", "Churn Monitor"],
    "export": ["csv", "pdf", "xlsx"],
}


def conversion_type(source, rng):
    if source == "Free Trial":
        return "trial_signup"
    if source == "Webinar":
        return "webinar_registration"
    if source in ("Content Syndication", "Email Nurture"):
        return "content_download"
    return "demo_request" if rng.random() < 0.7 else "contact_sales"


def _anon_ids(rng, n):
    return np.array([f"anon_{x:016x}" for x in rng.integers(0, 2**63, n, dtype=np.int64)], dtype=object)


def _ts(ords, secs):
    return (np.asarray(ords, dtype=np.int64) - EPOCH_ORD) * DAY_SECONDS + np.asarray(secs, dtype=np.int64)


def build_web(rng, leads, customers, subs, campaigns, target_sessions, target_events):
    parts = []

    # ---------------- prospect / lead sessions
    is_web = np.array([LEAD_SOURCES[s][3] for s in leads.lead_source])
    web_leads = leads[is_web & (rng.random(len(leads)) < WEB_TRACKING_COVERAGE)].copy()
    wl_anon = _anon_ids(rng, len(web_leads))
    created_ts = _ts(web_leads.created_ord, web_leads.created_sec)
    base = dict(country=web_leads.country.values, campaign_id=web_leads.campaign_id.values)
    # converting session: ends exactly at the lead's creation timestamp
    parts.append(pd.DataFrame(dict(anonymous_id=wl_anon, lead_id=web_leads.lead_id.values, customer_id=None,
                                   source=web_leads.lead_source.values, anchor_end_ts=created_ts,
                                   start_ts=-1, converted=True,
                                   conversion_type=[conversion_type(s, rng) for s in web_leads.lead_source],
                                   **base)))
    # earlier anonymous research visits
    n_pre = rng.poisson(0.35, len(web_leads))
    rep = np.repeat(np.arange(len(web_leads)), n_pre)
    pre_src = np.where(rng.random(len(rep)) < 0.5, web_leads.lead_source.values[rep],
                       rng.choice(["Organic Search", "Direct"], len(rep)))
    pre_start = created_ts[rep] - rng.integers(1, 45, len(rep)) * DAY_SECONDS + \
        rng.integers(-4 * 3600, 4 * 3600, len(rep))
    parts.append(pd.DataFrame(dict(anonymous_id=wl_anon[rep], lead_id=None, customer_id=None, source=pre_src,
                                   anchor_end_ts=-1, start_ts=pre_start, converted=False, conversion_type=None,
                                   country=web_leads.country.values[rep],
                                   campaign_id=np.where(pre_src == web_leads.lead_source.values[rep],
                                                        web_leads.campaign_id.values[rep], None))))
    # identified follow-up visits while the deal is worked
    n_post = rng.poisson(np.where(web_leads.status.values == "Converted", 0.8, 0.15))
    rep = np.repeat(np.arange(len(web_leads)), n_post)
    horizon = np.minimum(created_ts[rep] + 60 * DAY_SECONDS, _ts(END_ORD, DAY_SECONDS - 1))
    post_start = created_ts[rep] + (rng.random(len(rep)) * (horizon - created_ts[rep])).astype(np.int64) + 3600
    parts.append(pd.DataFrame(dict(anonymous_id=wl_anon[rep], lead_id=web_leads.lead_id.values[rep],
                                   customer_id=None, source=rng.choice(["Direct", "Email Nurture"], len(rep)),
                                   anchor_end_ts=-1, start_ts=post_start, converted=False, conversion_type=None,
                                   country=web_leads.country.values[rep], campaign_id=None)))

    # ---------------- logged-in customers
    live = subs.groupby("customer_id").agg(start=("start_ord", "min"), end=("end_ord", "max"),
                                           seats=("quantity", "max"))
    live["end"] = np.where(live.end < 0, END_ORD, live.end)
    w = (live.end - live.start + 1).clip(lower=1) * live.seats.clip(lower=1) ** 0.3
    n_cust = int(target_sessions * 0.16)
    cidx = rng.choice(len(live), size=n_cust, p=(w / w.sum()).values)
    lv = live.iloc[cidx]
    day = lv.start.values + (rng.random(n_cust) * (lv.end.values - lv.start.values + 1)).astype(np.int64)
    day = np.minimum(day, END_ORD)
    ccountry = customers.set_index("customer_id").country
    # each customer has a handful of recurring users (stable anonymous ids)
    user_slot = rng.integers(0, 6, n_cust)
    user_base = dict(zip(live.index, rng.integers(0, 2**62, len(live), dtype=np.int64)))
    cust_anon = np.array([f"anon_{user_base[c] + u:016x}" for c, u in zip(lv.index.values, user_slot)],
                         dtype=object)
    parts.append(pd.DataFrame(dict(anonymous_id=cust_anon, lead_id=None, customer_id=lv.index.values,
                                   source="Customer", anchor_end_ts=-1,
                                   start_ts=_ts(day, business_seconds(rng, n_cust)), converted=False,
                                   conversion_type=None, country=ccountry.loc[lv.index].values, campaign_id=None)))

    # ---------------- anonymous traffic that never converts
    n_so_far = sum(len(p) for p in parts)
    n_anon = max(0, target_sessions - n_so_far)
    visitors = _anon_ids(rng, max(1, int(n_anon * 0.72)))
    src = rng.choice(list(ANON_MIX), n_anon, p=list(ANON_MIX.values()))
    a_days = growth_day_ordinals(rng, n_anon, growth=0.9, weekend_factor=0.55)
    region, country, _ = sample_geo(rng, n_anon)
    ch = np.array([LEAD_SOURCES.get(s, (None, None))[1] for s in src], dtype=object)
    camp = assign_campaigns(rng, a_days, ch, region, np.full(n_anon, "All", dtype=object), campaigns)
    parts.append(pd.DataFrame(dict(anonymous_id=visitors[rng.integers(0, len(visitors), n_anon)], lead_id=None,
                                   customer_id=None, source=src, anchor_end_ts=-1,
                                   start_ts=_ts(a_days, rng.integers(0, DAY_SECONDS, n_anon)), converted=False,
                                   conversion_type=None, country=country, campaign_id=camp)))

    s = pd.concat(parts, ignore_index=True)
    s = s[(s.start_ts < 0) | (s.start_ts >= _ts(START_ORD, 0))].reset_index(drop=True)  # keep data window
    n = len(s)
    is_cust = (s.source == "Customer").values

    # ---------------- per-session attributes
    src_key = np.where(is_cust, "Direct", s.source.values)
    src_key = np.where(np.isin(src_key, list(TRAFFIC)), src_key, "Referral")
    info = {k: TRAFFIC[k] for k in TRAFFIC}
    s["utm_source"] = [info[k][0] for k in src_key]
    s["utm_medium"] = [info[k][1] for k in src_key]
    s["referrer_domain"] = [info[k][2] for k in src_key]
    s["channel_grouping"] = np.where(is_cust, "Direct", [info[k][3] for k in src_key])
    camp_utm = campaigns.set_index("campaign_id").utm_campaign
    s["utm_campaign"] = s.campaign_id.map(camp_utm)
    landing = np.array([info[k][4][rng.integers(len(info[k][4]))] for k in src_key], dtype=object)
    landing[is_cust] = rng.choice(["/login", "/login", "/docs/getting-started", "/docs/semantic-layer"],
                                  is_cust.sum())
    s["landing_page"] = landing

    device = rng.choice(["desktop", "mobile", "tablet"], n, p=[0.66, 0.29, 0.05])
    device[is_cust] = rng.choice(["desktop", "mobile"], is_cust.sum(), p=[0.93, 0.07])
    s["device_type"] = device
    s["browser"] = rng.choice(["Chrome", "Safari", "Edge", "Firefox"], n, p=[0.63, 0.2, 0.1, 0.07])
    s.loc[(device != "desktop") & (rng.random(n) < 0.6), "browser"] = "Safari"
    s["os"] = np.where(device == "desktop", rng.choice(["Windows", "macOS", "Linux"], n, p=[0.55, 0.4, 0.05]),
                       np.where(s.browser.values == "Safari", "iOS", "Android"))

    # ---------------- events
    bounce_p = np.array([TRAFFIC[k][5] for k in src_key])
    bounce_p[is_cust] = 0.12
    bounce = (rng.random(n) < bounce_p) & ~s.converted.values
    non_b = ~bounce
    lam = max(0.1, (target_events - n - non_b.sum()) / max(non_b.sum(), 1))
    n_ev = np.where(bounce, 1, 2 + rng.poisson(lam, n))
    n_ev = np.where(s.converted.values, np.maximum(n_ev, 3), n_ev)

    sess_idx = np.repeat(np.arange(n), n_ev)
    offsets = np.concatenate([[0], np.cumsum(n_ev)[:-1]])
    pos = np.arange(len(sess_idx)) - offsets[sess_idx]
    is_last = pos == (n_ev[sess_idx] - 1)
    ev_cust = is_cust[sess_idx]

    etype = np.where(ev_cust, rng.choice(list(CUSTOMER_EVENTS), len(sess_idx), p=list(CUSTOMER_EVENTS.values())),
                     rng.choice(list(PROSPECT_EVENTS), len(sess_idx), p=list(PROSPECT_EVENTS.values()))).astype(object)
    etype[pos == 0] = "page_view"
    conv_last = is_last & s.converted.values[sess_idx]
    etype[conv_last] = "form_submit"
    cust_login = ev_cust & (pos == 1) & (landing[sess_idx] == "/login")
    etype[cust_login] = "login"

    pages = np.where(ev_cust, rng.choice(list(DOC_PAGES), len(sess_idx), p=np.array(list(DOC_PAGES.values())) /
                                         sum(DOC_PAGES.values())),
                     rng.choice(list(SITE_PAGES), len(sess_idx), p=np.array(list(SITE_PAGES.values())) /
                                sum(SITE_PAGES.values()))).astype(object)
    pages[pos == 0] = landing[sess_idx[pos == 0]]
    conv_page = {"trial_signup": "/free-trial", "webinar_registration": "/webinars/register",
                 "content_download": "/resources/download", "demo_request": "/demo", "contact_sales": "/contact"}
    pages[conv_last] = [conv_page[t] for t in s.conversion_type.values[sess_idx[conv_last]]]
    keep_page = (etype == "page_view") | conv_last
    page_series = pd.Series(np.where(keep_page, pages, None)).ffill()

    detail = np.full(len(sess_idx), None, dtype=object)
    for et, opts in DETAILS.items():
        m = etype == et
        detail[m] = rng.choice(opts, m.sum())
    detail[conv_last] = s.conversion_type.values[sess_idx[conv_last]]
    detail[cust_login] = rng.choice(["password", "sso_okta", "sso_google"], cust_login.sum(), p=[0.4, 0.35, 0.25])

    gaps = np.where(pos == 0, 0, np.round(rng.exponential(42, len(sess_idx))).astype(np.int64) + 2)
    cum = np.cumsum(gaps)
    rel = cum - cum[offsets][sess_idx]
    dur = rel[np.cumsum(n_ev) - 1]
    start = s.start_ts.values.astype(np.int64)
    anchored = s.anchor_end_ts.values.astype(np.int64) > 0
    start = np.where(anchored, s.anchor_end_ts.values.astype(np.int64) - dur, start)
    ev_ts = start[sess_idx] + rel

    events = pd.DataFrame({
        "event_id": make_ids("EVT", len(sess_idx)),
        "session_id": None,
        "anonymous_id": s.anonymous_id.values[sess_idx],
        "event_timestamp": ev_ts.astype("datetime64[s]"),
        "event_type": etype,
        "page_path": page_series.values,
        "event_detail": detail,
    })

    s["session_start"] = start.astype("datetime64[s]")
    s["session_end"] = (start + dur).astype("datetime64[s]")
    s["duration_seconds"] = dur
    s["pageviews"] = np.bincount(sess_idx, weights=(etype == "page_view"), minlength=n).astype(int)
    s["event_count"] = n_ev
    s["is_bounce"] = bounce

    # order sessions chronologically and assign ids
    order = np.argsort(start, kind="stable")
    new_pos = np.empty(n, dtype=np.int64)
    new_pos[order] = np.arange(n)
    sid = make_ids("SES", n)
    s = s.iloc[order].reset_index(drop=True)
    s.insert(0, "session_id", sid)
    events["session_id"] = sid[new_pos[sess_idx]]
    events = events.sort_values(["event_timestamp", "event_id"], kind="stable").reset_index(drop=True)
    events["event_id"] = make_ids("EVT", len(events))

    s = s[["session_id", "anonymous_id", "lead_id", "customer_id", "session_start", "session_end",
           "duration_seconds", "landing_page", "referrer_domain", "channel_grouping", "utm_source", "utm_medium",
           "utm_campaign", "campaign_id", "device_type", "browser", "os", "country", "pageviews", "event_count",
           "is_bounce", "converted", "conversion_type"]]
    return s, events
