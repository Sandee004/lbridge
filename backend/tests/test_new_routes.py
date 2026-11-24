import asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from database import AsyncSessionLocal, engine, Base

async def test_routes():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test rules list
        res = await client.get("/statements/rules")
        assert res.status_code == 200, f"GET /statements/rules failed: {res.text}"
        print(f"✅ GET /statements/rules: {len(res.json())} rules returned")

        # 2. Test create rule
        new_rule_payload = {
            "pattern": "TEST_VENDOR_KEYWORD",
            "element": "expense",
            "direction": "debit",
            "priority": 50,
            "match_type": "word_regex"
        }
        res = await client.post("/statements/rules", json=new_rule_payload)
        assert res.status_code == 201, f"POST /statements/rules failed: {res.text}"
        rule_data = res.json()
        print(f"✅ POST /statements/rules created rule id: {rule_data['id']}")

        # 3. Test list statements
        res = await client.get("/statements")
        assert res.status_code == 200, f"GET /statements failed: {res.text}"
        statements = res.json()
        print(f"✅ GET /statements: {len(statements)} statements in database")

        # 4. If statements exist, test PATCH transaction
        if statements and statements[0]["transactions"]:
            first_txn = statements[0]["transactions"][0]
            txn_id = first_txn["id"]
            patch_payload = {
                "element": "Assets",
                "create_rule": True,
                "rule_pattern": "EQUIPMENT_PURCHASE",
                "rule_direction": "debit"
            }
            res = await client.patch(f"/statements/transactions/{txn_id}", json=patch_payload)
            assert res.status_code == 200, f"PATCH /statements/transactions failed: {res.text}"
            updated = res.json()
            assert updated["element"] == "asset", f"Element not updated properly: {updated['element']}"
            assert updated["tier"] == "user"
            assert updated["status"] == "reviewed"
            print(f"✅ PATCH /statements/transactions/{txn_id} updated element to {updated['element']}")

        # 5. Clean up the test rule
        res = await client.delete(f"/statements/rules/{rule_data['id']}")
        assert res.status_code == 204, f"DELETE /statements/rules failed: {res.text}"
        print("✅ DELETE /statements/rules deleted test rule")

    print("🎉 ALL BACKEND ROUTE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_routes())
