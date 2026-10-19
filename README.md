# Automated Financial Health Dashboard

Production-style starter project using **Python + PostgreSQL + Power BI**. It ingests Excel/CSV finance data, validates and normalizes it, loads it idempotently into PostgreSQL, records ETL run metrics, and provides SQL views for reporting.

> This is a portfolio starter, not an accounting system. Validate recognition rules, tax treatment, and cash-flow classifications with your finance team before using real business data.

## Architecture

`Excel/CSV files → Python ETL → PostgreSQL staging/upsert → reporting views → Power BI`

## Project tree

```text
financial_health_dashboard/
├── data/
│   ├── input/                 # Drop .csv/.xlsx/.xlsm files here
│   └── archive/               # Optional manually managed archive
├── logs/
├── powerbi/
│   └── DAX_MEASURES.md
├── sql/
│   ├── 01_schema.sql
│   └── 02_reporting_views.sql
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── etl.py
│   └── validate.py
├── tests/
│   └── test_validate.py
├── .env.example
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 1. Prerequisites

- Python 3.10+
- Docker Desktop (recommended) or PostgreSQL 14+
- Power BI Desktop (Windows) for the report layer

## 2. Start PostgreSQL with Docker

From this project folder:

```powershell
docker compose up -d
```

The local database is exposed on port `5432`. Change the demo credentials in `docker-compose.yml` before using this outside a local development machine.

## 3. Set up Python

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and run commands with `.\.venv\Scripts\python.exe`.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` to match your PostgreSQL connection.

## 4. Create database objects

```powershell
psql "postgresql://finance_app:change_me_local_only@localhost:5432/finance_dashboard" -f sql/01_schema.sql
psql "postgresql://finance_app:change_me_local_only@localhost:5432/finance_dashboard" -f sql/02_reporting_views.sql
```

Alternatively, open each SQL file in pgAdmin Query Tool and execute it against `finance_dashboard`.

## 5. Run the ETL

Sample files are included in `data/input/`:
- `sample_transactions.csv`
- `sample_budget.xlsx`

Run:

```powershell
python -m src.etl
```

The pipeline:
1. Scans `data/input` for CSV, XLSX and XLSM files.
2. Normalizes column names and supported aliases.
3. Validates required fields, dates, numeric amounts, categories and transaction types.
4. Rejects invalid rows and writes a rejected-row CSV to `logs/`.
5. Uses a database transaction to upsert valid rows by `transaction_id`.
6. Records row counts and status in `etl_runs`.
7. Logs operational details to console and `logs/etl.log`.

**Excel budget support:** Excel sheets with `month_start, department, category, budget_type, budget_amount, currency` are validated and upserted into `monthly_budgets`. Transaction-shaped CSV/Excel sheets use the transaction contract above. Unsupported sheets are skipped. Budget rows that fail validation are logged as warnings; extend the rejected-row audit if you need row-level budget rejection files.

## 6. Input file contract

Required transaction columns (case-insensitive; spaces and punctuation are normalized):

| Column | Type | Example |
|---|---|---|
| `transaction_id` | string | `TXN-1001` |
| `transaction_date` | date | `2026-01-05` |
| `description` | string | `Product sale` |
| `category` | string | `Sales` |
| `transaction_type` | `revenue` / `expense` / `cash_in` / `cash_out` | `revenue` |
| `amount` | decimal, non-negative | `125000.00` |
| `department` | string | `Sales` |
| `payment_method` | string | `Bank Transfer` |
| `counterparty` | string | `Customer A` |
| `currency` | ISO-like code | `INR` |

`transaction_id` is the idempotency key. Keep it stable across re-runs. A repeated ID updates the matching record instead of creating a duplicate. Amounts are stored as positive values; `transaction_type` determines how they are interpreted. `revenue` and `expense` support profit reporting; `cash_in` and `cash_out` support cash-flow reporting. If a transaction affects both profit and cash, your source model should define separate accounting and cash movement records to avoid double counting.

## 7. Reporting views

- `reporting.vw_monthly_financials` — revenue, expenses, net profit, margins, cash inflow/outflow and net cash flow by month.
- `reporting.vw_expense_by_category` — expenses by month/category/department.
- `reporting.vw_transaction_detail` — cleaned transaction detail for Power BI.
- `reporting.vw_monthly_budget` — view scaffold for monthly budget data (requires the optional budget table/load described in SQL comments).

## 8. Connect Power BI

1. Open Power BI Desktop → **Get data** → **PostgreSQL database**.
2. Server: `localhost:5432`; Database: `finance_dashboard`.
3. Choose Import mode for a simple portfolio report, or DirectQuery if near-live querying is required and you understand its performance tradeoffs.
4. Select the `reporting` schema views.
5. Add measures from `powerbi/DAX_MEASURES.md`.
6. Suggested pages: Executive Overview, Revenue & Profitability, Expense Analysis, Cash Flow, Transaction Detail.
7. Use `month_start` as the date axis. Add slicers for department, category, and transaction type.

For scheduled refresh in the Power BI Service, configure a supported gateway and credentials. A local PostgreSQL instance is not directly reachable by the cloud service without appropriate network/gateway configuration.

## 9. Schedule the ETL (Windows Task Scheduler)

Use Task Scheduler → Create Basic Task:
- Trigger: daily at 6:00 AM (choose a time appropriate for your source feeds)
- Action: Start a program
- Program: full path to `.venv\Scripts\python.exe`
- Arguments: `-m src.etl`
- Start in: full project folder path

Test the exact command manually first. Ensure the task account can read input files, write logs, and reach PostgreSQL.

## 10. Production hardening checklist

Before production:
- Move credentials to a secrets manager; do not commit `.env`.
- Use a least-privilege PostgreSQL role and TLS for remote connections.
- Add source-specific contracts, reconciliation totals, and duplicate/late-arriving data rules.
- Add alerting on failed runs and rejected-row thresholds.
- Define retention, backups, restore tests, and access controls.
- Add automated tests and CI.
- Add row-level budget rejection auditing and reconciliation if budget data is business-critical.
- Use a controlled archive/processed-file strategy with source hashes; do not move source files until the database transaction has committed.
- Confirm accounting policy for refunds, credit notes, tax, accruals, and cash movement.

## Troubleshooting

- `psql` not found: run SQL in pgAdmin, or install PostgreSQL command-line tools.
- Connection refused: check `docker compose ps`, port 5432, `.env`, and firewall.
- No rows loaded: ensure transaction columns match the input contract; non-transaction workbooks are skipped.
- Invalid rows: inspect the newest `logs/rejected_rows_*.csv`.
- Duplicate rows: IDs are upserted by `transaction_id`; do not generate a new ID on every run.

## Important notes
- The project includes runnable ETL and SQL source code, sample data, and Power BI measure definitions. It does not include a prebuilt .pbix dashboard file.
- The sample credentials are for local development only. Change them before using real financial data.
- Before production deployment, add alert notifications, budget-row rejection auditing, database backups, and a tested recovery procedure.
