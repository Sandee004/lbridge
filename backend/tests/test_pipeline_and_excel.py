import io
from pathlib import Path
import pytest
import httpx
from fastapi import UploadFile
from routers.ingester import upload_statement, get_statement
from parser.pdf_parser import parse_pdf_statement
from parser.excel_parser import parse_excel_or_csv_statement
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@pytest.mark.asyncio
async def test_pipeline_pdf_and_excel(db_session):
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    pdf_path = fixtures_dir / "access_bank_statement.pdf"
    if not pdf_path.exists():
        pdf_path = Path(__file__).resolve().parent.parent.parent / "access_bank_statement.pdf"

    xlsx_path = fixtures_dir / "demo_statement.xlsx"
    if not xlsx_path.exists():
        xlsx_path = Path(__file__).resolve().parent.parent.parent / "demo_statement.xlsx"

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    with open(xlsx_path, "rb") as f:
        xlsx_bytes = f.read()

    # 1. Ingest PDF
    upload_pdf = UploadFile(filename="access_bank_statement.pdf", file=io.BytesIO(pdf_bytes))
    resp_pdf = await upload_statement(file=upload_pdf, db=db_session)

    assert resp_pdf.statement_id is not None
    assert resp_pdf.math_ok is True
    assert resp_pdf.total_rows_parsed == 56
    assert resp_pdf.new_rows_stored == 56
    assert resp_pdf.rules_count > 0

    # 2. Ingest Excel
    upload_xlsx = UploadFile(filename="demo_statement.xlsx", file=io.BytesIO(xlsx_bytes))
    resp_xlsx = await upload_statement(file=upload_xlsx, db=db_session)

    assert resp_xlsx.statement_id is not None
    assert resp_xlsx.math_ok is True
    assert resp_xlsx.total_rows_parsed == 35
    assert resp_xlsx.new_rows_stored == 35

    # 3. Deduplication on re-upload
    upload_xlsx_2 = UploadFile(filename="demo_statement.xlsx", file=io.BytesIO(xlsx_bytes))
    resp_dedup = await upload_statement(file=upload_xlsx_2, db=db_session)

    assert resp_dedup.new_rows_stored == 0
    assert resp_dedup.duplicates_skipped == 35

    # 4. Check classified rows
    stmt = await get_statement(statement_id=resp_pdf.statement_id, db=db_session)
    assert len(stmt.transactions) == 56
    for t in stmt.transactions:
        assert t.element in ["asset", "liability", "income", "expense", "capital", "needs_review", "cogs", "internal_transfer", "taxes_vat"]
        assert t.tier in ["rule", "llm", "user", "ingestion"]


def test_pdf_parser_raises_on_unrecognizable_table():
    """P1.3: Feeding a PDF with no recognizable table raises ValueError."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 700, "This is an essay about accounting principles.")
    c.drawString(100, 680, "It does not contain any bank statements or transaction tables.")
    c.drawString(100, 660, "There are no dates or debit/credit amounts here whatsoever.")
    c.save()
    buf.seek(0)
    pdf_bytes = buf.read()

    with pytest.raises(ValueError, match="No transactions could be parsed"):
        parse_pdf_statement(pdf_bytes)


def test_excel_parser_raises_on_empty_or_no_table():
    """P1.3: Feeding an Excel/CSV with no table raises ValueError."""
    empty_csv = "Random Header,Another Note\nJust random prose,No transactions here\n"
    with pytest.raises(ValueError, match="Could not identify statement table columns|No transaction records found|No transactions could be parsed"):
        parse_excel_or_csv_statement(empty_csv.encode("utf-8"), filename="test.csv")


def test_missing_balances_marks_math_not_ok():
    """P1.3: When balances cannot be found, math_ok is False and error detail is set."""
    csv_data = (
        "Date,Description,Debit,Credit\n"
        "01/10/2026,Office Supplies,5000.00,0.00\n"
        "02/10/2026,Client Retainer,0.00,15000.00\n"
    )
    res = parse_excel_or_csv_statement(csv_data.encode("utf-8"), filename="nobalance.csv")
    assert res["transaction_count"] == 2
    assert res["math_ok"] is False
    assert res["math_error_detail"] == "Could not verify: balances not found"


@pytest.mark.asyncio
async def test_upload_unrecognizable_pdf_returns_422(client: httpx.AsyncClient, auth_headers: dict):
    """P1.3: Uploading a PDF without recognizable transactions returns HTTP 422."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 700, "Notice: Bank Holiday Announcement and Operational Updates.")
    c.drawString(100, 680, "All branches will remain closed on national holidays.")
    c.save()
    buf.seek(0)

    files = {"file": ("unrecognizable.pdf", buf.getvalue(), "application/pdf")}
    res = await client.post("/statements/upload", files=files, headers=auth_headers)
    assert res.status_code == 422, f"Expected 422 Unprocessable Entity, got {res.status_code}: {res.text}"
