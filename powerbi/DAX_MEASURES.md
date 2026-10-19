# Power BI measures

Create these measures after loading `reporting.vw_transaction_detail` as `Transactions`.
If using the monthly SQL view, adapt table/column names accordingly. Set `amount` data type to Fixed decimal number and `transaction_date` to Date.

```DAX
Total Revenue =
CALCULATE(
    SUM(Transactions[amount]),
    Transactions[transaction_type] = "revenue"
)

Total Expenses =
CALCULATE(
    SUM(Transactions[amount]),
    Transactions[transaction_type] = "expense"
)

Net Profit =
[Total Revenue] - [Total Expenses]

Net Profit Margin % =
DIVIDE([Net Profit], [Total Revenue])

Cash Inflow =
CALCULATE(
    SUM(Transactions[amount]),
    Transactions[transaction_type] = "cash_in"
)

Cash Outflow =
CALCULATE(
    SUM(Transactions[amount]),
    Transactions[transaction_type] = "cash_out"
)

Net Cash Flow =
[Cash Inflow] - [Cash Outflow]

Transaction Count =
DISTINCTCOUNT(Transactions[transaction_id])

Revenue Previous Month =
CALCULATE(
    [Total Revenue],
    DATEADD('Calendar'[Date], -1, MONTH)
)

Revenue MoM % =
DIVIDE(
    [Total Revenue] - [Revenue Previous Month],
    [Revenue Previous Month]
)

Expenses Previous Month =
CALCULATE(
    [Total Expenses],
    DATEADD('Calendar'[Date], -1, MONTH)
)

Expenses MoM % =
DIVIDE(
    [Total Expenses] - [Expenses Previous Month],
    [Expenses Previous Month]
)
```

## Calendar table

Create a date table and mark it as the model's date table:

```DAX
Calendar =
ADDCOLUMNS(
    CALENDAR(
        MIN(Transactions[transaction_date]),
        MAX(Transactions[transaction_date])
    ),
    "Year", YEAR([Date]),
    "Month Number", MONTH([Date]),
    "Month", FORMAT([Date], "MMM"),
    "Year-Month", FORMAT([Date], "YYYY-MM")
)
```

Create a relationship `Calendar[Date]` → `Transactions[transaction_date]` (one-to-many, single direction). Sort `Calendar[Month]` by `Calendar[Month Number]`; use `Year-Month` for chronological charts.

Format `Net Profit Margin %`, `Revenue MoM %`, and `Expenses MoM %` as Percentage.

## Recommended report pages

1. **Executive Overview** — cards for revenue, expenses, net profit, margin and net cash flow; monthly revenue/profit line chart.
2. **Profitability** — revenue and expense trend, margin by department, category contribution.
3. **Expense Analysis** — category/department bar charts and monthly matrix.
4. **Cash Flow** — inflows/outflows/net cash flow by month.
5. **Transactions** — detail table with date, category, department, counterparty, amount and type.

Use a currency slicer or separate reports per currency. Do not aggregate currencies together without exchange-rate conversion.
