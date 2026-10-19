import logging
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from src.config import INPUT_DIR, LOG_DIR, MAX_REJECTED_ROWS
from src.db import engine, check_connection
from src.validate import validate_transactions, normalize_frame

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "etl.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("finance_etl")

BUDGET_UPSERT_SQL = text("""
INSERT INTO public.monthly_budgets
(month_start, department, category, budget_type, budget_amount, currency)
VALUES (:month_start, :department, :category, :budget_type, :budget_amount, :currency)
ON CONFLICT (month_start, department, category, budget_type, currency)
DO UPDATE SET budget_amount = EXCLUDED.budget_amount
""")

UPSERT_SQL = text("""
INSERT INTO public.financial_transactions
(transaction_id, transaction_date, description, category, transaction_type,
 amount, department, payment_method, counterparty, currency, source_file, updated_at)
VALUES
(:transaction_id, :transaction_date, :description, :category, :transaction_type,
 :amount, :department, :payment_method, :counterparty, :currency, :source_file, NOW())
ON CONFLICT (transaction_id) DO UPDATE SET
 transaction_date = EXCLUDED.transaction_date,
 description = EXCLUDED.description,
 category = EXCLUDED.category,
 transaction_type = EXCLUDED.transaction_type,
 amount = EXCLUDED.amount,
 department = EXCLUDED.department,
 payment_method = EXCLUDED.payment_method,
 counterparty = EXCLUDED.counterparty,
 currency = EXCLUDED.currency,
 source_file = EXCLUDED.source_file,
 updated_at = NOW()
""")

def read_source(path: Path):
    if path.suffix.lower() == ".csv":
        return [("csv", pd.read_csv(path, dtype=str, keep_default_na=False))]
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        workbook = pd.ExcelFile(path)
        return [(sheet, pd.read_excel(path, sheet_name=sheet, dtype=str, keep_default_na=False))
                for sheet in workbook.sheet_names]
    return []

def record_run(conn, *, source_file, started_at, status, rows_read, rows_loaded, rows_rejected, error_message=None):
    conn.execute(text("""
        INSERT INTO public.etl_runs
        (source_file, started_at, finished_at, status, rows_read, rows_loaded, rows_rejected, error_message)
        VALUES (:source_file, :started_at, :finished_at, :status, :rows_read, :rows_loaded, :rows_rejected, :error_message)
    """), {
        "source_file": source_file,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc),
        "status": status,
        "rows_read": rows_read,
        "rows_loaded": rows_loaded,
        "rows_rejected": rows_rejected,
        "error_message": error_message,
    })

def process_file(path: Path):
    started = datetime.now(timezone.utc)
    rows_read = rows_loaded = rows_rejected = 0
    rejected_frames = []
    try:
        sheets = read_source(path)
        if not sheets:
            logger.info("Skipping unsupported file %s", path.name)
            return
        valid_frames = []
        budget_frames = []
        for sheet_name, raw in sheets:
            normalized = normalize_frame(raw)
            budget_columns = {"month_start", "department", "category", "budget_type", "budget_amount", "currency"}
            if budget_columns.issubset(set(normalized.columns)):
                budget = normalized[list(budget_columns)].copy()
                budget["month_start"] = pd.to_datetime(budget["month_start"], errors="coerce").dt.date
                budget["budget_type"] = budget["budget_type"].astype(str).str.strip().str.lower()
                budget["currency"] = budget["currency"].astype(str).str.strip().str.upper()
                budget["department"] = budget["department"].astype(str).str.strip().replace("", "Unassigned")
                budget["category"] = budget["category"].astype(str).str.strip()
                budget["budget_amount"] = pd.to_numeric(budget["budget_amount"].astype(str).str.replace(",", "", regex=False), errors="coerce")
                valid_budget = budget[
                    budget["month_start"].notna()
                    & budget["department"].ne("")
                    & budget["category"].ne("")
                    & budget["budget_type"].isin(["revenue", "expense"])
                    & budget["budget_amount"].notna()
                    & budget["budget_amount"].ge(0)
                    & budget["currency"].str.fullmatch(r"[A-Z]{3}", na=False)
                ].copy()
                if len(valid_budget) != len(budget):
                    logger.warning("Some budget rows in %s / %s failed validation", path.name, sheet_name)
                if not valid_budget.empty:
                    budget_frames.append(valid_budget.to_dict(orient="records"))
                # A budget sheet is a supported source, not a transaction sheet.
                continue
            valid, rejected, structural_errors = validate_transactions(raw)
            if structural_errors:
                logger.info("Skipping %s / %s: %s", path.name, sheet_name, "; ".join(structural_errors))
                continue
            rows_read += len(raw)
            rows_loaded += len(valid)
            rows_rejected += len(rejected)
            if not valid.empty:
                valid = valid.copy()
                valid["source_file"] = f"{path.name}:{sheet_name}"
                valid_frames.append(valid)
            if not rejected.empty:
                rejected["source_file"] = f"{path.name}:{sheet_name}"
                rejected_frames.append(rejected)

        if rows_read == 0 and not budget_frames:
            logger.info("No supported transaction or budget sheets in %s; no load performed", path.name)
            return
        if rows_rejected > MAX_REJECTED_ROWS:
            raise ValueError(f"Rejected {rows_rejected} rows, exceeding MAX_REJECTED_ROWS={MAX_REJECTED_ROWS}")

        # One transaction per source file: data and run status commit together.
        with engine.begin() as conn:
            for frame in valid_frames:
                records = frame.to_dict(orient="records")
                conn.execute(UPSERT_SQL, records)
            for budget_records in budget_frames:
                conn.execute(BUDGET_UPSERT_SQL, budget_records)
            record_run(
                conn, source_file=path.name, started_at=started, status="success",
                rows_read=rows_read, rows_loaded=rows_loaded, rows_rejected=rows_rejected,
            )
        if rejected_frames:
            rejected_path = LOG_DIR / f"rejected_rows_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{path.stem}.csv"
            pd.concat(rejected_frames, ignore_index=True).to_csv(rejected_path, index=False)
            logger.warning("%s rejected rows written to %s", rows_rejected, rejected_path)
        logger.info("Loaded %s: transactions_read=%s transactions_loaded=%s rejected=%s budget_rows=%s", path.name, rows_read, rows_loaded, rows_rejected, sum(len(x) for x in budget_frames))
    except Exception as exc:
        logger.exception("ETL failed for %s", path.name)
        try:
            with engine.begin() as conn:
                record_run(
                    conn, source_file=path.name, started_at=started, status="failed",
                    rows_read=rows_read, rows_loaded=0, rows_rejected=rows_rejected,
                    error_message=str(exc)[:4000],
                )
        except Exception:
            logger.exception("Could not record failed ETL run for %s", path.name)
        raise

def main():
    check_connection()
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in INPUT_DIR.iterdir() if p.suffix.lower() in {".csv", ".xlsx", ".xlsm"} and not p.name.startswith("~$")])
    if not files:
        logger.warning("No CSV/XLSX/XLSM files found in %s", INPUT_DIR)
        return
    failures = []
    for path in files:
        try:
            process_file(path)
        except Exception as exc:
            failures.append((path.name, str(exc)))
    if failures:
        raise RuntimeError(f"{len(failures)} source file(s) failed: {failures}")

if __name__ == "__main__":
    main()
