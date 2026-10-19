CREATE OR REPLACE VIEW reporting.vw_monthly_financials AS
SELECT
    DATE_TRUNC('month', transaction_date)::date AS month_start,
    currency,
    SUM(amount) FILTER (WHERE transaction_type = 'revenue') AS revenue,
    SUM(amount) FILTER (WHERE transaction_type = 'expense') AS expenses,
    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'revenue'), 0)
      - COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'expense'), 0) AS net_profit,
    CASE
      WHEN COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'revenue'), 0) = 0 THEN NULL
      ELSE (
        COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'revenue'), 0)
        - COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'expense'), 0)
      ) / NULLIF(SUM(amount) FILTER (WHERE transaction_type = 'revenue'), 0) * 100
    END AS net_profit_margin_pct,
    SUM(amount) FILTER (WHERE transaction_type = 'cash_in') AS cash_inflow,
    SUM(amount) FILTER (WHERE transaction_type = 'cash_out') AS cash_outflow,
    COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'cash_in'), 0)
      - COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'cash_out'), 0) AS net_cash_flow
FROM public.financial_transactions
GROUP BY DATE_TRUNC('month', transaction_date)::date, currency;

CREATE OR REPLACE VIEW reporting.vw_expense_by_category AS
SELECT
    DATE_TRUNC('month', transaction_date)::date AS month_start,
    currency,
    category,
    department,
    SUM(amount) AS expenses
FROM public.financial_transactions
WHERE transaction_type = 'expense'
GROUP BY DATE_TRUNC('month', transaction_date)::date, currency, category, department;

CREATE OR REPLACE VIEW reporting.vw_transaction_detail AS
SELECT
    transaction_id, transaction_date, DATE_TRUNC('month', transaction_date)::date AS month_start,
    description, category, transaction_type, amount, department, payment_method,
    counterparty, currency, source_file, created_at, updated_at
FROM public.financial_transactions;

CREATE OR REPLACE VIEW reporting.vw_monthly_budget AS
SELECT
    month_start, department, category, budget_type, currency,
    SUM(budget_amount) AS budget_amount
FROM public.monthly_budgets
GROUP BY month_start, department, category, budget_type, currency;

-- Operational monitoring view
CREATE OR REPLACE VIEW reporting.vw_etl_run_summary AS
SELECT etl_run_id, source_file, started_at, finished_at, status,
       rows_read, rows_loaded, rows_rejected, error_message
FROM public.etl_runs;
