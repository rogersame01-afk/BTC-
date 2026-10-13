# TrustOps 360 — Vanta-style Senior Analytics Engineer Interview Project

Synthetic SaaS security/compliance product analytics case study.
All entities and metrics are fictitious. **Not Vanta data and not a representation of Vanta's internal architecture.**

## Project objectives
Create a reusable warehouse model for product engagement, compliance readiness, invoices and
account health. Demonstrate software engineering discipline: version control, data contracts,
tests, repeatable deployment, incremental updates, privacy, analytical consumption and documentation.

## Source data
All 8 clean CSVs in `data/raw/` share `account_id`; 9th quarantine CSV intentionally contains a
missing account and a repeated event id. Files contain **synthetic, non-real `.invalid` email addresses**.

| File | Grain | Rows |
|---|---|---:|
| crm_accounts.csv | account | 480 |
| product_users.csv | user | 5602 |
| product_events.csv | event | 35620 |
| compliance_controls.csv | control | 6256 |
| compliance_evidence.csv | evidence | 8339 |
| audit_engagements.csv | audit | 480 |
| billing_subscriptions.csv | subscription | 480 |
| billing_invoices.csv | invoice | 2400 |

## Day 1: work through in order

### 1. Business analysis (30–45m)
Read `docs/metric_contract.md`. Write stakeholder interviews as *simulations*, not as completed real
interviews. Product asks for active days, Compliance asks for control pass rate, CS asks for
readiness, Finance owns active MRR, Security approves analytical access.

**Contract**: account_id conformed across systems; event_id unique in normal product feed; all
dates UTC; CSV timestamps ISO-ish without timezone; reporting cut September 2026.
Source system changes would require contract discussion and version control.

### 2. Create warehouse and load files (60–90m)
In Snowflake, choose a warehouse with suitable usage controls (e.g. X-Small, auto-suspend).
Run `snowflake/01_bootstrap_and_load.sql` through stage creation.
Upload the **eight clean CSV files** to `@VANTA_LAB.RAW_PRODUCT.UPLOAD_STAGE` using
Snowsight stage upload, or SnowSQL PUT. Stage upload filenames should be preserved.

Then run the 8 COPY commands at the end of the script. Each RAW table intentionally stores all
CSV fields as VARCHAR: schema-on-read casts in staging and reduces brittleness for source formats.
For production, use landing ingestion audit columns, rejected-row quarantine and least-privilege roles.

**Check**:
```sql
select count(*) from VANTA_LAB.RAW_PRODUCT.PRODUCT_EVENTS;
select count(*) from VANTA_LAB.RAW_CRM.CRM_ACCOUNTS;
```
Expected 35620 and 480 respectively.

**Important**: `COPY INTO` can remember loaded file metadata; don't assume rerunning loads appends data.
To demonstrate a malformed record, use the separate quarantine file in a dedicated sandbox copy,
not the baseline product events table.

### 3. Create dbt Cloud project (30m)
Create GitHub repository `trustops-360-analytics` and upload these files.
In dbt Cloud, create a Snowflake connection to VANTA_LAB, add Git repo, configure
a **development environment** and an isolated **production environment**.
Grant the dbt role read permissions on RAW_* and create permissions on its output schemas.
Because a custom `+schema` is used, dbt's *default* schema macro normally generates
`<target_schema>_STAGING`, `<target_schema>_INTERMEDIATE`, and `<target_schema>_MARTS`.
Do not assume it writes to bare `VANTA_LAB.MARTS`. Identify actual schema in build artifacts.

Commands in dbt Cloud IDE:
```bash
dbt deps
dbt parse
dbt build --select stg_accounts stg_product_events stg_controls stg_evidence stg_subscriptions stg_invoices
dbt build
```
Do not run source freshness as a production SLA test on this historical synthetic dataset:
its ingested_at ends in 2026 and the simulated freshness expectation will naturally age.

### 4. Trace the DAG and grains (60–90m)
- `stg_*`: names, casts, PII handling, normalization; one row per original entity.
- `int_control_health`: one row per account, roll up control health.
- `int_evidence_health`: one row per account, evidence debt.
- `dim_accounts`: one row per account, deterministic surrogate key.
- `fct_product_events`: one row per event, incremental MERGE.
- `fct_invoices`: one row per invoice.
- `mart_account_health`: one row per account with controlled metric aggregation.

**Why aggregate before joins?** Joining invoices to raw events can multiply invoice amounts
by number of events. Each CTE collapses each fact to account grain before joining.

### 5. Validate the mart (45m)
Run `dbt test` and check MART_ACCOUNT_HEALTH count: expected 480.
Investigate any failures rather than deleting assertions.
Use Snowflake query worksheet:
```sql
select health_tier, count(*) account_count, sum(active_mrr) active_mrr
from <YOUR_ACTUAL_DBT_MART_SCHEMA>.MART_ACCOUNT_HEALTH
group by 1;
```
Use exact relation generated in dbt.

## Day 2: reliability, performance, governance

### 6. Incremental demonstration (60–90m)
With `fct_product_events` already built, add one VALID account event to RAW_PRODUCT.PRODUCT_EVENTS:
```sql
insert into VANTA_LAB.RAW_PRODUCT.PRODUCT_EVENTS
values('EVTNEW0001','ACC00001','api','automation_run',
       '2026-09-29 11:00:00','2026-09-30 12:00:00','USR0000001');
```
Then run `dbt build --select +fct_product_events` followed by:
```sql
select * from <YOUR_ACTUAL_DBT_MART_SCHEMA>.FCT_PRODUCT_EVENTS
where event_id='EVTNEW0001';
```
Run again: event count must not grow; the MERGE is idempotent.
The incremental filter uses a **10-day ingestion-time lookback**, not event time.
Because staging is a view, filtering may push down during Snowflake execution: check Query Profile.
**Important**: The cutoff advances as `max(ingested_at)` advances; the example event's
ingestion time is within 10 days of the synthetic dataset maximum (Oct 8, 2026).
For an event outside the lookback or a late correction to an older event, demonstrate
the limitation and discuss CDC/full-refresh fallback. Do not invent production SLA claims.

### 7. Reconciliation and quarantine (45–60m)
- Execute `dbt test --select assert_invoice_reconciliation`.
- Compare invoice totals before and after transformation.
- In an ISOLATED raw sandbox table, append `quarantine_example.csv` and demonstrate
  unique `event_id` and account foreign-key failures; don't contaminate the baseline data.
- Document issue, severity, customer impact, root cause, producer team, mitigation, owner,
  and resolution in `docs/incident_template.md` (add your completed account of the experiment).

### 8. Historical changes via dbt snapshot (30m)
Run `dbt snapshot --select accounts_snapshot`.
Update an account with a newer `updated_at` and a changed `plan`, rerun the snapshot.
Query `dbt_valid_from`, `dbt_valid_to` for a two-version account.
Keep plan history separate from the current account dimension. In reality,
business-effective vs source-observed time must be established with Finance.

### 9. Security and anonymization (45m)
RAW contains owner emails; staging contains only an email hash.
Review what should be visible to Product vs CS vs Finance.
Do not grant RAW to the general BI consumer role.
For a real implementation, plain SHA-256 is insufficient for sensitive low-entropy values.
Design keyed HMAC tokenization, Snowflake masking policies, access roles, retention and query audit.

### 10. Metric contract / semantic enablement (45m)
Review `docs/metric_contract.md`. Use approved definitions and dimensions to avoid bespoke SQL.
`docs/account_health_semantic_optional.yml` is **illustrative**: its compatibility and naming
must be validated against your particular dbt Cloud Semantic Layer / MetricFlow version.
It's deliberately NOT loaded as an active model because support depends on account setup.

Sample governed request:
"Give active MRR and at-risk customer counts by segment for the Sep 2026 health snapshot."
Use approved mart and dimension names; log generated SQL, test it, and reject unapproved
columns. This is a defensible AI-readiness prototype, not a deployed LLM service.

### 11. Performance (45m)
Use the query profile for `fct_product_events` and `mart_account_health`, record:
bytes scanned, partitions pruned, duration, rows returned and warehouse credits.
Test at least two strategies, e.g. scanning raw events per request vs mart consumption.
At ~35,620 events, any timing difference can be noisy; discuss how you'd test at billions
using representative data and cost constraints. Avoid unsupported claims of optimization.

### 12. GitHub engineering process (30m)
Feature branch `feature/account-health-mart`; PR includes changed SQL, YAML schema,
test output screenshot, grain definition, query profile, sample output and rollback notes.
Codex: generate first draft / review SQL. Claude Code: review fanout, idempotency,
privacy and test coverage. YOU own validation and commit reviewed work.

## Interview deliverables / proof
- dbt DAG showing layers and tests
- successful dbt build and separate assertions
- query result: health_tier, count, active_mrr
- a failed test + root cause + fix
- event incremental MERGE and idempotency
- snapshot history with two versions
- metric contract; security tradeoff; query profile measurement
- `docs/interview_walkthrough.md` rehearsal notes

## Known limitations worth mentioning
- Synthetic account behavior isn't designed to be statistically predictive of churn.
- Reporting snapshot dates are fixed, not production rolling windows.
- Latest control state, late corrections, audit event-time as-of joins, billing reversals,
  account mergers and multiple subscriptions need separate handling for real production.
- Some dataset fields are intentionally unused, modeling the scope of an incremental migration.
- No real Fivetran, Airflow, frontend, AI agent or data science model is deployed.
