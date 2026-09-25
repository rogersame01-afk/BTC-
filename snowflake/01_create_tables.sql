-- ============================================================
-- NovaFlow raw layer: file format, stage and the 12 raw tables
-- Target: NOVAFLOW.NOVAFLOW_SALES_OPPS
-- Safe to re-run (CREATE OR REPLACE drops existing data).
-- ============================================================
USE DATABASE NOVAFLOW;
USE SCHEMA NOVAFLOW_SALES_OPPS;

CREATE OR REPLACE FILE FORMAT CSV_RAW_FF
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('')
    EMPTY_FIELD_AS_NULL = TRUE
    TIMESTAMP_FORMAT = AUTO
    ENCODING = 'UTF8';

CREATE OR REPLACE STAGE RAW_STAGE
    FILE_FORMAT = CSV_RAW_FF
    COMMENT = 'Landing area for NovaFlow raw CSV files';

CREATE OR REPLACE TABLE SALES_REPS (
    sales_rep_id        VARCHAR(20),
    sales_rep_name      VARCHAR(100),
    role                VARCHAR(100),
    region              VARCHAR(50),
    hire_date           TIMESTAMP_NTZ(9),
    annual_quota        NUMBER(14,2),
    manager_name        VARCHAR(100),
    active_flag         NUMBER(1,0)
);

CREATE OR REPLACE TABLE ACCOUNTS (
    account_id                VARCHAR(20),
    account_name              VARCHAR(200),
    industry                  VARCHAR(100),
    segment                   VARCHAR(50),
    region                    VARCHAR(50),
    country                   VARCHAR(100),
    employee_count            NUMBER(10,0),
    estimated_annual_revenue  NUMBER(18,2),
    created_at                TIMESTAMP_NTZ(9),
    account_owner_id          VARCHAR(20)
);

CREATE OR REPLACE TABLE CONTACTS (
    contact_id           VARCHAR(20),
    account_id           VARCHAR(20),
    first_name           VARCHAR(100),
    last_name            VARCHAR(100),
    job_title            VARCHAR(100),
    email                VARCHAR(200),
    phone                VARCHAR(50),
    created_at           TIMESTAMP_NTZ(9),
    decision_maker_flag  NUMBER(1,0)
);

CREATE OR REPLACE TABLE CAMPAIGNS (
    campaign_id    VARCHAR(20),
    campaign_name  VARCHAR(200),
    channel        VARCHAR(50),
    campaign_type  VARCHAR(50),
    start_date     TIMESTAMP_NTZ(9),
    end_date       TIMESTAMP_NTZ(9),
    budget         NUMBER(14,2),
    region         VARCHAR(50),
    status         VARCHAR(20)
);

CREATE OR REPLACE TABLE LEADS (
    lead_id         VARCHAR(20),
    created_at      TIMESTAMP_NTZ(9),
    lead_source     VARCHAR(50),
    campaign_id     VARCHAR(20),
    lead_status     VARCHAR(30),
    lead_score      NUMBER(3,0),
    industry        VARCHAR(100),
    company_size    VARCHAR(50),
    sales_rep_id    VARCHAR(20),
    converted_flag  NUMBER(1,0)
);

CREATE OR REPLACE TABLE OPPORTUNITIES (
    opportunity_id       VARCHAR(20),
    account_id           VARCHAR(20),
    sales_rep_id         VARCHAR(20),
    campaign_id          VARCHAR(20),
    opportunity_name     VARCHAR(300),
    segment              VARCHAR(50),
    stage                VARCHAR(50),
    amount               NUMBER(14,2),
    probability          NUMBER(5,2),
    created_at           TIMESTAMP_NTZ(9),
    expected_close_date  TIMESTAMP_NTZ(9),
    actual_close_date    TIMESTAMP_NTZ(9),
    sales_cycle_days     NUMBER(6,0),
    closed_won_flag      NUMBER(1,0),
    closed_lost_flag     NUMBER(1,0)
);

CREATE OR REPLACE TABLE OPPORTUNITY_HISTORY (
    opportunity_history_id  VARCHAR(20),
    opportunity_id          VARCHAR(20),
    stage                   VARCHAR(50),
    stage_sequence          NUMBER(3,0),
    entered_stage_at        TIMESTAMP_NTZ(9),
    exited_stage_at         TIMESTAMP_NTZ(9),
    days_in_stage           NUMBER(6,1)   -- written as 12.0 in the CSV
);

CREATE OR REPLACE TABLE MARKETING_TOUCHES (
    marketing_touch_id  VARCHAR(20),
    lead_id             VARCHAR(20),
    contact_id          VARCHAR(20),
    campaign_id         VARCHAR(20),
    touch_timestamp     TIMESTAMP_NTZ(9),
    channel             VARCHAR(50),
    touch_type          VARCHAR(50),
    device_type         VARCHAR(20),
    utm_source          VARCHAR(50),
    utm_medium          VARCHAR(50),
    attributed_revenue  NUMBER(14,2)
);

CREATE OR REPLACE TABLE SUBSCRIPTIONS (
    subscription_id            VARCHAR(20),
    account_id                 VARCHAR(20),
    plan_name                  VARCHAR(50),
    subscription_start_date    TIMESTAMP_NTZ(9),
    subscription_end_date      TIMESTAMP_NTZ(9),
    monthly_recurring_revenue  NUMBER(14,2),
    annual_recurring_revenue   NUMBER(14,2),
    status                     VARCHAR(20),
    churn_flag                 NUMBER(1,0)
);

CREATE OR REPLACE TABLE INVOICES (
    invoice_id       VARCHAR(20),
    subscription_id  VARCHAR(20),
    account_id       VARCHAR(20),
    invoice_date     TIMESTAMP_NTZ(9),
    invoice_amount   NUMBER(14,2),
    payment_status   VARCHAR(20),
    payment_date     TIMESTAMP_NTZ(9),
    currency         VARCHAR(3)
);

CREATE OR REPLACE TABLE SUPPORT_TICKETS (
    ticket_id           VARCHAR(20),
    account_id          VARCHAR(20),
    contact_id          VARCHAR(20),
    created_at          TIMESTAMP_NTZ(9),
    resolved_at         TIMESTAMP_NTZ(9),
    ticket_category     VARCHAR(50),
    priority            VARCHAR(20),
    status              VARCHAR(20),
    resolution_hours    NUMBER(10,2),
    customer_sentiment  VARCHAR(20),
    csat_score          NUMBER(1,0)
);

CREATE OR REPLACE TABLE WEBSITE_EVENTS (
    event_id         VARCHAR(20),
    session_id       VARCHAR(20),
    event_timestamp  TIMESTAMP_NTZ(9),
    visitor_type     VARCHAR(20),
    lead_id          VARCHAR(20),
    contact_id       VARCHAR(20),
    campaign_id      VARCHAR(20),
    event_type       VARCHAR(50),
    page_path        VARCHAR(200),
    traffic_source   VARCHAR(50),
    device_type      VARCHAR(20),
    country          VARCHAR(100),
    revenue          NUMBER(14,2)
);
