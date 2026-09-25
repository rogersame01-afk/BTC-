-- ============================================================
-- STEP: stage files -> raw tables (run in a Snowsight worksheet)
-- Safe to re-run: creates only missing objects, never touches the
-- uploaded files, empties each table before loading it.
-- ============================================================
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE NOVAFLOW;
USE SCHEMA NOVAFLOW_RAW;

-- 0) confirm the 12 CSVs are on the stage
LIST @RAW_STAGE;

-- 1) file format + tables (only created if they don't exist yet)
CREATE FILE FORMAT IF NOT EXISTS CSV_RAW_FF
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    NULL_IF = ('')
    EMPTY_FIELD_AS_NULL = TRUE
    TIMESTAMP_FORMAT = AUTO
    ENCODING = 'UTF8';
CREATE TABLE IF NOT EXISTS SALES_REPS (
    sales_rep_id        VARCHAR(20),
    sales_rep_name      VARCHAR(100),
    role                VARCHAR(100),
    region              VARCHAR(50),
    hire_date           TIMESTAMP_NTZ(9),
    annual_quota        NUMBER(14,2),
    manager_name        VARCHAR(100),
    active_flag         NUMBER(1,0)
);

CREATE TABLE IF NOT EXISTS ACCOUNTS (
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

CREATE TABLE IF NOT EXISTS CONTACTS (
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

CREATE TABLE IF NOT EXISTS CAMPAIGNS (
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

CREATE TABLE IF NOT EXISTS LEADS (
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

CREATE TABLE IF NOT EXISTS OPPORTUNITIES (
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

CREATE TABLE IF NOT EXISTS OPPORTUNITY_HISTORY (
    opportunity_history_id  VARCHAR(20),
    opportunity_id          VARCHAR(20),
    stage                   VARCHAR(50),
    stage_sequence          NUMBER(3,0),
    entered_stage_at        TIMESTAMP_NTZ(9),
    exited_stage_at         TIMESTAMP_NTZ(9),
    days_in_stage           NUMBER(6,1)   -- written as 12.0 in the CSV
);

CREATE TABLE IF NOT EXISTS MARKETING_TOUCHES (
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

CREATE TABLE IF NOT EXISTS SUBSCRIPTIONS (
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

CREATE TABLE IF NOT EXISTS INVOICES (
    invoice_id       VARCHAR(20),
    subscription_id  VARCHAR(20),
    account_id       VARCHAR(20),
    invoice_date     TIMESTAMP_NTZ(9),
    invoice_amount   NUMBER(14,2),
    payment_status   VARCHAR(20),
    payment_date     TIMESTAMP_NTZ(9),
    currency         VARCHAR(3)
);

CREATE TABLE IF NOT EXISTS SUPPORT_TICKETS (
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

CREATE TABLE IF NOT EXISTS WEBSITE_EVENTS (
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

-- 2) load: stage files -> tables
TRUNCATE TABLE SALES_REPS;          COPY INTO SALES_REPS          FROM @RAW_STAGE/sales_reps.csv          FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE ACCOUNTS;            COPY INTO ACCOUNTS            FROM @RAW_STAGE/accounts.csv            FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE CONTACTS;            COPY INTO CONTACTS            FROM @RAW_STAGE/contacts.csv            FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE CAMPAIGNS;           COPY INTO CAMPAIGNS           FROM @RAW_STAGE/campaigns.csv           FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE LEADS;               COPY INTO LEADS               FROM @RAW_STAGE/leads.csv               FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE OPPORTUNITIES;       COPY INTO OPPORTUNITIES       FROM @RAW_STAGE/opportunities.csv       FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE OPPORTUNITY_HISTORY; COPY INTO OPPORTUNITY_HISTORY FROM @RAW_STAGE/opportunity_history.csv FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE MARKETING_TOUCHES;   COPY INTO MARKETING_TOUCHES   FROM @RAW_STAGE/marketing_touches.csv   FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE SUBSCRIPTIONS;       COPY INTO SUBSCRIPTIONS       FROM @RAW_STAGE/subscriptions.csv       FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE INVOICES;            COPY INTO INVOICES            FROM @RAW_STAGE/invoices.csv            FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE SUPPORT_TICKETS;     COPY INTO SUPPORT_TICKETS     FROM @RAW_STAGE/support_tickets.csv     FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE WEBSITE_EVENTS;      COPY INTO WEBSITE_EVENTS      FROM @RAW_STAGE/website_events.csv      FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;


-- 3) check row counts
SELECT 'sales_reps' AS table_name, COUNT(*) AS row_count FROM SALES_REPS
UNION ALL SELECT 'accounts', COUNT(*) FROM ACCOUNTS
UNION ALL SELECT 'contacts', COUNT(*) FROM CONTACTS
UNION ALL SELECT 'campaigns', COUNT(*) FROM CAMPAIGNS
UNION ALL SELECT 'leads', COUNT(*) FROM LEADS
UNION ALL SELECT 'opportunities', COUNT(*) FROM OPPORTUNITIES
UNION ALL SELECT 'opportunity_history', COUNT(*) FROM OPPORTUNITY_HISTORY
UNION ALL SELECT 'marketing_touches', COUNT(*) FROM MARKETING_TOUCHES
UNION ALL SELECT 'subscriptions', COUNT(*) FROM SUBSCRIPTIONS
UNION ALL SELECT 'invoices', COUNT(*) FROM INVOICES
UNION ALL SELECT 'support_tickets', COUNT(*) FROM SUPPORT_TICKETS
UNION ALL SELECT 'website_events', COUNT(*) FROM WEBSITE_EVENTS
ORDER BY table_name;
