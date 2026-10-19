import re
from decimal import Decimal, InvalidOperation
import pandas as pd

REQUIRED = [
    "transaction_id", "transaction_date", "description", "category",
    "transaction_type", "amount", "department", "payment_method",
    "counterparty", "currency",
]
ALIASES = {
    "id": "transaction_id", "txn_id": "transaction_id", "date": "transaction_date",
    "type": "transaction_type", "value": "amount", "cost_center": "department",
    "payment": "payment_method", "vendor_customer": "counterparty",
}
ALLOWED_TYPES = {"revenue", "expense", "cash_in", "cash_out"}

def normalize_column(name):
    value = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    return ALIASES.get(value, value)

def normalize_frame(df):
    df = df.copy()
    df.columns = [normalize_column(c) for c in df.columns]
    # Keep the first occurrence if a source has duplicate normalized names.
    df = df.loc[:, ~df.columns.duplicated()]
    return df

def validate_transactions(df):
    df = normalize_frame(df)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return pd.DataFrame(), pd.DataFrame(), [f"Missing required columns: {', '.join(missing)}"]

    accepted, rejected = [], []
    for idx, row in df.iterrows():
        errors = []
        txn_id = "" if pd.isna(row["transaction_id"]) else str(row["transaction_id"]).strip()
        description = "" if pd.isna(row["description"]) else str(row["description"]).strip()
        category = "" if pd.isna(row["category"]) else str(row["category"]).strip()
        department = "" if pd.isna(row["department"]) else str(row["department"]).strip()
        payment_method = "" if pd.isna(row["payment_method"]) else str(row["payment_method"]).strip()
        counterparty = "" if pd.isna(row["counterparty"]) else str(row["counterparty"]).strip()
        currency = "" if pd.isna(row["currency"]) else str(row["currency"]).strip().upper()
        txn_type = "" if pd.isna(row["transaction_type"]) else str(row["transaction_type"]).strip().lower()

        if not txn_id:
            errors.append("transaction_id is blank")
        if not description:
            errors.append("description is blank")
        if not category:
            errors.append("category is blank")
        if txn_type not in ALLOWED_TYPES:
            errors.append(f"transaction_type must be one of {sorted(ALLOWED_TYPES)}")
        if not currency or len(currency) != 3 or not currency.isalpha():
            errors.append("currency must be a 3-letter code")

        try:
            txn_date = pd.to_datetime(row["transaction_date"], errors="raise").date()
        except Exception:
            txn_date = None
            errors.append("transaction_date is not a valid date")

        try:
            amount = Decimal(str(row["amount"]).replace(",", "").strip())
            if not amount.is_finite() or amount < 0:
                errors.append("amount must be a finite non-negative number")
        except (InvalidOperation, ValueError, AttributeError):
            amount = None
            errors.append("amount is not numeric")

        if errors:
            rejected.append({
                "source_row": int(idx) + 2,
                "transaction_id": txn_id,
                "errors": "; ".join(errors),
                **{k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()},
            })
        else:
            accepted.append({
                "transaction_id": txn_id,
                "transaction_date": txn_date,
                "description": description,
                "category": category,
                "transaction_type": txn_type,
                "amount": amount,
                "department": department or "Unassigned",
                "payment_method": payment_method or "Unknown",
                "counterparty": counterparty or "Unknown",
                "currency": currency,
            })

    good = pd.DataFrame(accepted, columns=REQUIRED)
    bad = pd.DataFrame(rejected)
    # Reject duplicate IDs within the same batch; otherwise order would decide the winner.
    if not good.empty:
        dup_mask = good["transaction_id"].duplicated(keep=False)
        if dup_mask.any():
            duplicate_rows = good.loc[dup_mask].copy()
            duplicate_rows["source_row"] = duplicate_rows.index + 2
            duplicate_rows["errors"] = "duplicate transaction_id within input batch"
            bad = pd.concat([bad, duplicate_rows], ignore_index=True, sort=False)
            good = good.loc[~dup_mask].copy()
    return good, bad, []
