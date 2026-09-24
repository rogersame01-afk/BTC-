"""Static configuration for the NovaFlow synthetic data generator.

NovaFlow is a fictional B2B SaaS analytics platform. Everything in this file
is a tunable assumption about how the business behaves.
"""
from datetime import date

START_DATE = date(2022, 1, 1)
END_DATE = date(2026, 6, 30)  # snapshot date: the data is "as of" this day
DEFAULT_SEED = 42

# Row-count targets at scale=1.0 (leads/sessions are sized so that funnel
# conversion rates stay realistic: ~15% lead->opportunity). Opportunities, accounts, subscriptions,
# invoices and payments are *emergent* from the simulated customer lifecycle
# and land near ~300k opportunities / ~200k billing transactions.
TARGETS = {
    "customers": 100_000,
    "leads": 250_000,
    "website_sessions": 400_000,
    "website_events": 1_000_000,
    "sales_activities": 500_000,
    "support_tickets": 50_000,
}
N_SALES_REPS = 250
N_CAMPAIGNS = 600
N_SUPPORT_AGENTS = 60

# --------------------------------------------------------------------------
# Geography
# --------------------------------------------------------------------------
REGIONS = {
    "North America": {"weight": 0.48, "countries": {"United States": 0.85, "Canada": 0.15}},
    "EMEA": {"weight": 0.30, "countries": {
        "United Kingdom": 0.30, "Germany": 0.22, "France": 0.15, "Netherlands": 0.10,
        "Spain": 0.07, "Ireland": 0.06, "Sweden": 0.05, "United Arab Emirates": 0.05}},
    "APAC": {"weight": 0.16, "countries": {
        "Australia": 0.30, "Singapore": 0.20, "Japan": 0.20, "India": 0.20, "New Zealand": 0.10}},
    "LATAM": {"weight": 0.06, "countries": {"Brazil": 0.50, "Mexico": 0.30, "Colombia": 0.10, "Chile": 0.10}},
}

CITIES = {
    "United States": ["New York", "San Francisco", "Austin", "Chicago", "Boston", "Seattle", "Denver",
                      "Atlanta", "Los Angeles", "Miami", "Dallas", "Raleigh", "Minneapolis", "Salt Lake City"],
    "Canada": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"],
    "United Kingdom": ["London", "Manchester", "Edinburgh", "Bristol", "Leeds"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
    "France": ["Paris", "Lyon", "Toulouse", "Nantes"],
    "Netherlands": ["Amsterdam", "Rotterdam", "Utrecht", "Eindhoven"],
    "Spain": ["Madrid", "Barcelona", "Valencia"],
    "Ireland": ["Dublin", "Cork", "Galway"],
    "Sweden": ["Stockholm", "Gothenburg", "Malmo"],
    "United Arab Emirates": ["Dubai", "Abu Dhabi"],
    "Australia": ["Sydney", "Melbourne", "Brisbane", "Perth"],
    "Singapore": ["Singapore"],
    "Japan": ["Tokyo", "Osaka", "Fukuoka"],
    "India": ["Bengaluru", "Mumbai", "Hyderabad", "Pune", "Delhi"],
    "New Zealand": ["Auckland", "Wellington"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Belo Horizonte"],
    "Mexico": ["Mexico City", "Monterrey", "Guadalajara"],
    "Colombia": ["Bogota", "Medellin"],
    "Chile": ["Santiago"],
}

CURRENCY_BY_COUNTRY = {
    "United States": "USD", "Canada": "CAD", "United Kingdom": "GBP", "Germany": "EUR", "France": "EUR",
    "Netherlands": "EUR", "Spain": "EUR", "Ireland": "EUR", "Sweden": "SEK", "United Arab Emirates": "USD",
    "Australia": "AUD", "Singapore": "SGD", "Japan": "JPY", "India": "INR", "New Zealand": "NZD",
    "Brazil": "BRL", "Mexico": "MXN", "Colombia": "USD", "Chile": "USD",
}
# Fixed rates: 1 unit of currency = X USD
FX_TO_USD = {"USD": 1.0, "CAD": 0.74, "GBP": 1.27, "EUR": 1.09, "SEK": 0.095, "AUD": 0.66, "SGD": 0.74,
             "JPY": 0.0068, "INR": 0.012, "NZD": 0.61, "BRL": 0.19, "MXN": 0.055}
TAX_RATE_BY_REGION = {"North America": 0.0, "EMEA": 0.20, "APAC": 0.10, "LATAM": 0.16}

# --------------------------------------------------------------------------
# Firmographics
# --------------------------------------------------------------------------
INDUSTRIES = {  # name: (weight, win-rate multiplier)
    "Technology": (0.22, 1.15),
    "Financial Services": (0.12, 1.00),
    "Retail & E-commerce": (0.11, 1.05),
    "Healthcare": (0.09, 0.90),
    "Manufacturing": (0.09, 0.90),
    "Professional Services": (0.08, 1.00),
    "Media & Entertainment": (0.06, 1.05),
    "Education": (0.06, 0.85),
    "Logistics & Transportation": (0.05, 0.95),
    "Telecommunications": (0.04, 0.95),
    "Energy & Utilities": (0.03, 0.85),
    "Government & Public Sector": (0.03, 0.70),
    "Hospitality": (0.02, 0.90),
}

SEGMENTS = {
    "SMB": dict(
        share=0.62, employees=(12, 200, 60), win_rate=0.23, cycle_median=25,
        seats_median=12, seats_sigma=0.6, tiers={"Starter": 0.6, "Professional": 0.4},
        discount=(0.0, 0.12), monthly_share=0.18, terms=[12], expansion_rate=1.0,
        activity_rate=0.22, ticket_rate=0.35,
    ),
    "Mid-Market": dict(
        share=0.29, employees=(200, 2000, 600), win_rate=0.19, cycle_median=55,
        seats_median=40, seats_sigma=0.6, tiers={"Professional": 0.75, "Enterprise": 0.25},
        discount=(0.05, 0.22), monthly_share=0.05, terms=[12, 12, 24], expansion_rate=1.9,
        activity_rate=0.20, ticket_rate=0.9,
    ),
    "Enterprise": dict(
        share=0.09, employees=(2000, 150000, 8000), win_rate=0.15, cycle_median=110,
        seats_median=90, seats_sigma=0.7, tiers={"Enterprise": 1.0},
        discount=(0.10, 0.35), monthly_share=0.0, terms=[12, 24, 36], expansion_rate=3.0,
        activity_rate=0.20, ticket_rate=2.2,
    ),
}

# --------------------------------------------------------------------------
# Go-to-market
# --------------------------------------------------------------------------
# source: (weight by segment [SMB, MM, ENT], campaign channel, win multiplier, arrives via website)
LEAD_SOURCES = {
    "Organic Search":       ([0.20, 0.12, 0.05], None, 1.00, True),
    "Paid Search":          ([0.16, 0.10, 0.04], "Paid Search", 0.90, True),
    "Paid Social":          ([0.10, 0.07, 0.03], "Paid Social", 0.80, True),
    "Content Syndication":  ([0.06, 0.09, 0.07], "Content Syndication", 0.85, True),
    "Webinar":              ([0.06, 0.09, 0.08], "Webinar", 1.05, True),
    "Email Nurture":        ([0.05, 0.06, 0.04], "Email Nurture", 0.90, True),
    "Free Trial":           ([0.15, 0.07, 0.02], None, 1.15, True),
    "Direct":               ([0.06, 0.05, 0.04], None, 1.10, True),
    "Trade Show":           ([0.02, 0.08, 0.13], "Trade Show", 0.95, False),
    "Partner Referral":     ([0.04, 0.08, 0.10], "Partner", 1.25, False),
    "Customer Referral":    ([0.04, 0.05, 0.06], None, 1.40, False),
    "ABM":                  ([0.00, 0.04, 0.18], "ABM", 1.10, False),
    "Outbound Prospecting": ([0.06, 0.10, 0.16], None, 0.75, False),
}

# Share of first New Business deals that originate from a lead record (the rest
# are AE-sourced / partner-sourced straight to an opportunity).
LEAD_ORIGIN_SHARE = {"Outbound Prospecting": 0.3, "Customer Referral": 0.3, "Partner Referral": 0.4, "ABM": 0.4,
                     "Trade Show": 0.6}
LEAD_ORIGIN_DEFAULT = 0.65
WEB_TRACKING_COVERAGE = 0.3  # consent banners / ad blockers: not every visit is tracked

CAMPAIGN_CHANNELS = {  # channel: (weight, duration days range, budget range, campaign type)
    "Paid Search": (0.20, (60, 120), (15_000, 80_000), "Digital"),
    "Paid Social": (0.15, (45, 90), (10_000, 60_000), "Digital"),
    "Webinar": (0.15, (21, 45), (3_000, 15_000), "Event"),
    "Trade Show": (0.08, (14, 40), (25_000, 150_000), "Event"),
    "Content Syndication": (0.12, (60, 120), (8_000, 40_000), "Content"),
    "Email Nurture": (0.15, (30, 90), (1_000, 6_000), "Email"),
    "Partner": (0.07, (60, 180), (5_000, 30_000), "Partner"),
    "ABM": (0.08, (60, 150), (20_000, 90_000), "ABM"),
}
CAMPAIGN_THEMES = [
    "Modern Data Stack", "AI-Powered Insights", "Self-Serve BI", "Revenue Analytics", "Data Governance",
    "Embedded Analytics", "Cost Optimization", "Real-time Dashboards", "Customer 360", "Cloud Migration",
    "Finance Analytics", "Retail Forecasting", "Product Analytics", "Executive Reporting",
]

NB_LOSS_REASONS = {"No Decision": 0.24, "Lost to Competitor": 0.20, "Price": 0.16, "No Budget": 0.13,
                   "Missing Features": 0.10, "Timing": 0.10, "Unresponsive": 0.07}
CHURN_REASONS = {"Low Adoption": 0.24, "Budget Cuts": 0.20, "Switched to Competitor": 0.18,
                 "Missing Features": 0.12, "Poor Support Experience": 0.10, "Company Acquired": 0.08,
                 "Business Closed": 0.08}

OPEN_STAGES = [("Prospecting", 10), ("Qualification", 20), ("Discovery", 30),
               ("Solution Demo", 40), ("Proposal", 60), ("Negotiation", 80)]

BUYER_TITLES = ["Head of Data", "VP of Analytics", "Director of Business Intelligence", "Data Engineer",
                "Analytics Manager", "CFO", "CTO", "COO", "Chief Data Officer", "BI Developer",
                "Marketing Operations Manager", "Revenue Operations Manager", "Data Scientist",
                "VP of Finance", "IT Director", "Product Manager"]
