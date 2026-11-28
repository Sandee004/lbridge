import pytest
import httpx
from sqlalchemy import select
import models


@pytest.mark.asyncio
async def test_rules_and_transactions_routes(client: httpx.AsyncClient, auth_headers: dict, db_session):
    # 1. Test rules list
    res = await client.get("/statements/rules", headers=auth_headers)
    assert res.status_code == 200, f"GET /statements/rules failed: {res.text}"
    rules = res.json()
    assert isinstance(rules, list)
    assert len(rules) > 0

    # 2. Test create rule
    new_rule_payload = {
        "pattern": "TEST_PYTEST_RULE",
        "element": "expense",
        "direction": "debit",
        "priority": 50,
        "match_type": "word_regex"
    }
    res = await client.post("/statements/rules", json=new_rule_payload, headers=auth_headers)
    assert res.status_code == 201, f"POST /statements/rules failed: {res.text}"
    rule_data = res.json()
    assert "TEST_PYTEST_RULE" in rule_data["pattern"]
    assert rule_data["element"] == "expense"
    rule_id = rule_data["id"]

    # 3. Test list statements
    res = await client.get("/statements", headers=auth_headers)
    assert res.status_code == 200, f"GET /statements failed: {res.text}"
    statements = res.json()
    assert isinstance(statements, list)

    # If statements exist, test PATCH transaction
    if statements and statements[0]["transactions"]:
        first_txn = statements[0]["transactions"][0]
        txn_id = first_txn["id"]
        patch_payload = {
            "element": "Assets",
            "create_rule": True,
            "rule_pattern": "EQUIPMENT_PURCHASE",
            "rule_direction": "debit"
        }
        res = await client.patch(f"/statements/transactions/{txn_id}", json=patch_payload, headers=auth_headers)
        assert res.status_code == 200, f"PATCH /statements/transactions failed: {res.text}"
        updated = res.json()
        assert updated["element"] == "asset"
        assert updated["tier"] == "user"
        assert updated["status"] == "reviewed"

        # Verify an Override record was created in the database
        override_res = await db_session.execute(
            select(models.Override).where(models.Override.transaction_id == txn_id)
        )
        override = override_res.scalars().first()
        assert override is not None
        assert override.final_element == "asset"

    # 4. Clean up the test rule
    res = await client.delete(f"/statements/rules/{rule_id}", headers=auth_headers)
    assert res.status_code == 204, f"DELETE /statements/rules failed: {res.text}"
