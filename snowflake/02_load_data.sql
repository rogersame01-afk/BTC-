-- ============================================================
-- Upload the local CSVs to the stage and COPY them into tables.
-- Run with Snowflake CLI, passing the folder that holds the CSVs:
--   snow sql -f snowflake/02_load_data.sql -D "raw_dir=C:/path/to/data/raw"
-- Use forward slashes in the path, even on Windows.
-- ============================================================
USE DATABASE NOVAFLOW;
USE SCHEMA NOVAFLOW_SALES_OPPS;

-- 1) upload (files are gzip-compressed automatically -> <name>.csv.gz)
PUT 'file://<% raw_dir %>/*.csv' @RAW_STAGE AUTO_COMPRESS = TRUE OVERWRITE = TRUE PARALLEL = 8;

LIST @RAW_STAGE;

-- 2) load (tables are emptied first so the script can be re-run)
TRUNCATE TABLE SALES_REPS;          COPY INTO SALES_REPS          FROM @RAW_STAGE/sales_reps.csv.gz          FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE ACCOUNTS;            COPY INTO ACCOUNTS            FROM @RAW_STAGE/accounts.csv.gz            FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE CONTACTS;            COPY INTO CONTACTS            FROM @RAW_STAGE/contacts.csv.gz            FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE CAMPAIGNS;           COPY INTO CAMPAIGNS           FROM @RAW_STAGE/campaigns.csv.gz           FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE LEADS;               COPY INTO LEADS               FROM @RAW_STAGE/leads.csv.gz               FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE OPPORTUNITIES;       COPY INTO OPPORTUNITIES       FROM @RAW_STAGE/opportunities.csv.gz       FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE OPPORTUNITY_HISTORY; COPY INTO OPPORTUNITY_HISTORY FROM @RAW_STAGE/opportunity_history.csv.gz FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE MARKETING_TOUCHES;   COPY INTO MARKETING_TOUCHES   FROM @RAW_STAGE/marketing_touches.csv.gz   FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE SUBSCRIPTIONS;       COPY INTO SUBSCRIPTIONS       FROM @RAW_STAGE/subscriptions.csv.gz       FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE INVOICES;            COPY INTO INVOICES            FROM @RAW_STAGE/invoices.csv.gz            FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE SUPPORT_TICKETS;     COPY INTO SUPPORT_TICKETS     FROM @RAW_STAGE/support_tickets.csv.gz     FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;
TRUNCATE TABLE WEBSITE_EVENTS;      COPY INTO WEBSITE_EVENTS      FROM @RAW_STAGE/website_events.csv.gz      FILE_FORMAT = (FORMAT_NAME = CSV_RAW_FF) FORCE = TRUE;

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
