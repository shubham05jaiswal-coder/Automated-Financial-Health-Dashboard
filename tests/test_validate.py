import pandas as pd
from src.validate import validate_transactions

def test_valid_transaction_is_accepted():
    df = pd.DataFrame([{
        "transaction_id": "T-1", "transaction_date": "2026-01-01",
        "description": "Sale", "category": "Sales", "transaction_type": "revenue",
        "amount": "100.50", "department": "Sales", "payment_method": "Bank",
        "counterparty": "Customer", "currency": "INR",
    }])
    valid, rejected, errors = validate_transactions(df)
    assert not errors
    assert len(valid) == 1
    assert rejected.empty
    assert str(valid.iloc[0]["amount"]) == "100.50"

def test_bad_amount_is_rejected():
    df = pd.DataFrame([{
        "transaction_id": "T-2", "transaction_date": "not-a-date",
        "description": "Bad", "category": "Sales", "transaction_type": "revenue",
        "amount": "abc", "department": "Sales", "payment_method": "Bank",
        "counterparty": "Customer", "currency": "INR",
    }])
    valid, rejected, errors = validate_transactions(df)
    assert valid.empty
    assert len(rejected) == 1
    assert "amount is not numeric" in rejected.iloc[0]["errors"]

def test_duplicate_ids_in_batch_are_rejected():
    row = {
        "transaction_id": "T-3", "transaction_date": "2026-01-01",
        "description": "Sale", "category": "Sales", "transaction_type": "revenue",
        "amount": "100", "department": "Sales", "payment_method": "Bank",
        "counterparty": "Customer", "currency": "INR",
    }
    valid, rejected, errors = validate_transactions(pd.DataFrame([row, row]))
    assert valid.empty
    assert len(rejected) == 2
