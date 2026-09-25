-- ============================================================
-- Reconcile: rows in each staged CSV vs rows loaded in its table.
-- CSV counts exclude the header (CSV_RAW_FF has SKIP_HEADER = 1).
-- ============================================================
USE DATABASE NOVAFLOW;
USE SCHEMA NOVAFLOW_RAW;

WITH csv_counts AS (
    SELECT
        LOWER(REGEXP_REPLACE(SPLIT_PART(METADATA$FILENAME, '/', -1), '\\.csv(\\.gz)?$', '')) AS table_name,
        COUNT(*) AS csv_rows
    FROM @RAW_STAGE (FILE_FORMAT => 'CSV_RAW_FF')
    GROUP BY 1
),
table_counts AS (
              SELECT 'sales_reps'          AS table_name, COUNT(*) AS table_rows FROM SALES_REPS
    UNION ALL SELECT 'accounts',            COUNT(*) FROM ACCOUNTS
    UNION ALL SELECT 'contacts',            COUNT(*) FROM CONTACTS
    UNION ALL SELECT 'campaigns',           COUNT(*) FROM CAMPAIGNS
    UNION ALL SELECT 'leads',               COUNT(*) FROM LEADS
    UNION ALL SELECT 'opportunities',       COUNT(*) FROM OPPORTUNITIES
    UNION ALL SELECT 'opportunity_history', COUNT(*) FROM OPPORTUNITY_HISTORY
    UNION ALL SELECT 'marketing_touches',   COUNT(*) FROM MARKETING_TOUCHES
    UNION ALL SELECT 'subscriptions',       COUNT(*) FROM SUBSCRIPTIONS
    UNION ALL SELECT 'invoices',            COUNT(*) FROM INVOICES
    UNION ALL SELECT 'support_tickets',     COUNT(*) FROM SUPPORT_TICKETS
    UNION ALL SELECT 'website_events',      COUNT(*) FROM WEBSITE_EVENTS
)
SELECT
    COALESCE(c.table_name, t.table_name)          AS table_name,
    c.csv_rows,
    t.table_rows,
    t.table_rows - c.csv_rows                     AS difference,
    IFF(c.csv_rows = t.table_rows, 'MATCH', 'MISMATCH') AS status
FROM csv_counts c
FULL OUTER JOIN table_counts t
    ON c.table_name = t.table_name
ORDER BY status DESC, table_name;
