# NovaFlow Analytics

An analytics-engineering sandbox built around **NovaFlow**, a fictional B2B SaaS analytics company.

- [`data_generator/`](data_generator/README.md): Phase 1. A Python + Faker generator for a realistic,
  relationally consistent CRM / marketing / billing / support dataset (100k customers, ~300k
  opportunities, ~1M web events, ~500k sales activities, ~226k payments, ~50k support tickets).
- [`BTC/`](BTC/): dbt project that will model the raw data.

```bash
pip install -r data_generator/requirements.txt
python data_generator/generate.py      # writes data/raw/*.csv
python data_generator/validate.py
```
