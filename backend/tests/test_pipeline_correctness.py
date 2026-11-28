import json
import pytest
import httpx
from sqlalchemy import select
import config
import models
from pipeline.llm import (
    OLLAMA_RESULT_SCHEMA,
    ALLOWED_ELEMENTS,
    classify_batch_with_ollama,
    get_few_shot_examples,
)
from pipeline.categories import DEFAULT_CATEGORIES
from pipeline.orchestrator import validate_and_guard, run_classification_pipeline
from pipeline.rules import apply_rules_to_transactions, seed_default_rules
from parser.pdf_parser import parse_pdf_statement
from routers.statements import process_statement_bytes


def test_p2_1_schema_used_in_request(monkeypatch):
    """P2.1: Ollama request body format must be the schema dict, not 'json'."""
    sent_request = {}

    async def mock_post(self, url, *args, **kwargs):
        nonlocal sent_request
        sent_request = kwargs.get("json", {})
        return httpx.Response(200, json={"message": {"content": json.dumps({"results": []})}})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    batch = [{"fingerprint": "abc", "amount": 100.0, "direction": "debit", "description_raw": "Test"}]
    import asyncio
    asyncio.run(classify_batch_with_ollama(batch))

    assert sent_request.get("format") == OLLAMA_RESULT_SCHEMA
    assert isinstance(sent_request.get("format"), dict)


def test_p2_2_aligned_element_set():
    """P2.2: Schema enum must equal category slugs plus 'needs_review'."""
    expected = [c["slug"] for c in DEFAULT_CATEGORIES] + ["needs_review"]
    schema_enum = OLLAMA_RESULT_SCHEMA["properties"]["results"]["items"]["properties"]["element"]["enum"]
    assert sorted(schema_enum) == sorted(expected)


@pytest.mark.asyncio
async def test_p2_3_validate_model_output(monkeypatch):
    """P2.3: Unknown element or non-numeric confidence must become needs_review."""
    async def mock_post(self, url, *args, **kwargs):
        return httpx.Response(200, json={
            "message": {
                "content": json.dumps({
                    "results": [
                        {"id": "0", "element": "Expenses", "confidence": 0.95, "reason": "plural"},
                        {"id": "1", "element": "foo", "confidence": 0.90, "reason": "invalid"},
                        {"id": "2", "element": "expense", "confidence": "high", "reason": "string conf"},
                    ]
                })
            }
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    batch = [
        {"amount": 100.0, "direction": "debit", "description_raw": "Item 0"},
        {"amount": 200.0, "direction": "debit", "description_raw": "Item 1"},
        {"amount": 300.0, "direction": "debit", "description_raw": "Item 2"},
    ]

    classified = await classify_batch_with_ollama(batch)

    assert classified[0]["element"] == "needs_review"
    assert "unknown category" in classified[0]["reason"].lower()

    assert classified[1]["element"] == "needs_review"
    assert "unknown category" in classified[1]["reason"].lower()

    assert classified[2]["element"] == "needs_review"
    assert classified[2]["confidence"] == 0.0


@pytest.mark.asyncio
async def test_p2_4_short_row_ids(monkeypatch):
    """P2.4: Indices '0'..'n' must be sent and mapped back; omitted index becomes needs_review."""
    sent_request = {}

    async def mock_post(self, url, *args, **kwargs):
        nonlocal sent_request
        sent_request = kwargs.get("json", {})
        return httpx.Response(200, json={
            "message": {
                "content": json.dumps({
                    "results": [
                        {"id": "0", "element": "expense", "confidence": 0.95, "reason": "matched index 0"}
                        # id "1" omitted
                    ]
                })
            }
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    batch = [
        {"amount": 50.0, "direction": "debit", "description_raw": "AWS CLOUD"},
        {"amount": 150.0, "direction": "debit", "description_raw": "UBER TRIP"},
    ]

    classified = await classify_batch_with_ollama(batch)

    # Verify short index IDs in payload
    user_msg = sent_request["messages"][1]["content"]
    assert '"id": "0"' in user_msg
    assert '"id": "1"' in user_msg

    # Row 0 mapped correctly
    assert classified[0]["element"] == "expense"
    assert classified[0]["confidence"] == 0.95

    # Row 1 omitted -> needs_review
    assert classified[1]["element"] == "needs_review"
    assert classified[1]["confidence"] == 0.0


@pytest.mark.asyncio
async def test_p2_5_dedup_before_classification(db_session, monkeypatch):
    """P2.5: Re-uploading overlapping data makes zero LLM calls and does not change rule hit_count."""
    llm_call_count = 0
    orig_post = httpx.AsyncClient.post

    async def mock_post(self, url, *args, **kwargs):
        nonlocal llm_call_count
        if "/api/chat" in str(url):
            llm_call_count += 1
            return httpx.Response(200, json={"message": {"content": json.dumps({"results": []})}})
        return await orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    csv_data = (
        "Date,Description,Debit,Credit,Balance\n"
        "01/10/2026,AWS CLOUD SERVICES,5000.00,0.00,95000.00\n"
        "02/10/2026,UNKNOWN RANDOM MERCHANT,2000.00,0.00,93000.00\n"
    ).encode("utf-8")

    # 1. First upload
    resp1 = await process_statement_bytes(csv_data, "test_p25.csv", db_session)
    assert resp1.new_rows_stored == 2
    assert llm_call_count == 1  # 1 call for UNKNOWN RANDOM MERCHANT

    # Get rule hit count for AWS rule
    aws_rule_res = await db_session.execute(select(models.Rule).where(models.Rule.pattern.contains("aws")))
    aws_rule = aws_rule_res.scalars().first()
    hit_count_before = aws_rule.hit_count if aws_rule else 0

    # 2. Re-upload the exact same CSV
    llm_calls_before_reupload = llm_call_count
    resp2 = await process_statement_bytes(csv_data, "test_p25.csv", db_session)
    assert resp2.new_rows_stored == 0
    assert resp2.duplicates_skipped == 2

    # Assert ZERO new LLM calls were made
    assert llm_call_count == llm_calls_before_reupload

    # Assert rule hit_count did NOT change
    await db_session.refresh(aws_rule)
    assert aws_rule.hit_count == hit_count_before


@pytest.mark.asyncio
async def test_p2_6_user_rule_priority_and_validation(client: httpx.AsyncClient, auth_headers: dict, db_session):
    """P2.6: User rules have higher priority (200), word boundary escape, and element validation."""
    # 1. Invalid element on PATCH transaction returns 422
    # Ingest a sample first
    res = await client.post("/statements/sample/access-bank-pdf", headers=auth_headers)
    assert res.status_code == 200
    stmts_res = await client.get("/statements", headers=auth_headers)
    txn = stmts_res.json()[0]["transactions"][0]

    bad_patch = await client.patch(
        f"/statements/transactions/{txn['id']}",
        json={"element": "non_existent_category"},
        headers=auth_headers
    )
    assert bad_patch.status_code == 422

    # 2. Override SPECTRANET row (normally Expense seed rule with priority 90) to Asset with user rule
    spectranet_txns = [t for t in stmts_res.json()[0]["transactions"] if "SPECTRANET" in t["description_raw"]]
    assert len(spectranet_txns) > 0
    target_txn = spectranet_txns[0]

    patch_res = await client.patch(
        f"/statements/transactions/{target_txn['id']}",
        json={"element": "asset", "create_rule": True, "rule_pattern": "SPECTRANET"},
        headers=auth_headers
    )
    assert patch_res.status_code == 200

    # Check rule was created with priority 200 and escaped pattern
    rule_res = await db_session.execute(
        select(models.Rule).where(models.Rule.source == "user", models.Rule.pattern.contains("SPECTRANET"))
    )
    user_rule = rule_res.scalars().first()
    assert user_rule is not None
    assert user_rule.priority == 200
    assert r"\bSPECTRANET\b" in user_rule.pattern

    # 3. Ingest a new row matching "SPECTRANET" and assert it matches the user rule (Asset) not seed rule (Expense)
    new_csv = (
        "Date,Description,Debit,Credit,Balance\n"
        "15/10/2026,SPECTRANET 5G ENTERPRISE ROUTER,550000.00,0.00,830000.00\n"
    ).encode("utf-8")
    resp_new = await process_statement_bytes(new_csv, "new_spectranet.csv", db_session)
    assert resp_new.new_rows_stored == 1

    # Check the stored transaction
    new_txn_match = await db_session.execute(
        select(models.Transaction).where(models.Transaction.description_raw.contains("SPECTRANET 5G"))
    )
    stored_txn = new_txn_match.scalars().first()
    assert stored_txn.element == "asset"
    assert stored_txn.tier == "rule"


@pytest.mark.asyncio
async def test_p2_7_seed_rule_cleanup(db_session):
    """P2.7: 'SLOT SYSTEMS ... LAPTOP REPAIR' must not be auto-classified as an asset."""
    await seed_default_rules(db_session)
    txns = [{
        "description_raw": "SLOT SYSTEMS IKEJA LAPTOP REPAIR",
        "description_norm": "slot systems ikeja laptop repair",
        "direction": "debit",
        "amount": 15000.0,
    }]
    matched, unmatched = await apply_rules_to_transactions(txns, db_session)
    # If matched by anything, it must NOT be an asset
    if matched:
        assert matched[0]["element"] != "asset"


def test_p2_8_capitalization_threshold():
    """P2.8: Asset purchase below threshold demoted to needs_review; above threshold remains asset."""
    # Under threshold (e.g. ₦150,000 < ₦500,000)
    small_asset = {
        "amount": 150000.0,
        "direction": "debit",
        "element": "asset",
        "tier": "rule",
        "description_raw": "OFFICE CHAIR",
    }
    validate_and_guard(small_asset)
    assert small_asset["element"] == "needs_review"
    assert small_asset["tier"] == "validator"
    assert small_asset["confidence"] == 0.0
    assert "capitalization threshold" in small_asset["reason"].lower()

    # Above threshold (e.g. ₦1,200,000 >= ₦500,000)
    large_asset = {
        "amount": 1200000.0,
        "direction": "debit",
        "element": "asset",
        "tier": "rule",
        "description_raw": "MACBOOK PRO M3 MAX",
    }
    validate_and_guard(large_asset)
    assert large_asset["element"] == "asset"
    assert large_asset["tier"] == "rule"


def test_p2_9_guardrails_provenance_and_demotion():
    """P2.9: asset, cogs, taxes must be debits; capital requires owner name match."""
    # 1. Asset as credit -> demote
    c_asset = {"amount": 50000.0, "direction": "credit", "element": "asset", "tier": "llm"}
    validate_and_guard(c_asset)
    assert c_asset["element"] == "needs_review"
    assert c_asset["tier"] == "validator"
    assert c_asset["confidence"] == 0.0

    # 2. COGS as credit -> demote
    c_cogs = {"amount": 30000.0, "direction": "credit", "element": "cogs", "tier": "llm"}
    validate_and_guard(c_cogs)
    assert c_cogs["element"] == "needs_review"
    assert c_cogs["tier"] == "validator"

    # 3. Taxes as credit -> demote
    c_taxes = {"amount": 10000.0, "direction": "credit", "element": "taxes", "tier": "llm"}
    validate_and_guard(c_taxes)
    assert c_taxes["element"] == "needs_review"
    assert c_taxes["tier"] == "validator"

    # 4. Capital without owner name match -> demote
    config.OWNER_NAMES = ["adeola", "chukwuma"]
    cap_unmatched = {
        "amount": 1000000.0,
        "direction": "credit",
        "element": "capital",
        "tier": "llm",
        "description_norm": "deposit from random investor",
    }
    validate_and_guard(cap_unmatched)
    assert cap_unmatched["element"] == "needs_review"
    assert cap_unmatched["tier"] == "validator"

    # 5. Capital with owner name match -> remains capital
    cap_matched = {
        "amount": 1000000.0,
        "direction": "credit",
        "element": "capital",
        "tier": "llm",
        "description_norm": "director equity adeola investment",
    }
    validate_and_guard(cap_matched)
    assert cap_matched["element"] == "capital"
    assert cap_matched["tier"] == "llm"


@pytest.mark.asyncio
async def test_p2_10_few_shot_similarity_retrieval(db_session):
    """P2.10: Selects top-k overrides most similar by token overlap, dropping amount."""
    # Create statement
    stmt = models.Statement(
        filename="test_stmt.pdf",
        bank_name="Test Bank",
        currency="NGN",
        math_ok=True,
        source_hash="dummy_hash_p210",
    )
    db_session.add(stmt)
    await db_session.flush()

    # Create older relevant transaction and override (Slack -> expense)
    t1 = models.Transaction(
        statement_id=stmt.id,
        fingerprint="fp1",
        date="01/01/2026",
        amount=50000.0,
        direction="debit",
        description_raw="SLACK TECHNOLOGIES MONTHLY SUBSCRIPTION",
        description_norm="slack technologies monthly subscription",
        element="expense",
        tier="user",
        status="reviewed",
    )
    db_session.add(t1)
    await db_session.flush()

    o1 = models.Override(
        transaction_id=t1.id,
        predicted_element="needs_review",
        predicted_tier="llm",
        final_element="expense",
    )
    db_session.add(o1)

    # Create newer irrelevant transaction and override (Zenith Dividend -> income)
    t2 = models.Transaction(
        statement_id=stmt.id,
        fingerprint="fp2",
        date="02/01/2026",
        amount=100000.0,
        direction="credit",
        description_raw="ZENITH BANK ANNUAL DIVIDEND WARRANT",
        description_norm="zenith bank annual dividend warrant",
        element="income",
        tier="user",
        status="reviewed",
    )
    db_session.add(t2)
    await db_session.flush()

    o2 = models.Override(
        transaction_id=t2.id,
        predicted_element="needs_review",
        predicted_tier="llm",
        final_element="income",
    )
    db_session.add(o2)
    await db_session.commit()

    # Batch to classify containing Slack
    current_batch = [{
        "description_raw": "SLACK CLOUD CHAT",
        "description_norm": "slack cloud chat",
        "direction": "debit",
    }]

    few_shot_prompt = await get_few_shot_examples(db_session, batch=current_batch, limit=1)

    # Assert older Slack override was selected over newer Dividend override
    assert "SLACK TECHNOLOGIES" in few_shot_prompt
    assert "ZENITH BANK" not in few_shot_prompt
    # Assert amount is dropped from the line
    assert "₦" not in few_shot_prompt
    assert "50,000" not in few_shot_prompt
    assert "-> EXPENSE" in few_shot_prompt
