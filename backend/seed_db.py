import asyncio
import os
import sys

# Ensure backend root is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, AsyncSessionLocal, Base
import models
from utils import hash_password
from pipeline.categories import seed_default_categories
from pipeline.rules import seed_default_rules
from routers.ingester import _process_statement_bytes


async def reset_and_seed():
    print("🔄 Dropping old tables and recreating database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database schema initialized cleanly.")

    async with AsyncSessionLocal() as db:
        # 1. Seed Categories
        print("🌱 Seeding default accounting categories (Assets, Liabilities, Income, Expenses, Capital, COGS, Transfers, Taxes)...")
        await seed_default_categories(db)
        print("✅ Categories seeded.")

        # 2. Seed Rules
        print("🌱 Seeding default categorization rules...")
        await seed_default_rules(db)
        print("✅ Rules seeded.")

        # 3. Seed Default User
        print("🌱 Seeding default finance user (finance@company.com)...")
        user = models.User(
            email="finance@company.com",
            password=hash_password("SecurePassword123!"),
            company_name="Access Capital Ltd",
            username="finance",
        )
        db.add(user)
        await db.commit()
        print("✅ User created.")

        # 4. Ingest Sample 1: Access Bank Statement PDF (56 transactions)
        fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "fixtures")
        pdf_path = os.path.join(fixtures_dir, "access_bank_statement.pdf")
        if os.path.exists(pdf_path):
            print(f"📄 Ingesting Access Bank PDF statement from {pdf_path}...")
            with open(pdf_path, "rb") as f:
                content = f.read()
            summary = await _process_statement_bytes(content, "Access_Bank_Oct2026.pdf", db)
            print(f"✅ Ingested PDF: {summary.bank_name} ({summary.new_rows_stored} transactions stored, math_ok={summary.math_ok}).")
        else:
            print(f"⚠️ PDF fixture not found at {pdf_path}")

        # 5. Ingest Sample 2: Demo Corporate Statement XLSX (35 transactions)
        xlsx_path = os.path.join(fixtures_dir, "demo_statement.xlsx")
        if os.path.exists(xlsx_path):
            print(f"📊 Ingesting Demo Corporate Statement XLSX from {xlsx_path}...")
            with open(xlsx_path, "rb") as f:
                content = f.read()
            summary = await _process_statement_bytes(content, "Demo_Corporate_Statement.xlsx", db)
            print(f"✅ Ingested Excel: {summary.bank_name} ({summary.new_rows_stored} transactions stored, math_ok={summary.math_ok}).")
        else:
            print(f"⚠️ Excel fixture not found at {xlsx_path}")

    print("\n🎉 Database successfully reset and reseeded with zero empty statements!")


if __name__ == "__main__":
    asyncio.run(reset_and_seed())
