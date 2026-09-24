"""Sales activities: calls, emails, meetings and demos logged against
opportunities (by the owning rep) and against leads (by SDRs)."""
import numpy as np
import pandas as pd

from .config import SEGMENTS
from .utils import END_ORD, business_seconds, make_ids, weekday_shift

OPP_TYPES = {"Email": 0.34, "Call": 0.25, "Meeting": 0.18, "Demo": 0.09, "LinkedIn Message": 0.06,
             "Proposal Sent": 0.04, "Follow-up Task": 0.04}
LEAD_TYPES = {"Email": 0.5, "Call": 0.33, "LinkedIn Message": 0.14, "Meeting": 0.03}
OUTCOMES = {
    "Call": (["Connected", "Left Voicemail", "No Answer", "Wrong Number"], [0.38, 0.32, 0.27, 0.03]),
    "Email": (["Sent", "Replied", "Bounced"], [0.72, 0.25, 0.03]),
    "LinkedIn Message": (["Sent", "Replied"], [0.8, 0.2]),
    "Meeting": (["Completed", "No Show", "Rescheduled"], [0.82, 0.08, 0.1]),
    "Demo": (["Completed", "No Show", "Rescheduled"], [0.85, 0.06, 0.09]),
    "Proposal Sent": (["Sent"], [1.0]),
    "Follow-up Task": (["Completed", "Open"], [0.9, 0.1]),
}
SUBJECTS = {
    "Email": ["Intro: NovaFlow for {c}", "Following up", "Recap + next steps", "Pricing overview", "Case study you may like",
              "Security questionnaire", "Checking in"],
    "Call": ["Discovery call", "Follow-up call", "Pricing discussion", "Cold call", "Check-in call"],
    "LinkedIn Message": ["Connection request", "InMail: analytics at {c}"],
    "Meeting": ["Discovery meeting", "Technical deep dive", "Executive alignment", "QBR", "Procurement sync"],
    "Demo": ["Product demo", "AI Insights demo", "Tailored demo for {c}"],
    "Proposal Sent": ["Proposal: {c}", "Order form sent"],
    "Follow-up Task": ["Send follow-up materials", "Update mutual action plan"],
}


def _subjects(rng, types, companies):
    out = np.empty(len(types), dtype=object)
    for t, opts in SUBJECTS.items():
        m = np.flatnonzero(types == t)
        pick = rng.integers(0, len(opts), len(m))
        out[m] = [opts[k].format(c=companies[j]) for k, j in zip(pick, m)]
    return out


def build_activities(rng, opps, leads, customers, reps, target):
    seg = customers.set_index("customer_id").segment
    o = opps.copy()
    o["segment"] = o.customer_id.map(seg)
    o_end = np.where(o.is_closed, o.close_ord, END_ORD).astype(np.int64)
    o_start = o.created_ord.values.astype(np.int64)
    span = np.maximum(o_end - o_start, 1)
    type_mult = o.opportunity_type.map({"New Business": 1.0, "Expansion": 0.6, "Renewal": 0.45}).values
    o_lam = span * o.segment.map({k: v["activity_rate"] for k, v in SEGMENTS.items()}).values * type_mult
    o_lam = np.minimum(o_lam, 80)

    worked = leads.status.isin(["Working", "Converted", "Disqualified", "Unresponsive", "Recycled", "Nurturing"]).values
    l_lam = np.where(worked, np.where(leads.status.values == "Converted", 5.0, 2.5), 0.4)
    l_end = np.where(leads.converted_ord.values > 0, leads.converted_ord.values,
                     np.minimum(leads.created_ord.values + 45, END_ORD)).astype(np.int64)
    l_start = leads.created_ord.values.astype(np.int64)

    scale = target / (o_lam.sum() + l_lam.sum())
    o_n = rng.poisson(o_lam * scale)
    l_n = rng.poisson(l_lam * scale)

    company = customers.set_index("customer_id").company_name
    # --- opportunity activities
    oi = np.repeat(np.arange(len(o)), o_n)
    o_day = o_start[oi] + np.floor(rng.random(len(oi)) * (span[oi] + 1)).astype(np.int64)
    o_type = rng.choice(list(OPP_TYPES), len(oi), p=list(OPP_TYPES.values()))
    a1 = pd.DataFrame({
        "activity_type": o_type,
        "day": o_day,
        "min_day": o_start[oi],
        "rep_id": o.owner_rep_id.values[oi],
        "customer_id": o.customer_id.values[oi],
        "lead_id": o.lead_id.values[oi] if "lead_id" in o else None,
        "opportunity_id": o.opportunity_id.values[oi],
        "company": o.customer_id.map(company).values[oi],
    })
    # --- lead (prospecting) activities
    li = np.repeat(np.arange(len(leads)), l_n)
    l_span = np.maximum(l_end - l_start, 0)
    l_day = l_start[li] + np.floor(rng.random(len(li)) * (l_span[li] + 1)).astype(np.int64)
    a2 = pd.DataFrame({
        "activity_type": rng.choice(list(LEAD_TYPES), len(li), p=list(LEAD_TYPES.values())),
        "day": l_day,
        "min_day": l_start[li],
        "rep_id": leads.owner_rep_id.values[li],
        "customer_id": leads.converted_customer_id.values[li],
        "lead_id": leads.lead_id.values[li],
        "opportunity_id": None,
        "company": leads.company_name.values[li],
    })
    a = pd.concat([a1, a2], ignore_index=True)
    n = len(a)
    shifted = weekday_shift(a.day.values, rng)
    a["day"] = np.minimum(np.where(shifted < a.min_day.values, a.day.values, shifted), END_ORD)
    t = a.activity_type.values
    a["sec"] = business_seconds(rng, n)
    a["direction"] = np.where(np.isin(t, ["Email", "Call"]) & (rng.random(n) < 0.18), "Inbound", "Outbound")
    outcome = np.empty(n, dtype=object)
    for typ, (opts, p) in OUTCOMES.items():
        m = t == typ
        outcome[m] = rng.choice(opts, m.sum(), p=p)
    a["outcome"] = outcome
    dur = np.full(n, np.nan)
    m = (t == "Call") & (outcome == "Connected")
    dur[m] = np.clip(np.round(rng.lognormal(np.log(9), 0.6, m.sum())), 1, 90)
    m = (t == "Call") & (outcome != "Connected")
    dur[m] = np.round(rng.uniform(0, 2, m.sum()))
    m = np.isin(t, ["Meeting", "Demo"]) & (outcome == "Completed")
    dur[m] = rng.choice([30, 45, 60, 90], m.sum(), p=[0.45, 0.2, 0.3, 0.05])
    a["duration_minutes"] = pd.array(dur, dtype="Int64")
    a["subject"] = _subjects(rng, t, a.company.values)
    a = a.sort_values(["day", "sec"], kind="stable").reset_index(drop=True)
    a.insert(0, "activity_id", make_ids("ACT", n))
    return a.drop(columns=["company", "min_day"])
