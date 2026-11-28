import csv
import io
import openpyxl
import pytest
import httpx
from models import Statement, Transaction
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_p4_1_and_p4_3_flat_csv_export_and_formula_guard(
    client: httpx.AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    # Create a test statement
    stmt = Statement(
        id="test-stmt-401",
        filename="export_test.pdf",
        bank_name="Access Bank Plc",
        currency="NGN",
        opening_balance=100000.0,
        closing_balance=150000.0,
        total_credits=75000.0,
        total_debits=25000.0,
        math_ok=True,
    )
    db_session.add(stmt)
    await db_session.flush()

    # Add transactions including P4.3 formula injection attempts
    txns = [
        Transaction(
            id="txn-01",
            statement_id=stmt.id,
            fingerprint="fp-01",
            date="01/10/2026",
            amount=50000.0,
            direction="credit",
            description_raw='=HYPERLINK("http://malicious-site.com", "Malicious Link")',
            description_norm="hyperlink malicious link",
            element="income",
            tier="rule",
            rule_id=1,
            confidence=1.0,
            status="auto",
        ),
        Transaction(
            id="txn-02",
            statement_id=stmt.id,
            fingerprint="fp-02",
            date="02/10/2026",
            amount=25000.0,
            direction="debit",
            description_raw="+cmd|' /C calc'!A0",
            description_norm="cmd calc",
            element="expense",
            tier="llm",
            confidence=0.92,
            status="auto",
        ),
        Transaction(
            id="txn-03",
            statement_id=stmt.id,
            fingerprint="fp-03",
            date="03/10/2026",
            amount=15000.0,
            direction="credit",
            description_raw="@SUM(1+1)*cmd",
            description_norm="sum cmd",
            element="income",
            tier="user",
            confidence=1.0,
            status="reviewed",
        ),
        Transaction(
            id="txn-04",
            statement_id=stmt.id,
            fingerprint="fp-04",
            date="04/10/2026",
            amount=10000.0,
            direction="debit",
            description_raw="-2+5+cmd|' /C notepad'!A0",
            description_norm="cmd notepad",
            element="expense",
            tier="rule",
            rule_id=2,
            confidence=0.99,
            status="auto",
        ),
    ]
    for t in txns:
        db_session.add(t)
    await db_session.commit()

    # GET /statements/{id}/export?format=csv&mode=flat
    res = await client.get(f"/statements/{stmt.id}/export?format=csv&mode=flat", headers=auth_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    assert "clean_ledger.csv" in res.headers["content-disposition"]

    # Parse CSV output
    reader = csv.reader(io.StringIO(res.text))
    rows = list(reader)
    header = rows[0]
    assert header == ["ID", "Date", "Value_Date", "Narration", "Direction", "Amount", "Element", "Tier", "Confidence", "Status"]

    # P4.3: Assert formula injection strings in text columns are neutralized with leading single quote
    data_rows = rows[1:]
    assert len(data_rows) == 4

    # Row 1: =HYPERLINK(...) neutralized to '=HYPERLINK(...)
    assert data_rows[0][3].startswith("'=")
    assert data_rows[0][3] == '\'=HYPERLINK("http://malicious-site.com", "Malicious Link")'
    assert data_rows[0][5] == "50000.0"  # Numeric amount untouched

    # Row 2: +cmd neutralized to '+cmd
    assert data_rows[1][3].startswith("'+")

    # Row 3: @SUM neutralized to '@SUM
    assert data_rows[2][3].startswith("'@")

    # Row 4: -2+5 neutralized to '-2+5
    assert data_rows[3][3].startswith("'-")


@pytest.mark.asyncio
async def test_p4_2_journal_csv_blocks_unresolved_and_exports_when_clean(
    client: httpx.AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    stmt = Statement(
        id="test-stmt-402",
        filename="journal_test.pdf",
        bank_name="Zenith Bank Plc",
        currency="NGN",
        opening_balance=200000.0,
        closing_balance=250000.0,
        total_credits=50000.0,
        total_debits=0.0,
        math_ok=True,
    )
    db_session.add(stmt)
    await db_session.flush()

    # Add 1 resolved transaction and 1 unresolved (needs_review) transaction
    t1 = Transaction(
        id="txn-j1",
        statement_id=stmt.id,
        fingerprint="fp-j1",
        date="01/10/2026",
        amount=30000.0,
        direction="credit",
        description_raw="CONSULTING FEE CLIENT PAYMENT",
        description_norm="consulting fee client payment",
        element="income",
        tier="rule",
        confidence=1.0,
        status="auto",
    )
    t2 = Transaction(
        id="txn-j2",
        statement_id=stmt.id,
        fingerprint="fp-j2",
        date="02/10/2026",
        amount=20000.0,
        direction="debit",
        description_raw="UNKNOWN UNTAGGED PAYMENT REF992",
        description_norm="unknown untagged payment ref992",
        element="needs_review",
        tier="validator",
        confidence=0.0,
        status="auto",
    )
    db_session.add(t1)
    db_session.add(t2)
    await db_session.commit()

    # P4.2: Journal export must refuse unresolved rows
    res_blocked = await client.get(f"/statements/{stmt.id}/export?format=csv&mode=journal", headers=auth_headers)
    assert res_blocked.status_code == 400
    assert "1 unresolved transaction" in res_blocked.json()["detail"]

    # Now resolve the unresolved transaction
    t2.element = "expense"
    t2.status = "reviewed"
    await db_session.commit()

    # Re-attempt journal export
    res_ok = await client.get(f"/statements/{stmt.id}/export?format=csv&mode=journal", headers=auth_headers)
    assert res_ok.status_code == 200
    assert "journal.csv" in res_ok.headers["content-disposition"]

    # Verify double entry structure
    reader = csv.reader(io.StringIO(res_ok.text))
    rows = list(reader)
    assert rows[0] == ["Journal_Date", "Journal_Number", "Account_Name", "Debit", "Credit", "Description"]

    # 2 transactions * 2 double-entry rows = 4 rows
    journal_rows = rows[1:]
    assert len(journal_rows) == 4

    total_debit = sum(float(r[3]) for r in journal_rows)
    total_credit = sum(float(r[4]) for r in journal_rows)
    assert total_debit == total_credit == 50000.0


@pytest.mark.asyncio
async def test_p4_4_xlsx_export_three_sheets_and_sumifs(
    client: httpx.AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    stmt = Statement(
        id="test-stmt-404",
        filename="excel_test.pdf",
        bank_name="GTBank Plc",
        currency="NGN",
        opening_balance=500000.0,
        closing_balance=600000.0,
        total_credits=150000.0,
        total_debits=50000.0,
        math_ok=True,
    )
    db_session.add(stmt)
    await db_session.flush()

    txns = [
        Transaction(
            id="txn-x1",
            statement_id=stmt.id,
            fingerprint="fp-x1",
            date="01/10/2026",
            amount=150000.0,
            direction="credit",
            description_raw="CLIENT CONTRACT PAYMENT",
            description_norm="client contract payment",
            element="income",
            tier="rule",
            confidence=1.0,
            status="auto",
        ),
        Transaction(
            id="txn-x2",
            statement_id=stmt.id,
            fingerprint="fp-x2",
            date="02/10/2026",
            amount=30000.0,
            direction="debit",
            description_raw="OFFICE RENT CONTRIBUTION",
            description_norm="office rent contribution",
            element="expense",
            tier="llm",
            confidence=0.88,
            status="auto",
        ),
        Transaction(
            id="txn-x3",
            statement_id=stmt.id,
            fingerprint="fp-x3",
            date="03/10/2026",
            amount=20000.0,
            direction="debit",
            description_raw="PETROL GENERATOR DIESEL",
            description_norm="petrol generator diesel",
            element="expense",
            tier="rule",
            confidence=0.99,
            status="auto",
        ),
    ]
    for t in txns:
        db_session.add(t)
    await db_session.commit()

    # GET /statements/{id}/export?format=xlsx
    res = await client.get(f"/statements/{stmt.id}/export?format=xlsx", headers=auth_headers)
    assert res.status_code == 200
    assert "spreadsheetml.sheet" in res.headers["content-type"]

    # Open workbook with openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(res.content))
    assert wb.sheetnames == ["Categorized Rows", "5-Element Summary", "Audit Log"]

    # Sheet 1: Categorized Rows
    ws_rows = wb["Categorized Rows"]
    assert ws_rows.max_row == 4  # Header + 3 transactions
    assert ws_rows["D2"].value == "CLIENT CONTRACT PAYMENT"
    assert ws_rows["F2"].value == 150000.0

    # Sheet 2: 5-Element Summary
    ws_summary = wb["5-Element Summary"]
    summary_rows = list(ws_summary.iter_rows(values_only=True))
    assert summary_rows[0] == ("Element", "Total Amount")

    # Check SUMIFS formula format
    elem_formula_map = {row[0]: row[1] for row in summary_rows[1:]}
    assert "=SUMIFS('Categorized Rows'!$F:$F, 'Categorized Rows'!$G:$G, A2)" in elem_formula_map.get("Assets", "")
    assert "=SUMIFS('Categorized Rows'!$F:$F, 'Categorized Rows'!$G:$G, A4)" in elem_formula_map.get("Income", "")
    assert "=SUMIFS('Categorized Rows'!$F:$F, 'Categorized Rows'!$G:$G, A5)" in elem_formula_map.get("Expenses", "")

    # Calculate actual row sums in 'Categorized Rows' to verify they equal the expected category amounts
    row_data = list(ws_rows.iter_rows(values_only=True))[1:]
    income_sum = sum(float(r[5]) for r in row_data if r[6] == "Income")
    expense_sum = sum(float(r[5]) for r in row_data if r[6] == "Expenses")
    assert income_sum == 150000.0
    assert expense_sum == 50000.0

    # Sheet 3: Audit Log
    ws_audit = wb["Audit Log"]
    audit_rows = list(ws_audit.iter_rows(values_only=True))
    assert audit_rows[0] == (
        "Transaction ID", "Date", "Description", "Amount", "Element", "Tier", "Rule ID / Model", "Confidence", "Status", "Reason"
    )
    assert len(audit_rows) == 4  # Header + 3 transactions
    assert audit_rows[1][5] == "rule"
    assert audit_rows[2][5] == "llm"
