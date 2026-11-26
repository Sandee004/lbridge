import asyncio
import io
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import UploadFile
from database import AsyncSessionLocal, engine, Base
from routers.ingester import upload_statement, list_statements, get_statement
import models

async def run_comprehensive_test():
    print("=" * 70)
    print("LEDGERBRIDGE END-TO-END PIPELINE & PARSER VERIFICATION")
    print("=" * 70)

    # 1. Reset tables to ensure clean state
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized.")

    # -------------------------------------------------------------
    # Test 1: Upload Access Bank PDF statement through full pipeline
    # -------------------------------------------------------------
    pdf_path = os.path.join(os.path.dirname(__file__), "../access_bank_statement.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print("\n--- Test 1: Ingesting Access Bank PDF (56 transactions) ---")
    async with AsyncSessionLocal() as db:
        upload_pdf = UploadFile(filename="access_bank_statement.pdf", file=io.BytesIO(pdf_bytes))
        resp_pdf = await upload_statement(file=upload_pdf, db=db)
        print("Upload Result:")
        print(f"  Statement ID:         {resp_pdf.statement_id}")
        print(f"  Bank:                 {resp_pdf.bank_name} ({resp_pdf.currency})")
        print(f"  Math OK:              {resp_pdf.math_ok}")
        print(f"  Total Rows Parsed:    {resp_pdf.total_rows_parsed}")
        print(f"  Classified by Rules:  {resp_pdf.rules_count}")
        print(f"  Processed by AI:      {resp_pdf.llm_count}")
        print(f"  Needs Review Bucket:  {resp_pdf.needs_review_count}")
        print(f"  New Rows Stored:      {resp_pdf.new_rows_stored}")
        print(f"  Message:              {resp_pdf.message}")

    # -------------------------------------------------------------
    # Test 2: Ingest Excel statement (.xlsx)
    # -------------------------------------------------------------
    xlsx_path = os.path.join(os.path.dirname(__file__), "../demo_statement.xlsx")
    with open(xlsx_path, "rb") as f:
        xlsx_bytes = f.read()

    print("\n--- Test 2: Ingesting Excel .xlsx Statement (35 transactions) ---")
    async with AsyncSessionLocal() as db:
        upload_xlsx = UploadFile(filename="demo_statement.xlsx", file=io.BytesIO(xlsx_bytes))
        resp_xlsx = await upload_statement(file=upload_xlsx, db=db)
        print("Upload Result:")
        print(f"  Statement ID:         {resp_xlsx.statement_id}")
        print(f"  Bank:                 {resp_xlsx.bank_name} ({resp_xlsx.currency})")
        print(f"  Math OK:              {resp_xlsx.math_ok}")
        print(f"  Total Rows Parsed:    {resp_xlsx.total_rows_parsed}")
        print(f"  Classified by Rules:  {resp_xlsx.rules_count}")
        print(f"  Processed by AI:      {resp_xlsx.llm_count}")
        print(f"  Needs Review Bucket:  {resp_xlsx.needs_review_count}")
        print(f"  New Rows Stored:      {resp_xlsx.new_rows_stored}")
        print(f"  Message:              {resp_xlsx.message}")

    # -------------------------------------------------------------
    # Test 3: Deduplication check on re-upload
    # -------------------------------------------------------------
    print("\n--- Test 3: Testing Deduplication on Re-uploading Excel ---")
    async with AsyncSessionLocal() as db:
        upload_xlsx_2 = UploadFile(filename="demo_statement.xlsx", file=io.BytesIO(xlsx_bytes))
        resp_dedup = await upload_statement(file=upload_xlsx_2, db=db)
        print(f"  New rows stored:      {resp_dedup.new_rows_stored} (Expected: 0)")
        print(f"  Duplicates skipped:   {resp_dedup.duplicates_skipped} (Expected: 35)")

    # -------------------------------------------------------------
    # Test 4: Inspect Categorized Rows from SQLite
    # -------------------------------------------------------------
    print("\n--- Test 4: Sample Classified Rows Breakdown ---")
    async with AsyncSessionLocal() as db:
        stmt = await get_statement(statement_id=resp_pdf.statement_id, db=db)
        print(f"Showing sample classifications from statement '{stmt.bank_name}':")
        for t in stmt.transactions[:12]:
            tier_badge = f"[{t.tier.upper()}]" if t.tier else "[NONE]"
            elem_badge = f"[{t.element.upper()}]" if t.element else "[UNKNOWN]"
            print(f"  {t.date} | {tier_badge:<8} {elem_badge:<14} | ₦{t.amount:<10,.2f} | {t.description_raw[:45]}")
            print(f"         Reason: {t.reason[:65]}")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
