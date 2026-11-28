import pytest
import httpx
from sqlalchemy import select
import models


@pytest.mark.asyncio
async def test_e2e_integration_flow(client: httpx.AsyncClient, auth_headers: dict, db_session):
    # 1. P3.4 Option A: In single-user local mode, requests succeed without auth headers
    async with httpx.AsyncClient(transport=client._transport, base_url="http://test") as unauth_client:
        unauth_res = await unauth_client.get("/statements")
        assert unauth_res.status_code == 200, f"Expected 200 OK in single-user mode, got {unauth_res.status_code}"

    # 2. Test sample loaders with authentication
    res = await client.post("/statements/sample/access-bank-pdf", headers=auth_headers)
    assert res.status_code == 200, f"Sample PDF load failed: {res.text}"
    pdf_summary = res.json()
    assert pdf_summary["total_rows_parsed"] == 56
    assert pdf_summary["math_ok"] is True

    res = await client.post("/statements/sample/demo-excel", headers=auth_headers)
    assert res.status_code == 200, f"Sample Excel load failed: {res.text}"
    excel_summary = res.json()
    assert excel_summary["total_rows_parsed"] == 35
    assert excel_summary["math_ok"] is True

    # 3. Retrieve all statements
    res = await client.get("/statements", headers=auth_headers)
    assert res.status_code == 200
    statements = res.json()
    assert len(statements) >= 2

    # 4. Triage resolution / override test
    all_txns = [t for s in statements for t in s["transactions"]]
    review_txns = [t for t in all_txns if t["element"] == "needs_review"]
    if review_txns:
        target_tx = review_txns[0]
        patch_data = {
            "element": "expense",
            "create_rule": True,
            "rule_pattern": "STARLINK_TEST",
            "rule_direction": "debit"
        }
        res = await client.patch(f"/statements/transactions/{target_tx['id']}", json=patch_data, headers=auth_headers)
        assert res.status_code == 200, f"Triage resolution failed: {res.text}"
        updated_tx = res.json()
        assert updated_tx["element"] == "expense"
        assert updated_tx["tier"] == "user"
        assert updated_tx["status"] == "reviewed"

        # Check rule is created in DB
        res = await client.get("/statements/rules", headers=auth_headers)
        assert res.status_code == 200
        rules = res.json()
        rule_patterns = [r["pattern"] for r in rules]
        assert any("STARLINK_TEST" in p for p in rule_patterns)

        # Verify Override record
        ov_match = await db_session.execute(
            select(models.Override).where(models.Override.transaction_id == target_tx["id"])
        )
        assert ov_match.scalars().first() is not None

    # 5. Verify Category Management
    res = await client.get("/categories", headers=auth_headers)
    assert res.status_code == 200, f"Get categories failed: {res.text}"
    cats = res.json()
    cat_names = [c["name"] for c in cats]
    assert "Cost of Goods Sold" in cat_names
    assert "Internal Transfer" in cat_names
    assert "Taxes & VAT" in cat_names
    assert len(cats) >= 8

    # Create custom category
    create_cat_res = await client.post(
        "/categories",
        json={
            "name": "Direct Materials",
            "direction": "debit",
            "color": "amber",
            "description": "Raw goods used in production"
        },
        headers=auth_headers
    )
    assert create_cat_res.status_code == 201, f"Create category failed: {create_cat_res.text}"
    custom_cat = create_cat_res.json()
    assert custom_cat["slug"] == "direct_materials"

    # Attempt to delete core category (should be rejected with 400)
    assets_cat = next((c for c in cats if c["slug"] == "assets" or c["name"] == "Assets"), None)
    if assets_cat:
        del_core_res = await client.delete(f"/categories/{assets_cat['id']}", headers=auth_headers)
        assert del_core_res.status_code == 400, f"Core category deletion should be rejected: {del_core_res.text}"

    # Delete custom category
    del_custom_res = await client.delete(f"/categories/{custom_cat['id']}", headers=auth_headers)
    assert del_custom_res.status_code == 204

    # 6. Verify non-empty statements
    res = await client.get("/statements", headers=auth_headers)
    assert res.status_code == 200
    active_stmts = res.json()
    for s in active_stmts:
        assert s["transaction_count"] > 0
        assert len(s["transactions"]) > 0
