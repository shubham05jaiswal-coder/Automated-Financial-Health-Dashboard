CREATE SCHEMA IF NOT EXISTS reporting;

CREATE TABLE IF NOT EXISTS public.financial_transactions (
    transaction_id   TEXT PRIMARY KEY,
    transaction_date DATE NOT NULL,
    description      TEXT NOT NULL,
    category         TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('revenue','expense','cash_in','cash_out')),
    amount           NUMERIC(18,2) NOT NULL CHECK (amount >= 0),
    department       TEXT NOT NULL DEFAULT 'Unassigned',
    payment_method   TEXT NOT NULL DEFAULT 'Unknown',
    counterparty     TEXT NOT NULL DEFAULT 'Unknown',
    currency         CHAR(3) NOT NULL,
    source_file      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_financial_transactions_date
    ON public.financial_transactions (transaction_date);
CREATE INDEX IF NOT EXISTS ix_financial_transactions_category_date
    ON public.financial_transactions (category, transaction_date);
CREATE INDEX IF NOT EXISTS ix_financial_transactions_department_date
    ON public.financial_transactions (department, transaction_date);

CREATE TABLE IF NOT EXISTS public.etl_runs (
    etl_run_id    BIGSERIAL PRIMARY KEY,
    source_file   TEXT NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status        TEXT NOT NULL CHECK (status IN ('success','failed')),
    rows_read     INTEGER NOT NULL DEFAULT 0,
    rows_loaded   INTEGER NOT NULL DEFAULT 0,
    rows_rejected INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

-- Optional budget ingestion table for future actual-vs-budget analysis.
CREATE TABLE IF NOT EXISTS public.monthly_budgets (
    budget_id  BIGSERIAL PRIMARY KEY,
    month_start DATE NOT NULL,
    department TEXT NOT NULL,
    category   TEXT NOT NULL,
    budget_type TEXT NOT NULL CHECK (budget_type IN ('revenue','expense')),
    budget_amount NUMERIC(18,2) NOT NULL CHECK (budget_amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    UNIQUE (month_start, department, category, budget_type, currency)
);
