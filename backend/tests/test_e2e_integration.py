import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, ASGITransport
from main import app
from database import Base, engine

async def run_e2e():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Verify Frontend SPA is served
        res = await client.get("/")
        assert res.status_code == 200, f"SPA index failed: {res.status_code}"
        assert "<!doctype html>" in res.text.lower() or "<html" in res.text.lower()
        print("✅ Frontend SPA served successfully at '/'")

        # 2. Check health endpoint
        res = await client.get("/health")
        assert res.status_code == 200
        print("✅ Health endpoint returned status: ok")

        # 3. Verify unauthenticated request to protected endpoint is rejected
        unauth_res = await client.get("/statements")
        assert unauth_res.status_code == 401, f"Expected 401 Unauthorized, got {unauth_res.status_code}"
        print("✅ Unauthenticated request correctly rejected with 401 Unauthorized")

        # 4. Authenticate / Signup user with company_name
        auth_payload = {
            "email": "finance@company.com",
            "password": "SecurePassword123!",
            "company_name": "Acme Finance Corp"
        }
        login_res = await client.post("/auth/login", json={"email": auth_payload["email"], "password": auth_payload["password"]})
        if login_res.status_code == 200:
            token = login_res.json()["access_token"]
            print("✅ Logged in existing user")
        else:
            signup_res = await client.post("/auth/signup", json=auth_payload)
            assert signup_res.status_code in [200, 201], f"Signup failed: {signup_res.text}"
            token = signup_res.json()["access_token"]
            print(f"✅ Signed up new user with company '{auth_payload['company_name']}'")

        headers = {"Authorization": f"Bearer {token}"}

        # 5. Test Sample Loader for Access Bank PDF with auth
        res = await client.post("/statements/sample/access-bank-pdf", headers=headers)
        assert res.status_code == 200, f"Sample load failed: {res.text}"
        pdf_summary = res.json()
        print(f"✅ Loaded Access Bank PDF: {pdf_summary['bank_name']} ({pdf_summary['total_rows_parsed']} rows, math_ok: {pdf_summary['math_ok']})")

        # 6. Test Sample Loader for Demo Excel with auth
        res = await client.post("/statements/sample/demo-excel", headers=headers)
        assert res.status_code == 200, f"Sample load failed: {res.text}"
        excel_summary = res.json()
        print(f"✅ Loaded Excel Demo: {excel_summary['bank_name']} ({excel_summary['total_rows_parsed']} rows, math_ok: {excel_summary['math_ok']})")

        # 7. Verify statement listing has statements
        res = await client.get("/statements", headers=headers)
        assert res.status_code == 200
        statements = res.json()
        assert len(statements) >= 2, f"Expected at least 2 statements, got {len(statements)}"
        print(f"✅ Retrieved {len(statements)} statements from SQLite")

        # 8. Verify triage workflow on an unreviewed transaction
        all_txns = [t for s in statements for t in s["transactions"]]
        needs_review = [t for t in all_txns if t["element"] in ["needs_review", "Needs Review"]]
        print(f"ℹ️ Found {len(needs_review)} transactions pending review")

        if needs_review:
            target_tx = needs_review[0]
            patch_data = {
                "element": "expense",
                "create_rule": True,
                "rule_pattern": "STARLINK_TEST",
                "rule_direction": "debit"
            }
            res = await client.patch(f"/statements/transactions/{target_tx['id']}", json=patch_data, headers=headers)
            assert res.status_code == 200, f"Triage resolution failed: {res.text}"
            updated_tx = res.json()
            assert updated_tx["element"] == "expense"
            assert updated_tx["tier"] == "user"
            assert updated_tx["status"] == "reviewed"
            print(f"✅ Triage resolved txn {target_tx['id'][:8]} -> expense, created rule STARLINK_TEST")

            # Check rule is created in DB
            res = await client.get("/statements/rules", headers=headers)
            assert res.status_code == 200
            rules = res.json()
            rule_patterns = [r["pattern"] for r in rules]
            assert "STARLINK_TEST" in rule_patterns, f"Rule not persisted: {rule_patterns}"
            print("✅ Verified rule STARLINK_TEST exists in rules database")

    print("\n🎉 ALL SECURE BACKEND & INTEGRATION CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(run_e2e())
