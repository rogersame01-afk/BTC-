from pathlib import Path
from datetime import datetime, timedelta
import random

import numpy as np
import pandas as pd
from faker import Faker


# ============================================================
# CONFIGURATION
# ============================================================

SEED = 42

random.seed(SEED)
np.random.seed(SEED)
Faker.seed(SEED)

fake = Faker()

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Change these values if you want a smaller/larger dataset.
N_SALES_REPS = 120
N_ACCOUNTS = 25_000
N_CONTACTS = 75_000
N_LEADS = 120_000
N_OPPORTUNITIES = 70_000
N_CAMPAIGNS = 400
N_MARKETING_TOUCHES = 300_000
N_SUBSCRIPTIONS = 22_000
N_INVOICES = 120_000
N_SUPPORT_TICKETS = 80_000
N_WEBSITE_EVENTS = 500_000

START_DATE = pd.Timestamp("2024-01-01")
END_DATE = pd.Timestamp("2026-09-01")


# ============================================================
# HELPERS
# ============================================================

def random_date(start=START_DATE, end=END_DATE):
    """Return a random timestamp between start and end."""
    seconds = int((end - start).total_seconds())
    return start + pd.to_timedelta(random.randint(0, seconds), unit="s")


def random_dates(n, start=START_DATE, end=END_DATE):
    """Vectorized random timestamps."""
    start_ns = start.value
    end_ns = end.value

    values = np.random.randint(start_ns, end_ns, size=n, dtype=np.int64)
    return pd.to_datetime(values)


def random_id(prefix, number, width=7):
    return f"{prefix}{number:0{width}d}"


def weighted_choice(values, probabilities, size):
    return np.random.choice(values, size=size, p=probabilities)


def save_csv(df, filename):
    path = OUTPUT_DIR / filename
    df.to_csv(path, index=False)
    print(f"Created {filename:<30} {len(df):>10,} rows")


# ============================================================
# 1. SALES REPS
# ============================================================

def generate_sales_reps():

    roles = weighted_choice(
        [
            "Account Executive",
            "Senior Account Executive",
            "Business Development Representative",
            "Sales Development Representative",
            "Enterprise Account Executive"
        ],
        [0.30, 0.20, 0.18, 0.18, 0.14],
        N_SALES_REPS
    )

    regions = weighted_choice(
        ["North America", "EMEA", "APAC", "LATAM"],
        [0.60, 0.18, 0.15, 0.07],
        N_SALES_REPS
    )

    hire_dates = random_dates(
        N_SALES_REPS,
        pd.Timestamp("2018-01-01"),
        pd.Timestamp("2026-01-01")
    )

    quotas = []

    for role in roles:

        if "Enterprise" in role:
            quota = np.random.normal(1_800_000, 300_000)

        elif "Senior" in role:
            quota = np.random.normal(1_400_000, 250_000)

        elif "Account Executive" in role:
            quota = np.random.normal(1_000_000, 200_000)

        else:
            quota = np.random.normal(500_000, 100_000)

        quotas.append(max(250_000, round(quota, 2)))

    df = pd.DataFrame({
        "sales_rep_id": [
            random_id("REP", i + 1, 5)
            for i in range(N_SALES_REPS)
        ],
        "sales_rep_name": [
            fake.name()
            for _ in range(N_SALES_REPS)
        ],
        "role": roles,
        "region": regions,
        "hire_date": hire_dates,
        "annual_quota": quotas,
        "manager_name": [
            fake.name()
            for _ in range(N_SALES_REPS)
        ],
        "active_flag": weighted_choice(
            [1, 0],
            [0.94, 0.06],
            N_SALES_REPS
        )
    })

    save_csv(df, "sales_reps.csv")

    return df


# ============================================================
# 2. ACCOUNTS
# ============================================================

def generate_accounts(sales_reps):

    industries = [
        "Technology",
        "Financial Services",
        "Retail",
        "Healthcare",
        "Education",
        "Manufacturing",
        "Professional Services",
        "Media",
        "Telecommunications",
        "Transportation"
    ]

    account_segments = weighted_choice(
        ["SMB", "Mid-Market", "Enterprise"],
        [0.52, 0.32, 0.16],
        N_ACCOUNTS
    )

    employees = []

    for segment in account_segments:

        if segment == "SMB":
            count = random.randint(10, 199)

        elif segment == "Mid-Market":
            count = random.randint(200, 1999)

        else:
            count = random.randint(2000, 50_000)

        employees.append(count)

    annual_revenue = []

    for employee_count in employees:
        revenue_per_employee = np.random.uniform(80_000, 350_000)

        revenue = employee_count * revenue_per_employee

        annual_revenue.append(round(revenue, 2))

    created_dates = random_dates(N_ACCOUNTS)

    df = pd.DataFrame({
        "account_id": [
            random_id("ACC", i + 1)
            for i in range(N_ACCOUNTS)
        ],
        "account_name": [
            fake.company()
            for _ in range(N_ACCOUNTS)
        ],
        "industry": np.random.choice(
            industries,
            N_ACCOUNTS
        ),
        "segment": account_segments,
        "region": weighted_choice(
            ["North America", "EMEA", "APAC", "LATAM"],
            [0.60, 0.18, 0.15, 0.07],
            N_ACCOUNTS
        ),
        "country": [
            fake.country()
            for _ in range(N_ACCOUNTS)
        ],
        "employee_count": employees,
        "estimated_annual_revenue": annual_revenue,
        "created_at": created_dates,
        "account_owner_id": np.random.choice(
            sales_reps["sales_rep_id"],
            N_ACCOUNTS
        )
    })

    save_csv(df, "accounts.csv")

    return df


# ============================================================
# 3. CONTACTS
# ============================================================

def generate_contacts(accounts):

    account_ids = np.random.choice(
        accounts["account_id"],
        N_CONTACTS
    )

    job_titles = [
        "Chief Executive Officer",
        "Chief Financial Officer",
        "Chief Technology Officer",
        "VP Sales",
        "VP Marketing",
        "VP Operations",
        "Director of Sales",
        "Director of Marketing",
        "Director of Analytics",
        "Revenue Operations Manager",
        "Marketing Operations Manager",
        "Sales Operations Manager",
        "Data Analyst",
        "Business Analyst",
        "Product Manager"
    ]

    first_names = [
        fake.first_name()
        for _ in range(N_CONTACTS)
    ]

    last_names = [
        fake.last_name()
        for _ in range(N_CONTACTS)
    ]

    df = pd.DataFrame({
        "contact_id": [
            random_id("CON", i + 1)
            for i in range(N_CONTACTS)
        ],
        "account_id": account_ids,
        "first_name": first_names,
        "last_name": last_names,
        "job_title": np.random.choice(
            job_titles,
            N_CONTACTS
        ),
        "email": [
            f"{first.lower()}.{last.lower()}@example.com"
            .replace(" ", "")
            .replace("'", "")
            for first, last in zip(first_names, last_names)
        ],
        "phone": [
            fake.phone_number()
            for _ in range(N_CONTACTS)
        ],
        "created_at": random_dates(N_CONTACTS),
        "decision_maker_flag": weighted_choice(
            [1, 0],
            [0.24, 0.76],
            N_CONTACTS
        )
    })

    save_csv(df, "contacts.csv")

    return df


# ============================================================
# 4. CAMPAIGNS
# ============================================================

def generate_campaigns():

    channels = [
        "Google Ads",
        "LinkedIn Ads",
        "Meta Ads",
        "Email",
        "Webinar",
        "Organic Search",
        "Affiliate",
        "Content Marketing"
    ]

    campaign_types = [
        "Brand Awareness",
        "Lead Generation",
        "Product Launch",
        "Retargeting",
        "Customer Expansion",
        "Event Promotion"
    ]

    campaign_rows = []

    for i in range(N_CAMPAIGNS):

        start_date = random_date(
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2026-07-01")
        )

        duration = random.randint(14, 120)

        end_date = min(
            start_date + pd.Timedelta(days=duration),
            END_DATE
        )

        channel = random.choice(channels)

        if channel in ["Google Ads", "LinkedIn Ads", "Meta Ads"]:
            budget = np.random.uniform(10_000, 250_000)

        elif channel == "Webinar":
            budget = np.random.uniform(5_000, 75_000)

        else:
            budget = np.random.uniform(2_000, 80_000)

        campaign_rows.append({
            "campaign_id": random_id("CAM", i + 1, 6),
            "campaign_name": f"{random.choice(campaign_types)} - {i + 1}",
            "channel": channel,
            "campaign_type": random.choice(campaign_types),
            "start_date": start_date,
            "end_date": end_date,
            "budget": round(budget, 2),
            "region": random.choice(
                ["North America", "EMEA", "APAC", "LATAM", "Global"]
            ),
            "status": random.choice(
                ["Completed", "Active", "Paused"]
            )
        })

    df = pd.DataFrame(campaign_rows)

    save_csv(df, "campaigns.csv")

    return df


# ============================================================
# 5. LEADS
# ============================================================

def generate_leads(campaigns, sales_reps):

    lead_sources = [
        "Google Ads",
        "LinkedIn Ads",
        "Meta Ads",
        "Organic Search",
        "Email",
        "Webinar",
        "Referral",
        "Direct",
        "Affiliate"
    ]

    statuses = weighted_choice(
        [
            "New",
            "Working",
            "Qualified",
            "Disqualified",
            "Converted"
        ],
        [0.14, 0.18, 0.22, 0.20, 0.26],
        N_LEADS
    )

    created_dates = random_dates(N_LEADS)

    campaign_ids = np.random.choice(
        campaigns["campaign_id"],
        N_LEADS
    )

    df = pd.DataFrame({
        "lead_id": [
            random_id("LEAD", i + 1)
            for i in range(N_LEADS)
        ],
        "created_at": created_dates,
        "lead_source": np.random.choice(
            lead_sources,
            N_LEADS
        ),
        "campaign_id": campaign_ids,
        "lead_status": statuses,
        "lead_score": np.clip(
            np.random.normal(60, 22, N_LEADS),
            0,
            100
        ).round(0).astype(int),
        "industry": np.random.choice(
            [
                "Technology",
                "Financial Services",
                "Retail",
                "Healthcare",
                "Education",
                "Manufacturing",
                "Professional Services"
            ],
            N_LEADS
        ),
        "company_size": weighted_choice(
            ["SMB", "Mid-Market", "Enterprise"],
            [0.55, 0.30, 0.15],
            N_LEADS
        ),
        "sales_rep_id": np.random.choice(
            sales_reps["sales_rep_id"],
            N_LEADS
        ),
        "converted_flag": [
            1 if status == "Converted" else 0
            for status in statuses
        ]
    })

    save_csv(df, "leads.csv")

    return df


# ============================================================
# 6. OPPORTUNITIES
# ============================================================

def generate_opportunities(accounts, sales_reps, campaigns):

    stages = [
        "Prospecting",
        "Discovery",
        "Demo",
        "Proposal",
        "Negotiation",
        "Closed Won",
        "Closed Lost"
    ]

    stage_probabilities = [
        0.08,
        0.10,
        0.10,
        0.12,
        0.10,
        0.30,
        0.20
    ]

    rows = []

    account_lookup = accounts.set_index("account_id")

    for i in range(N_OPPORTUNITIES):

        account_id = random.choice(
            accounts["account_id"].tolist()
        )

        account = account_lookup.loc[account_id]

        segment = account["segment"]

        created_at = random_date()

        if segment == "Enterprise":
            sales_cycle_days = max(
                30,
                int(np.random.normal(120, 35))
            )
            amount = np.random.lognormal(
                mean=np.log(120_000),
                sigma=0.55
            )

        elif segment == "Mid-Market":
            sales_cycle_days = max(
                15,
                int(np.random.normal(70, 25))
            )
            amount = np.random.lognormal(
                mean=np.log(45_000),
                sigma=0.50
            )

        else:
            sales_cycle_days = max(
                5,
                int(np.random.normal(35, 15))
            )
            amount = np.random.lognormal(
                mean=np.log(12_000),
                sigma=0.45
            )

        stage = np.random.choice(
            stages,
            p=stage_probabilities
        )

        expected_close_date = created_at + pd.Timedelta(
            days=sales_cycle_days
        )

        actual_close_date = pd.NaT

        if stage in ["Closed Won", "Closed Lost"]:

            actual_close_date = min(
                expected_close_date,
                END_DATE
            )

        probability_map = {
            "Prospecting": 0.10,
            "Discovery": 0.20,
            "Demo": 0.35,
            "Proposal": 0.55,
            "Negotiation": 0.75,
            "Closed Won": 1.00,
            "Closed Lost": 0.00
        }

        rows.append({
            "opportunity_id": random_id("OPP", i + 1),
            "account_id": account_id,
            "sales_rep_id": random.choice(
                sales_reps["sales_rep_id"].tolist()
            ),
            "campaign_id": random.choice(
                campaigns["campaign_id"].tolist()
            ),
            "opportunity_name": f"{account['account_name']} Opportunity {i + 1}",
            "segment": segment,
            "stage": stage,
            "amount": round(amount, 2),
            "probability": probability_map[stage],
            "created_at": created_at,
            "expected_close_date": expected_close_date,
            "actual_close_date": actual_close_date,
            "sales_cycle_days": sales_cycle_days,
            "closed_won_flag": 1 if stage == "Closed Won" else 0,
            "closed_lost_flag": 1 if stage == "Closed Lost" else 0
        })

    df = pd.DataFrame(rows)

    save_csv(df, "opportunities.csv")

    return df


# ============================================================
# 7. OPPORTUNITY HISTORY
# ============================================================

def generate_opportunity_history(opportunities):

    stage_sequence = [
        "Prospecting",
        "Discovery",
        "Demo",
        "Proposal",
        "Negotiation"
    ]

    rows = []
    history_id = 1

    for _, opp in opportunities.iterrows():

        created_at = pd.Timestamp(opp["created_at"])

        # Normalise the injected "Closed-Won" typo so history can be built;
        # the dirty value is kept in opportunities.csv for dbt to clean.
        final_stage = (
            "Closed Won"
            if opp["stage"] == "Closed-Won"
            else opp["stage"]
        )

        if final_stage == "Closed Won":
            stages = stage_sequence + ["Closed Won"]

        elif final_stage == "Closed Lost":

            lost_index = random.randint(
                1,
                len(stage_sequence)
            )

            stages = (
                stage_sequence[:lost_index]
                + ["Closed Lost"]
            )

        else:

            current_idx = stage_sequence.index(final_stage)

            stages = stage_sequence[:current_idx + 1]

        current_date = created_at

        for stage_num, stage in enumerate(stages, start=1):

            days_in_stage = random.randint(2, 30)

            entered_stage_at = current_date
            exited_stage_at = (
                current_date + pd.Timedelta(days=days_in_stage)
            )

            if stage == stages[-1] and stage not in [
                "Closed Won",
                "Closed Lost"
            ]:
                exited_stage_at = pd.NaT

            rows.append({
                "opportunity_history_id": random_id(
                    "OPPH",
                    history_id,
                    9
                ),
                "opportunity_id": opp["opportunity_id"],
                "stage": stage,
                "stage_sequence": stage_num,
                "entered_stage_at": entered_stage_at,
                "exited_stage_at": exited_stage_at,
                "days_in_stage": (
                    days_in_stage
                    if pd.notna(exited_stage_at)
                    else None
                )
            })

            current_date = (
                exited_stage_at
                if pd.notna(exited_stage_at)
                else current_date
            )

            history_id += 1

    df = pd.DataFrame(rows)

    save_csv(df, "opportunity_history.csv")

    return df


# ============================================================
# 8. MARKETING TOUCHES
# ============================================================

def generate_marketing_touches(
    leads,
    contacts,
    campaigns
):

    lead_ids = leads["lead_id"].tolist()

    contact_ids = contacts["contact_id"].tolist()

    campaign_ids = campaigns["campaign_id"].tolist()

    channels = [
        "Google Ads",
        "LinkedIn Ads",
        "Meta Ads",
        "Email",
        "Organic Search",
        "Webinar",
        "Affiliate",
        "Direct"
    ]

    touch_types = [
        "Impression",
        "Click",
        "Landing Page",
        "Form Fill",
        "Email Open",
        "Email Click",
        "Webinar Registration",
        "Demo Request"
    ]

    rows = []

    for i in range(N_MARKETING_TOUCHES):

        person_type = random.choice(
            ["lead", "contact"]
        )

        lead_id = None
        contact_id = None

        if person_type == "lead":
            lead_id = random.choice(lead_ids)

        else:
            contact_id = random.choice(contact_ids)

        channel = random.choice(channels)

        rows.append({
            "marketing_touch_id": random_id(
                "MT",
                i + 1,
                9
            ),
            "lead_id": lead_id,
            "contact_id": contact_id,
            "campaign_id": random.choice(campaign_ids),
            "touch_timestamp": random_date(),
            "channel": channel,
            "touch_type": random.choice(touch_types),
            "device_type": random.choice(
                ["Desktop", "Mobile", "Tablet"]
            ),
            "utm_source": channel.lower().replace(" ", "_"),
            "utm_medium": random.choice(
                [
                    "cpc",
                    "organic",
                    "email",
                    "social",
                    "referral"
                ]
            ),
            "attributed_revenue": round(
                max(
                    0,
                    np.random.normal(500, 1800)
                ),
                2
            )
        })

    df = pd.DataFrame(rows)

    save_csv(df, "marketing_touches.csv")

    return df


# ============================================================
# 9. SUBSCRIPTIONS
# ============================================================

def generate_subscriptions(accounts):

    selected_accounts = np.random.choice(
        accounts["account_id"],
        size=N_SUBSCRIPTIONS,
        replace=False
    )

    plans = weighted_choice(
        ["Basic", "Professional", "Business", "Enterprise"],
        [0.30, 0.36, 0.24, 0.10],
        N_SUBSCRIPTIONS
    )

    monthly_price_map = {
        "Basic": 499,
        "Professional": 1_499,
        "Business": 3_999,
        "Enterprise": 9_999
    }

    rows = []

    for i, account_id in enumerate(selected_accounts):

        plan = plans[i]

        start_date = random_date(
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2026-08-01")
        )

        churn_flag = np.random.choice(
            [1, 0],
            p=[0.16, 0.84]
        )

        end_date = pd.NaT

        status = "Active"

        if churn_flag == 1:

            possible_end = (
                start_date
                + pd.Timedelta(
                    days=random.randint(30, 600)
                )
            )

            if possible_end <= END_DATE:
                end_date = possible_end
                status = "Cancelled"
            else:
                churn_flag = 0

        monthly_price = monthly_price_map[plan]

        # Add pricing variation
        monthly_price = monthly_price * np.random.uniform(
            0.90,
            1.25
        )

        rows.append({
            "subscription_id": random_id(
                "SUB",
                i + 1,
                7
            ),
            "account_id": account_id,
            "plan_name": plan,
            "subscription_start_date": start_date,
            "subscription_end_date": end_date,
            "monthly_recurring_revenue": round(
                monthly_price,
                2
            ),
            "annual_recurring_revenue": round(
                monthly_price * 12,
                2
            ),
            "status": status,
            "churn_flag": churn_flag
        })

    df = pd.DataFrame(rows)

    save_csv(df, "subscriptions.csv")

    return df


# ============================================================
# 10. INVOICES
# ============================================================

def generate_invoices(subscriptions):

    subscription_records = (
        subscriptions
        .set_index("subscription_id")
        .to_dict("index")
    )

    subscription_ids = list(
        subscription_records.keys()
    )

    rows = []

    for i in range(N_INVOICES):

        subscription_id = random.choice(
            subscription_ids
        )

        sub = subscription_records[
            subscription_id
        ]

        invoice_date = random_date(
            max(
                pd.Timestamp(sub["subscription_start_date"]),
                START_DATE
            ),
            END_DATE
        )

        base_amount = sub[
            "monthly_recurring_revenue"
        ]

        invoice_amount = base_amount * np.random.uniform(
            0.95,
            1.08
        )

        payment_status = np.random.choice(
            ["Paid", "Past Due", "Failed"],
            p=[0.92, 0.05, 0.03]
        )

        payment_date = pd.NaT

        if payment_status == "Paid":
            payment_date = (
                invoice_date
                + pd.Timedelta(
                    days=random.randint(0, 15)
                )
            )

        rows.append({
            "invoice_id": random_id(
                "INV",
                i + 1,
                9
            ),
            "subscription_id": subscription_id,
            "account_id": sub["account_id"],
            "invoice_date": invoice_date,
            "invoice_amount": round(
                invoice_amount,
                2
            ),
            "payment_status": payment_status,
            "payment_date": payment_date,
            "currency": "USD"
        })

    df = pd.DataFrame(rows)

    save_csv(df, "invoices.csv")

    return df


# ============================================================
# 11. SUPPORT TICKETS
# ============================================================

def generate_support_tickets(
    accounts,
    contacts
):

    contact_lookup = (
        contacts.groupby("account_id")["contact_id"]
        .apply(list)
        .to_dict()
    )

    ticket_categories = [
        "Login / Access",
        "Billing",
        "Product Bug",
        "Integration",
        "Performance",
        "Feature Request",
        "Configuration",
        "Reporting"
    ]

    priorities = [
        "Low",
        "Medium",
        "High",
        "Critical"
    ]

    sentiments = [
        "Positive",
        "Neutral",
        "Negative",
        "Very Negative"
    ]

    rows = []

    account_ids = accounts["account_id"].tolist()

    for i in range(N_SUPPORT_TICKETS):

        account_id = random.choice(account_ids)

        available_contacts = contact_lookup.get(
            account_id,
            []
        )

        contact_id = (
            random.choice(available_contacts)
            if available_contacts
            else None
        )

        created_at = random_date()

        priority = np.random.choice(
            priorities,
            p=[0.30, 0.42, 0.22, 0.06]
        )

        resolution_hours_map = {
            "Low": np.random.uniform(18, 96),
            "Medium": np.random.uniform(8, 48),
            "High": np.random.uniform(2, 24),
            "Critical": np.random.uniform(0.5, 8)
        }

        resolution_hours = resolution_hours_map[
            priority
        ]

        resolved_at = (
            created_at
            + pd.Timedelta(
                hours=float(resolution_hours)
            )
        )

        if resolved_at > END_DATE:
            resolved_at = pd.NaT

        sentiment = np.random.choice(
            sentiments,
            p=[0.15, 0.35, 0.38, 0.12]
        )

        rows.append({
            "ticket_id": random_id(
                "TKT",
                i + 1,
                8
            ),
            "account_id": account_id,
            "contact_id": contact_id,
            "created_at": created_at,
            "resolved_at": resolved_at,
            "ticket_category": random.choice(
                ticket_categories
            ),
            "priority": priority,
            "status": (
                "Resolved"
                if pd.notna(resolved_at)
                else "Open"
            ),
            "resolution_hours": round(
                resolution_hours,
                2
            ) if pd.notna(resolved_at) else None,
            "customer_sentiment": sentiment,
            "csat_score": (
                random.randint(1, 2)
                if sentiment == "Very Negative"
                else random.randint(2, 3)
                if sentiment == "Negative"
                else random.randint(3, 4)
                if sentiment == "Neutral"
                else random.randint(4, 5)
            )
        })

    df = pd.DataFrame(rows)

    save_csv(df, "support_tickets.csv")

    return df


# ============================================================
# 12. WEBSITE EVENTS
# ============================================================

def generate_website_events(
    leads,
    contacts,
    campaigns
):

    event_types = [
        "page_view",
        "pricing_view",
        "product_view",
        "blog_view",
        "form_start",
        "form_submit",
        "demo_request",
        "signup",
        "login",
        "checkout_start",
        "purchase"
    ]

    pages = [
        "/",
        "/pricing",
        "/product",
        "/solutions",
        "/enterprise",
        "/blog",
        "/resources",
        "/demo",
        "/signup",
        "/checkout"
    ]

    channels = [
        "Organic Search",
        "Google Ads",
        "LinkedIn Ads",
        "Meta Ads",
        "Email",
        "Direct",
        "Referral"
    ]

    lead_ids = leads["lead_id"].tolist()
    contact_ids = contacts["contact_id"].tolist()
    campaign_ids = campaigns["campaign_id"].tolist()

    rows = []

    for i in range(N_WEBSITE_EVENTS):

        visitor_type = np.random.choice(
            ["anonymous", "lead", "contact"],
            p=[0.50, 0.30, 0.20]
        )

        lead_id = None
        contact_id = None

        if visitor_type == "lead":
            lead_id = random.choice(lead_ids)

        elif visitor_type == "contact":
            contact_id = random.choice(
                contact_ids
            )

        event_type = np.random.choice(
            event_types,
            p=[
                0.35,
                0.09,
                0.12,
                0.10,
                0.06,
                0.05,
                0.04,
                0.05,
                0.05,
                0.05,
                0.04
            ]
        )

        rows.append({
            "event_id": random_id(
                "EVT",
                i + 1,
                10
            ),
            "session_id": random_id(
                "SES",
                random.randint(
                    1,
                    max(
                        1,
                        int(
                            N_WEBSITE_EVENTS / 4
                        )
                    )
                ),
                10
            ),
            "event_timestamp": random_date(),
            "visitor_type": visitor_type,
            "lead_id": lead_id,
            "contact_id": contact_id,
            "campaign_id": (
                random.choice(campaign_ids)
                if random.random() < 0.65
                else None
            ),
            "event_type": event_type,
            "page_path": random.choice(pages),
            "traffic_source": random.choice(
                channels
            ),
            "device_type": np.random.choice(
                [
                    "Desktop",
                    "Mobile",
                    "Tablet"
                ],
                p=[0.55, 0.40, 0.05]
            ),
            "country": fake.country(),
            "revenue": (
                round(
                    np.random.lognormal(
                        mean=np.log(1000),
                        sigma=0.8
                    ),
                    2
                )
                if event_type == "purchase"
                else 0
            )
        })

    df = pd.DataFrame(rows)

    save_csv(df, "website_events.csv")

    return df


# ============================================================
# DATA QUALITY ISSUES
# ============================================================

def inject_data_quality_issues(
    accounts,
    leads,
    opportunities
):
    """
    Deliberately introduce small amounts of bad source data.
    This gives you realistic problems to clean with dbt.
    """

    # --------------------------------------------------------
    # Missing industries
    # --------------------------------------------------------
    sample_size = int(
        len(accounts) * 0.005
    )

    missing_indices = np.random.choice(
        accounts.index,
        sample_size,
        replace=False
    )

    accounts.loc[
        missing_indices,
        "industry"
    ] = None

    # --------------------------------------------------------
    # Inconsistent regions
    # --------------------------------------------------------
    bad_region_indices = np.random.choice(
        accounts.index,
        int(len(accounts) * 0.003),
        replace=False
    )

    accounts.loc[
        bad_region_indices,
        "region"
    ] = np.random.choice(
        ["NA", "N. America", "north america"],
        len(bad_region_indices)
    )

    # --------------------------------------------------------
    # Missing lead sources
    # --------------------------------------------------------
    lead_missing_indices = np.random.choice(
        leads.index,
        int(len(leads) * 0.005),
        replace=False
    )

    leads.loc[
        lead_missing_indices,
        "lead_source"
    ] = None

    # --------------------------------------------------------
    # Unexpected opportunity stage
    # --------------------------------------------------------
    bad_stage_indices = np.random.choice(
        opportunities.index,
        int(len(opportunities) * 0.002),
        replace=False
    )

    opportunities.loc[
        bad_stage_indices,
        "stage"
    ] = "Closed-Won"

    return accounts, leads, opportunities


# ============================================================
# MAIN
# ============================================================

def main():

    print("\nGenerating synthetic analytics dataset...\n")

    sales_reps = generate_sales_reps()

    accounts = generate_accounts(
        sales_reps
    )

    contacts = generate_contacts(
        accounts
    )

    campaigns = generate_campaigns()

    leads = generate_leads(
        campaigns,
        sales_reps
    )

    opportunities = generate_opportunities(
        accounts,
        sales_reps,
        campaigns
    )

    # Inject issues before final save
    accounts, leads, opportunities = (
        inject_data_quality_issues(
            accounts,
            leads,
            opportunities
        )
    )

    # Re-save modified raw tables
    save_csv(
        accounts,
        "accounts.csv"
    )

    save_csv(
        leads,
        "leads.csv"
    )

    save_csv(
        opportunities,
        "opportunities.csv"
    )

    opportunity_history = (
        generate_opportunity_history(
            opportunities
        )
    )

    marketing_touches = (
        generate_marketing_touches(
            leads,
            contacts,
            campaigns
        )
    )

    subscriptions = (
        generate_subscriptions(
            accounts
        )
    )

    invoices = generate_invoices(
        subscriptions
    )

    support_tickets = (
        generate_support_tickets(
            accounts,
            contacts
        )
    )

    website_events = (
        generate_website_events(
            leads,
            contacts,
            campaigns
        )
    )

    print("\nGeneration complete.")
    print(
        f"Files written to: "
        f"{OUTPUT_DIR.resolve()}"
    )


if __name__ == "__main__":
    main()
