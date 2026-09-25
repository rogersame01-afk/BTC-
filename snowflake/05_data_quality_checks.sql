-- =====================================================================
-- NovaFlow raw layer: data profiling & data-quality checks
-- Run block by block in a Snowsight worksheet whose context is set to
--   Database NOVAFLOW   Schema NOVAFLOW_RAW   (top-right of the worksheet)
-- Select a block and press Ctrl+Enter, or put the cursor in a statement.
-- "Snapshot" date of the generated data = 2026-09-01.
-- =====================================================================
USE DATABASE NOVAFLOW;
USE SCHEMA NOVAFLOW_RAW;


-- =====================================================================
-- STEP 1  Volume & structure overview
-- =====================================================================
SELECT table_name, row_count, ROUND(bytes / 1024 / 1024, 1) AS size_mb
FROM NOVAFLOW.INFORMATION_SCHEMA.TABLES
WHERE table_schema = 'NOVAFLOW_RAW' AND table_type = 'BASE TABLE'
ORDER BY row_count DESC;

SELECT table_name, column_name, data_type, ordinal_position
FROM NOVAFLOW.INFORMATION_SCHEMA.COLUMNS
WHERE table_schema = 'NOVAFLOW_RAW'
ORDER BY table_name, ordinal_position;


-- =====================================================================
-- STEP 2  Completeness: NULL count and % for EVERY column of EVERY table
-- (builds the query from INFORMATION_SCHEMA and runs it)
-- =====================================================================
EXECUTE IMMEDIATE $$
DECLARE
    q   STRING;
    res RESULTSET;
BEGIN
    SELECT LISTAGG(
             'SELECT ''' || table_name || ''' AS table_name, ''' || column_name || ''' AS column_name, '
          || 'COUNT(*) AS total_rows, COUNT(*) - COUNT(' || column_name || ') AS null_rows, '
          || 'ROUND(100 * (COUNT(*) - COUNT(' || column_name || ')) / NULLIF(COUNT(*), 0), 2) AS null_pct '
          || 'FROM NOVAFLOW.NOVAFLOW_RAW.' || table_name,
             ' UNION ALL ') WITHIN GROUP (ORDER BY table_name, ordinal_position)
    INTO :q
    FROM NOVAFLOW.INFORMATION_SCHEMA.COLUMNS
    WHERE table_schema = 'NOVAFLOW_RAW';
    q := q || ' ORDER BY null_pct DESC, table_name, column_name';
    res := (EXECUTE IMMEDIATE :q);
    RETURN TABLE(res);
END;
$$;


-- =====================================================================
-- STEP 3  Uniqueness: primary keys and natural keys
-- =====================================================================
SELECT 'accounts.account_id' AS key_column, COUNT(*) AS total_rows, COUNT(DISTINCT account_id) AS distinct_values, COUNT(*) - COUNT(DISTINCT account_id) AS duplicates FROM ACCOUNTS
UNION ALL SELECT 'contacts.contact_id', COUNT(*), COUNT(DISTINCT contact_id), COUNT(*) - COUNT(DISTINCT contact_id) FROM CONTACTS
UNION ALL SELECT 'leads.lead_id', COUNT(*), COUNT(DISTINCT lead_id), COUNT(*) - COUNT(DISTINCT lead_id) FROM LEADS
UNION ALL SELECT 'opportunities.opportunity_id', COUNT(*), COUNT(DISTINCT opportunity_id), COUNT(*) - COUNT(DISTINCT opportunity_id) FROM OPPORTUNITIES
UNION ALL SELECT 'opportunity_history.opportunity_history_id', COUNT(*), COUNT(DISTINCT opportunity_history_id), COUNT(*) - COUNT(DISTINCT opportunity_history_id) FROM OPPORTUNITY_HISTORY
UNION ALL SELECT 'sales_reps.sales_rep_id', COUNT(*), COUNT(DISTINCT sales_rep_id), COUNT(*) - COUNT(DISTINCT sales_rep_id) FROM SALES_REPS
UNION ALL SELECT 'campaigns.campaign_id', COUNT(*), COUNT(DISTINCT campaign_id), COUNT(*) - COUNT(DISTINCT campaign_id) FROM CAMPAIGNS
UNION ALL SELECT 'marketing_touches.marketing_touch_id', COUNT(*), COUNT(DISTINCT marketing_touch_id), COUNT(*) - COUNT(DISTINCT marketing_touch_id) FROM MARKETING_TOUCHES
UNION ALL SELECT 'subscriptions.subscription_id', COUNT(*), COUNT(DISTINCT subscription_id), COUNT(*) - COUNT(DISTINCT subscription_id) FROM SUBSCRIPTIONS
UNION ALL SELECT 'invoices.invoice_id', COUNT(*), COUNT(DISTINCT invoice_id), COUNT(*) - COUNT(DISTINCT invoice_id) FROM INVOICES
UNION ALL SELECT 'support_tickets.ticket_id', COUNT(*), COUNT(DISTINCT ticket_id), COUNT(*) - COUNT(DISTINCT ticket_id) FROM SUPPORT_TICKETS
UNION ALL SELECT 'website_events.event_id', COUNT(*), COUNT(DISTINCT event_id), COUNT(*) - COUNT(DISTINCT event_id) FROM WEBSITE_EVENTS
-- natural keys (should arguably be unique too)
UNION ALL SELECT 'contacts.email (natural key)', COUNT(*), COUNT(DISTINCT email), COUNT(*) - COUNT(DISTINCT email) FROM CONTACTS
UNION ALL SELECT 'accounts.account_name (natural key)', COUNT(*), COUNT(DISTINCT account_name), COUNT(*) - COUNT(DISTINCT account_name) FROM ACCOUNTS
ORDER BY duplicates DESC;

-- drill-down: most duplicated contact emails
SELECT email, COUNT(*) AS contacts, COUNT(DISTINCT account_id) AS accounts
FROM CONTACTS
GROUP BY email
HAVING COUNT(*) > 1
ORDER BY contacts DESC
LIMIT 20;


-- =====================================================================
-- STEP 4  Validity: categorical columns vs accepted values
-- =====================================================================
-- 4a. profile the distinct values
SELECT 'accounts.region' AS column_name, region AS value, COUNT(*) AS row_count FROM ACCOUNTS GROUP BY region
UNION ALL SELECT 'accounts.segment', segment, COUNT(*) FROM ACCOUNTS GROUP BY segment
UNION ALL SELECT 'accounts.industry', industry, COUNT(*) FROM ACCOUNTS GROUP BY industry
UNION ALL SELECT 'opportunities.stage', stage, COUNT(*) FROM OPPORTUNITIES GROUP BY stage
UNION ALL SELECT 'leads.lead_source', lead_source, COUNT(*) FROM LEADS GROUP BY lead_source
UNION ALL SELECT 'leads.lead_status', lead_status, COUNT(*) FROM LEADS GROUP BY lead_status
UNION ALL SELECT 'subscriptions.plan_name', plan_name, COUNT(*) FROM SUBSCRIPTIONS GROUP BY plan_name
UNION ALL SELECT 'invoices.payment_status', payment_status, COUNT(*) FROM INVOICES GROUP BY payment_status
UNION ALL SELECT 'support_tickets.priority', priority, COUNT(*) FROM SUPPORT_TICKETS GROUP BY priority
UNION ALL SELECT 'campaigns.status', status, COUNT(*) FROM CAMPAIGNS GROUP BY status
ORDER BY column_name, row_count DESC;

-- 4b. rows whose value is NOT in the accepted list (or NULL)
SELECT 'accounts.region' AS check_name, region AS bad_value, COUNT(*) AS rows_failing
FROM ACCOUNTS
WHERE region IS NULL OR region NOT IN ('North America', 'EMEA', 'APAC', 'LATAM')
GROUP BY region
UNION ALL
SELECT 'opportunities.stage', stage, COUNT(*)
FROM OPPORTUNITIES
WHERE stage IS NULL OR stage NOT IN ('Prospecting', 'Discovery', 'Demo', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost')
GROUP BY stage
UNION ALL
SELECT 'leads.lead_source', COALESCE(lead_source, '<NULL>'), COUNT(*)
FROM LEADS
WHERE lead_source IS NULL
   OR lead_source NOT IN ('Google Ads', 'LinkedIn Ads', 'Meta Ads', 'Organic Search', 'Email', 'Webinar', 'Referral', 'Direct', 'Affiliate')
GROUP BY lead_source
UNION ALL
SELECT 'accounts.industry', COALESCE(industry, '<NULL>'), COUNT(*)
FROM ACCOUNTS
WHERE industry IS NULL
GROUP BY industry
ORDER BY check_name;

-- 4c. format checks
SELECT
    COUNT_IF(NOT RLIKE(email, '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')) AS invalid_emails,
    COUNT_IF(phone IS NULL OR LENGTH(REGEXP_REPLACE(phone, '[^0-9]', '')) < 10)       AS short_or_missing_phones,
    COUNT_IF(email ILIKE '%@example.com')                                             AS placeholder_domain_emails
FROM CONTACTS;


-- =====================================================================
-- STEP 5  Ranges: numeric sanity
-- =====================================================================
SELECT
    MIN(amount) AS min_amount, MAX(amount) AS max_amount,
    COUNT_IF(amount <= 0)                          AS non_positive_amounts,
    COUNT_IF(probability NOT BETWEEN 0 AND 1)      AS bad_probability,
    COUNT_IF(sales_cycle_days < 0)                 AS negative_cycle
FROM OPPORTUNITIES;

SELECT
    COUNT_IF(lead_score NOT BETWEEN 0 AND 100)     AS bad_lead_score,
    COUNT_IF(converted_flag NOT IN (0, 1))         AS bad_converted_flag
FROM LEADS;

SELECT
    COUNT_IF(csat_score NOT BETWEEN 1 AND 5)       AS bad_csat,
    COUNT_IF(resolution_hours < 0)                 AS negative_resolution
FROM SUPPORT_TICKETS;

SELECT
    COUNT_IF(monthly_recurring_revenue <= 0)                                        AS bad_mrr,
    COUNT_IF(ABS(annual_recurring_revenue - 12 * monthly_recurring_revenue) > 0.10) AS arr_not_12x_mrr
FROM SUBSCRIPTIONS;

SELECT
    COUNT_IF(employee_count <= 0)                              AS bad_employee_count,
    COUNT_IF(segment = 'SMB'        AND employee_count >= 200)  AS smb_too_big,
    COUNT_IF(segment = 'Enterprise' AND employee_count < 2000)  AS ent_too_small
FROM ACCOUNTS;


-- =====================================================================
-- STEP 6  Referential integrity: orphaned foreign keys (expect 0 everywhere)
-- =====================================================================
SELECT 'contacts.account_id -> accounts' AS relationship, COUNT(*) AS orphans FROM CONTACTS c LEFT JOIN ACCOUNTS a ON c.account_id = a.account_id WHERE a.account_id IS NULL
UNION ALL SELECT 'accounts.account_owner_id -> sales_reps', COUNT(*) FROM ACCOUNTS a LEFT JOIN SALES_REPS r ON a.account_owner_id = r.sales_rep_id WHERE r.sales_rep_id IS NULL
UNION ALL SELECT 'leads.campaign_id -> campaigns', COUNT(*) FROM LEADS l LEFT JOIN CAMPAIGNS c ON l.campaign_id = c.campaign_id WHERE l.campaign_id IS NOT NULL AND c.campaign_id IS NULL
UNION ALL SELECT 'leads.sales_rep_id -> sales_reps', COUNT(*) FROM LEADS l LEFT JOIN SALES_REPS r ON l.sales_rep_id = r.sales_rep_id WHERE r.sales_rep_id IS NULL
UNION ALL SELECT 'opportunities.account_id -> accounts', COUNT(*) FROM OPPORTUNITIES o LEFT JOIN ACCOUNTS a ON o.account_id = a.account_id WHERE a.account_id IS NULL
UNION ALL SELECT 'opportunities.sales_rep_id -> sales_reps', COUNT(*) FROM OPPORTUNITIES o LEFT JOIN SALES_REPS r ON o.sales_rep_id = r.sales_rep_id WHERE r.sales_rep_id IS NULL
UNION ALL SELECT 'opportunities.campaign_id -> campaigns', COUNT(*) FROM OPPORTUNITIES o LEFT JOIN CAMPAIGNS c ON o.campaign_id = c.campaign_id WHERE c.campaign_id IS NULL
UNION ALL SELECT 'opportunity_history.opportunity_id -> opportunities', COUNT(*) FROM OPPORTUNITY_HISTORY h LEFT JOIN OPPORTUNITIES o ON h.opportunity_id = o.opportunity_id WHERE o.opportunity_id IS NULL
UNION ALL SELECT 'marketing_touches.lead_id -> leads', COUNT(*) FROM MARKETING_TOUCHES m LEFT JOIN LEADS l ON m.lead_id = l.lead_id WHERE m.lead_id IS NOT NULL AND l.lead_id IS NULL
UNION ALL SELECT 'marketing_touches.contact_id -> contacts', COUNT(*) FROM MARKETING_TOUCHES m LEFT JOIN CONTACTS c ON m.contact_id = c.contact_id WHERE m.contact_id IS NOT NULL AND c.contact_id IS NULL
UNION ALL SELECT 'subscriptions.account_id -> accounts', COUNT(*) FROM SUBSCRIPTIONS s LEFT JOIN ACCOUNTS a ON s.account_id = a.account_id WHERE a.account_id IS NULL
UNION ALL SELECT 'invoices.subscription_id -> subscriptions', COUNT(*) FROM INVOICES i LEFT JOIN SUBSCRIPTIONS s ON i.subscription_id = s.subscription_id WHERE s.subscription_id IS NULL
UNION ALL SELECT 'invoices.account_id = subscription.account_id', COUNT(*) FROM INVOICES i JOIN SUBSCRIPTIONS s ON i.subscription_id = s.subscription_id WHERE i.account_id <> s.account_id
UNION ALL SELECT 'support_tickets.account_id -> accounts', COUNT(*) FROM SUPPORT_TICKETS t LEFT JOIN ACCOUNTS a ON t.account_id = a.account_id WHERE a.account_id IS NULL
UNION ALL SELECT 'support_tickets.contact_id belongs to ticket account', COUNT(*) FROM SUPPORT_TICKETS t JOIN CONTACTS c ON t.contact_id = c.contact_id WHERE c.account_id <> t.account_id
UNION ALL SELECT 'website_events.lead_id -> leads', COUNT(*) FROM WEBSITE_EVENTS w LEFT JOIN LEADS l ON w.lead_id = l.lead_id WHERE w.lead_id IS NOT NULL AND l.lead_id IS NULL
UNION ALL SELECT 'website_events.campaign_id -> campaigns', COUNT(*) FROM WEBSITE_EVENTS w LEFT JOIN CAMPAIGNS c ON w.campaign_id = c.campaign_id WHERE w.campaign_id IS NOT NULL AND c.campaign_id IS NULL
ORDER BY orphans DESC;


-- =====================================================================
-- STEP 7  Consistency: columns that must agree with each other
-- =====================================================================
SELECT 'opp stage vs closed flags' AS check_name,
       COUNT_IF( (stage = 'Closed Won'  AND (closed_won_flag <> 1 OR closed_lost_flag <> 0))
              OR (stage = 'Closed Lost' AND (closed_lost_flag <> 1 OR closed_won_flag <> 0))
              OR (stage = 'Closed-Won'  AND closed_won_flag <> 1)
              OR (stage NOT IN ('Closed Won', 'Closed Lost', 'Closed-Won') AND (closed_won_flag + closed_lost_flag) > 0)) AS rows_failing
FROM OPPORTUNITIES
UNION ALL
SELECT 'closed opp without actual_close_date',
       COUNT_IF(stage IN ('Closed Won', 'Closed Lost', 'Closed-Won') AND actual_close_date IS NULL)
FROM OPPORTUNITIES
UNION ALL
SELECT 'open opp with actual_close_date',
       COUNT_IF(stage NOT IN ('Closed Won', 'Closed Lost', 'Closed-Won') AND actual_close_date IS NOT NULL)
FROM OPPORTUNITIES
UNION ALL
SELECT 'subscription status vs end date',
       COUNT_IF((status = 'Cancelled') <> (subscription_end_date IS NOT NULL))
FROM SUBSCRIPTIONS
UNION ALL
SELECT 'subscription churn_flag vs status',
       COUNT_IF((churn_flag = 1) <> (status = 'Cancelled'))
FROM SUBSCRIPTIONS
UNION ALL
SELECT 'lead converted_flag vs lead_status',
       COUNT_IF((converted_flag = 1) <> (lead_status = 'Converted'))
FROM LEADS
UNION ALL
SELECT 'invoice Paid without payment_date / unpaid with payment_date',
       COUNT_IF((payment_status = 'Paid') <> (payment_date IS NOT NULL))
FROM INVOICES
UNION ALL
SELECT 'campaign status Active but already ended',
       COUNT_IF(status = 'Active' AND end_date < '2026-09-01')
FROM CAMPAIGNS
UNION ALL
SELECT 'ticket status vs resolved_at',
       COUNT_IF((status = 'Resolved') <> (resolved_at IS NOT NULL))
FROM SUPPORT_TICKETS
UNION ALL
SELECT 'opp stage differs from last stage in history', COUNT(*)
FROM (
    SELECT opportunity_id, stage AS last_history_stage
    FROM OPPORTUNITY_HISTORY
    QUALIFY ROW_NUMBER() OVER (PARTITION BY opportunity_id ORDER BY stage_sequence DESC) = 1
) h
JOIN OPPORTUNITIES o ON o.opportunity_id = h.opportunity_id
WHERE h.last_history_stage <> o.stage
UNION ALL
SELECT 'website purchase event without revenue / revenue on non-purchase',
       COUNT_IF((event_type = 'purchase') <> (revenue > 0))
FROM WEBSITE_EVENTS
UNION ALL
SELECT 'attributed revenue on Impression touches',
       COUNT_IF(touch_type = 'Impression' AND attributed_revenue > 0)
FROM MARKETING_TOUCHES
ORDER BY rows_failing DESC;


-- =====================================================================
-- STEP 8  Timeliness & temporal logic: events in a sensible order
-- =====================================================================
SELECT 'opportunity created before its account existed' AS check_name, COUNT(*) AS rows_failing
FROM OPPORTUNITIES o JOIN ACCOUNTS a ON o.account_id = a.account_id
WHERE o.created_at < a.created_at
UNION ALL
SELECT 'ticket created before its account existed', COUNT(*)
FROM SUPPORT_TICKETS t JOIN ACCOUNTS a ON t.account_id = a.account_id
WHERE t.created_at < a.created_at
UNION ALL
SELECT 'invoice dated after subscription ended', COUNT(*)
FROM INVOICES i JOIN SUBSCRIPTIONS s ON i.subscription_id = s.subscription_id
WHERE s.subscription_end_date IS NOT NULL AND i.invoice_date > s.subscription_end_date
UNION ALL
SELECT 'invoice dated before subscription started', COUNT(*)
FROM INVOICES i JOIN SUBSCRIPTIONS s ON i.subscription_id = s.subscription_id
WHERE i.invoice_date < s.subscription_start_date
UNION ALL
SELECT 'payment date after data snapshot (future)', COUNT_IF(payment_date > '2026-09-01') FROM INVOICES
UNION ALL
SELECT 'stale pipeline: open opp past expected close', COUNT_IF(stage IN ('Prospecting', 'Discovery', 'Demo', 'Proposal', 'Negotiation') AND expected_close_date < '2026-09-01') FROM OPPORTUNITIES
UNION ALL
SELECT 'history stage exited before entered', COUNT_IF(exited_stage_at < entered_stage_at) FROM OPPORTUNITY_HISTORY
UNION ALL
SELECT 'ticket resolved before created', COUNT_IF(resolved_at < created_at) FROM SUPPORT_TICKETS
UNION ALL
SELECT 'web session spanning more than 1 day', COUNT(*)
FROM (
    SELECT session_id
    FROM WEBSITE_EVENTS
    GROUP BY session_id
    HAVING DATEDIFF('hour', MIN(event_timestamp), MAX(event_timestamp)) > 24
)
ORDER BY rows_failing DESC;

-- date coverage of every table (look for gaps or out-of-window dates)
SELECT 'accounts.created_at' AS column_name, MIN(created_at) AS min_date, MAX(created_at) AS max_date FROM ACCOUNTS
UNION ALL SELECT 'opportunities.created_at', MIN(created_at), MAX(created_at) FROM OPPORTUNITIES
UNION ALL SELECT 'opportunities.expected_close_date', MIN(expected_close_date), MAX(expected_close_date) FROM OPPORTUNITIES
UNION ALL SELECT 'invoices.invoice_date', MIN(invoice_date), MAX(invoice_date) FROM INVOICES
UNION ALL SELECT 'invoices.payment_date', MIN(payment_date), MAX(payment_date) FROM INVOICES
UNION ALL SELECT 'support_tickets.created_at', MIN(created_at), MAX(created_at) FROM SUPPORT_TICKETS
UNION ALL SELECT 'website_events.event_timestamp', MIN(event_timestamp), MAX(event_timestamp) FROM WEBSITE_EVENTS
UNION ALL SELECT 'sales_reps.hire_date', MIN(hire_date), MAX(hire_date) FROM SALES_REPS;


-- =====================================================================
-- STEP 9  Distributions & outliers
-- =====================================================================
-- 9a. deal size distribution by segment
SELECT segment,
       COUNT(*)                                   AS opps,
       ROUND(MIN(amount), 0)                      AS min_amount,
       ROUND(APPROX_PERCENTILE(amount, 0.25), 0)  AS p25,
       ROUND(MEDIAN(amount), 0)                   AS median,
       ROUND(APPROX_PERCENTILE(amount, 0.75), 0)  AS p75,
       ROUND(APPROX_PERCENTILE(amount, 0.99), 0)  AS p99,
       ROUND(MAX(amount), 0)                      AS max_amount,
       ROUND(AVG(amount), 0)                      AS avg_amount,
       ROUND(STDDEV(amount), 0)                   AS stddev_amount
FROM OPPORTUNITIES
GROUP BY segment
ORDER BY median DESC;

-- 9b. IQR outliers per segment (values above Q3 + 1.5 * IQR)
WITH q AS (
    SELECT segment,
           APPROX_PERCENTILE(amount, 0.25) AS q1,
           APPROX_PERCENTILE(amount, 0.75) AS q3
    FROM OPPORTUNITIES
    GROUP BY segment
)
SELECT o.segment,
       COUNT(*)                                              AS opps,
       COUNT_IF(o.amount > q.q3 + 1.5 * (q.q3 - q.q1))       AS high_outliers,
       ROUND(100 * high_outliers / opps, 2)                  AS outlier_pct
FROM OPPORTUNITIES o JOIN q ON q.segment = o.segment
GROUP BY o.segment
ORDER BY o.segment;

-- 9c. monthly volume trend (sudden drops / spikes = pipeline problems)
SELECT DATE_TRUNC('month', created_at) AS month,
       COUNT(*)                         AS opportunities_created,
       ROUND(SUM(amount) / 1e6, 2)      AS pipeline_musd
FROM OPPORTUNITIES
GROUP BY 1
ORDER BY 1;

-- 9d. region vs country plausibility (sample of odd combinations)
SELECT region, country, COUNT(*) AS accounts
FROM ACCOUNTS
WHERE region = 'EMEA'
GROUP BY region, country
ORDER BY accounts DESC
LIMIT 25;


-- =====================================================================
-- STEP 10  Data-quality scorecard (one row per rule, PASS / WARN / FAIL)
-- Saved to a table so you can track results over time.
-- =====================================================================
CREATE TABLE IF NOT EXISTS DQ_RESULTS (
    run_at        TIMESTAMP_NTZ,
    rule_name     VARCHAR,
    dimension     VARCHAR,
    table_name    VARCHAR,
    rows_checked  NUMBER,
    rows_failing  NUMBER,
    fail_pct      NUMBER(6,2),
    status        VARCHAR
);

INSERT INTO DQ_RESULTS
WITH checks AS (
    SELECT 'account_id unique' AS rule_name, 'Uniqueness' AS dimension, 'accounts' AS table_name,
           COUNT(*) AS rows_checked, COUNT(*) - COUNT(DISTINCT account_id) AS rows_failing FROM ACCOUNTS
    UNION ALL SELECT 'opportunity_id unique', 'Uniqueness', 'opportunities', COUNT(*), COUNT(*) - COUNT(DISTINCT opportunity_id) FROM OPPORTUNITIES
    UNION ALL SELECT 'contact email unique', 'Uniqueness', 'contacts', COUNT(*), COUNT(*) - COUNT(DISTINCT email) FROM CONTACTS
    UNION ALL SELECT 'industry not null', 'Completeness', 'accounts', COUNT(*), COUNT_IF(industry IS NULL) FROM ACCOUNTS
    UNION ALL SELECT 'lead_source not null', 'Completeness', 'leads', COUNT(*), COUNT_IF(lead_source IS NULL) FROM LEADS
    UNION ALL SELECT 'region in accepted values', 'Validity', 'accounts', COUNT(*), COUNT_IF(region IS NULL OR region NOT IN ('North America', 'EMEA', 'APAC', 'LATAM')) FROM ACCOUNTS
    UNION ALL SELECT 'stage in accepted values', 'Validity', 'opportunities', COUNT(*), COUNT_IF(stage NOT IN ('Prospecting', 'Discovery', 'Demo', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost')) FROM OPPORTUNITIES
    UNION ALL SELECT 'amount > 0', 'Validity', 'opportunities', COUNT(*), COUNT_IF(amount <= 0) FROM OPPORTUNITIES
    UNION ALL SELECT 'opportunity -> account exists', 'Integrity', 'opportunities', COUNT(*), COUNT_IF(a.account_id IS NULL) FROM OPPORTUNITIES o LEFT JOIN ACCOUNTS a ON o.account_id = a.account_id
    UNION ALL SELECT 'invoice -> subscription exists', 'Integrity', 'invoices', COUNT(*), COUNT_IF(s.subscription_id IS NULL) FROM INVOICES i LEFT JOIN SUBSCRIPTIONS s ON i.subscription_id = s.subscription_id
    UNION ALL SELECT 'closed opp has close date', 'Consistency', 'opportunities', COUNT(*), COUNT_IF(stage IN ('Closed Won', 'Closed Lost', 'Closed-Won') AND actual_close_date IS NULL) FROM OPPORTUNITIES
    UNION ALL SELECT 'opp created after account', 'Timeliness', 'opportunities', COUNT(*), COUNT_IF(o.created_at < a.created_at) FROM OPPORTUNITIES o JOIN ACCOUNTS a ON o.account_id = a.account_id
    UNION ALL SELECT 'invoice not after subscription end', 'Timeliness', 'invoices', COUNT(*), COUNT_IF(s.subscription_end_date IS NOT NULL AND i.invoice_date > s.subscription_end_date) FROM INVOICES i JOIN SUBSCRIPTIONS s ON i.subscription_id = s.subscription_id
    UNION ALL SELECT 'no future payment dates', 'Timeliness', 'invoices', COUNT(*), COUNT_IF(payment_date > '2026-09-01') FROM INVOICES
)
SELECT CURRENT_TIMESTAMP()                                           AS run_at,
       rule_name, dimension, table_name, rows_checked, rows_failing,
       ROUND(100 * rows_failing / NULLIF(rows_checked, 0), 2)        AS fail_pct,
       CASE WHEN rows_failing = 0 THEN 'PASS'
            WHEN rows_failing / NULLIF(rows_checked, 0) < 0.01 THEN 'WARN'
            ELSE 'FAIL' END                                          AS status
FROM checks;

-- latest scorecard
SELECT rule_name, dimension, table_name, rows_checked, rows_failing, fail_pct, status
FROM DQ_RESULTS
WHERE run_at = (SELECT MAX(run_at) FROM DQ_RESULTS)
ORDER BY CASE status WHEN 'FAIL' THEN 1 WHEN 'WARN' THEN 2 ELSE 3 END, dimension, rule_name;
