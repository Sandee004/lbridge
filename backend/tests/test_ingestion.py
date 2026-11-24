import asyncio
import io
import os
from fastapi import UploadFile
from database import AsyncSessionLocal, engine, Base
from routers.ingester import upload_statement, list_statements, get_statement
import models

async def run_test():
    # 1. Reset / Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    pdf_path = os.path.join(os.path.dirname(__file__), "../access_bank_statement.pdf")
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    # 2. Upload 1
    async with AsyncSessionLocal() as db:
        upload_file_1 = UploadFile(filename="access_bank_statement.pdf", file=io.BytesIO(file_bytes))
        resp1 = await upload_statement(file=upload_file_1, db=db)
        print("Upload 1 Result (Access Bank):", {
            "statement_id": resp1.statement_id,
            "bank_name": resp1.bank_name,
            "currency": resp1.currency,
            "opening_balance": resp1.opening_balance,
            "closing_balance": resp1.closing_balance,
            "total_credits": resp1.total_credits,
            "total_debits": resp1.total_debits,
            "total_rows_parsed": resp1.total_rows_parsed,
            "new_rows_stored": resp1.new_rows_stored,
            "duplicates_skipped": resp1.duplicates_skipped,
            "math_ok": resp1.math_ok,
            "message": resp1.message
        })
        stmt_id = resp1.statement_id

    # 3. Upload 2 (Deduplication Test)
    async with AsyncSessionLocal() as db:
        upload_file_2 = UploadFile(filename="access_bank_statement.pdf", file=io.BytesIO(file_bytes))
        resp2 = await upload_statement(file=upload_file_2, db=db)
        print("Upload 2 (Dedup test) Result:", {
            "total_rows_parsed": resp2.total_rows_parsed,
            "new_rows_stored": resp2.new_rows_stored,
            "duplicates_skipped": resp2.duplicates_skipped,
            "message": resp2.message
        })

    # 4. List & Get Statement Details
    async with AsyncSessionLocal() as db:
        statements = await list_statements(db=db)
        print(f"Total statements in DB: {len(statements)}")
        single = await get_statement(statement_id=stmt_id, db=db)
        print(f"Retrieved statement {single.bank_name} ({single.currency}): {len(single.transactions)} transactions")
        print("\nSample Nigerian transactions in SQLite:")
        for t in single.transactions[:8]:
            print(f"  [{t.date}] {t.direction.upper():<6} ₦{t.amount:<12,.2f} (Bal: ₦{t.balance:,.2f}) {t.description_raw[:55]}")

if __name__ == "__main__":
    asyncio.run(run_test())
