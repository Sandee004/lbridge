import io
import os
from pathlib import Path
import pytest
from fastapi import UploadFile
from routers.ingester import upload_statement, list_statements, get_statement


@pytest.mark.asyncio
async def test_pdf_ingestion_and_deduplication(db_session):
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    pdf_path = fixtures_dir / "access_bank_statement.pdf"
    if not pdf_path.exists():
        pdf_path = Path(__file__).resolve().parent.parent.parent / "access_bank_statement.pdf"

    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    # 1. First upload
    upload_file_1 = UploadFile(filename="access_bank_statement.pdf", file=io.BytesIO(file_bytes))
    resp1 = await upload_statement(file=upload_file_1, db=db_session)

    assert resp1.statement_id is not None
    assert resp1.bank_name == "Access Bank Plc"
    assert resp1.currency == "NGN"
    assert resp1.total_rows_parsed == 56
    assert resp1.new_rows_stored == 56
    assert resp1.duplicates_skipped == 0
    assert resp1.math_ok is True
    assert resp1.opening_balance > 0
    assert resp1.closing_balance > 0

    stmt_id = resp1.statement_id

    # 2. Second upload (Deduplication check)
    upload_file_2 = UploadFile(filename="access_bank_statement.pdf", file=io.BytesIO(file_bytes))
    resp2 = await upload_statement(file=upload_file_2, db=db_session)

    assert resp2.total_rows_parsed == 56
    assert resp2.new_rows_stored == 0
    assert resp2.duplicates_skipped == 56

    # 3. List and get statement details
    statements = await list_statements(db=db_session)
    assert len(statements) >= 1

    single = await get_statement(statement_id=stmt_id, db=db_session)
    assert single.id == stmt_id
    assert single.bank_name == "Access Bank Plc"
    assert len(single.transactions) == 56
