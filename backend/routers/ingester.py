import os
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Override, Rule, Statement, Transaction, User
from utils import get_current_user
from parser import parse_pdf_statement, parse_excel_or_csv_statement
from pipeline import run_classification_pipeline
from schemas import (
    RuleCreateRequest,
    RuleResponse,
    StatementResponse,
    TransactionResponse,
    TransactionUpdateRequest,
    UploadSummaryResponse,
)

router = APIRouter()


async def _process_statement_bytes(content: bytes, filename: str, db: AsyncSession) -> UploadSummaryResponse:
    """Core statement ingestion and classification logic shared between file upload and sample loading."""
    ext = os.path.splitext(filename)[1].lower()
    supported_exts = [".pdf", ".xlsx", ".xls", ".csv"]
    if ext not in supported_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. LedgerBridge supports: {', '.join(supported_exts)}.",
        )

    try:
        if ext == ".pdf":
            parsed_data = parse_pdf_statement(content, filename=filename)
        else:
            parsed_data = parse_excel_or_csv_statement(content, filename=filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse bank statement file: {str(e)}",
        )

    # 1. Create Statement record
    statement = Statement(
        filename=parsed_data["filename"],
        bank_name=parsed_data["bank_name"],
        currency=parsed_data.get("currency", "NGN"),
        period_start=parsed_data["period_start"],
        period_end=parsed_data["period_end"],
        opening_balance=parsed_data["opening_balance"],
        closing_balance=parsed_data["closing_balance"],
        total_credits=parsed_data["total_credits"],
        total_debits=parsed_data["total_debits"],
        math_ok=parsed_data["math_ok"],
        math_error_detail=parsed_data["math_error_detail"],
    )
    db.add(statement)
    await db.flush()

    # 2. Run Classification Pipeline (Tier 1: Rules -> Tier 2: Ollama Qwen -> Guardrails)
    raw_txns = parsed_data.get("transactions", [])
    classified_txns = await run_classification_pipeline(raw_txns, db)

    # 3. Deduplicate transactions by SHA-256 fingerprint & persist
    new_rows_stored = 0
    duplicates_skipped = 0
    rules_count = 0
    llm_count = 0
    needs_review_count = 0

    for item in classified_txns:
        fp = item["fingerprint"]
        existing = await db.execute(select(Transaction.id).where(Transaction.fingerprint == fp))
        if existing.scalars().first():
            duplicates_skipped += 1
            continue

        tier = item.get("tier", "ingestion")
        element = item.get("element", "needs_review")

        if tier == "rule":
            rules_count += 1
        elif tier == "llm":
            llm_count += 1

        if element == "needs_review":
            needs_review_count += 1

        txn = Transaction(
            statement_id=statement.id,
            fingerprint=fp,
            date=item["date"],
            value_date=item.get("value_date", item["date"]),
            amount=item["amount"],
            direction=item["direction"],
            description_raw=item["description_raw"],
            description_norm=item["description_norm"],
            balance=item["balance"],
            element=element,
            tier=tier,
            rule_id=item.get("rule_id"),
            confidence=item.get("confidence", 0.0),
            reason=item.get("reason", "Bank statement row"),
            status="reviewed" if element != "needs_review" and tier == "rule" else "auto",
        )
        db.add(txn)
        new_rows_stored += 1

    await db.commit()
    await db.refresh(statement)

    msg = (
        f"Parsed {parsed_data['transaction_count']} rows: "
        f"{rules_count} matched by rules, {llm_count} processed by AI, "
        f"{needs_review_count} flagged for review. "
        f"Stored {new_rows_stored} new rows ({duplicates_skipped} duplicates skipped). "
    )
    if parsed_data["math_ok"]:
        msg += "Statement arithmetic verified successfully."
    else:
        msg += f"Warning: {parsed_data['math_error_detail']}"

    return UploadSummaryResponse(
        statement_id=statement.id,
        filename=statement.filename,
        bank_name=statement.bank_name,
        currency=statement.currency,
        math_ok=statement.math_ok,
        math_error_detail=statement.math_error_detail,
        opening_balance=statement.opening_balance,
        closing_balance=statement.closing_balance,
        total_credits=statement.total_credits,
        total_debits=statement.total_debits,
        total_rows_parsed=parsed_data["transaction_count"],
        new_rows_stored=new_rows_stored,
        duplicates_skipped=duplicates_skipped,
        rules_count=rules_count,
        llm_count=llm_count,
        needs_review_count=needs_review_count,
        message=msg,
    )


@router.post("/upload", response_model=UploadSummaryResponse, status_code=status.HTTP_201_CREATED)
async def upload_statement(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and parse a bank statement (PDF, Excel .xlsx/.xls, or CSV).
    Verifies statement math, runs the multi-tier classification funnel (Rules -> Ollama Qwen),
    deduplicates rows against SQLite, and stores records in the database.
    """
    filename = file.filename or "statement.pdf"
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    return await _process_statement_bytes(content, filename, db)


@router.post("/sample/{sample_name}", response_model=UploadSummaryResponse)
async def load_sample_statement(
    sample_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick load built-in sample statements (Access Bank PDF or Demo Excel) for frictionless testing."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sample_name == "access-bank-pdf":
        target_name = "access_bank_statement.pdf"
        filename = "Access_Bank_Oct2026.pdf"
    elif sample_name == "demo-excel":
        target_name = "demo_statement.xlsx"
        filename = "Demo_Corporate_Statement.xlsx"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid sample name. Choose 'access-bank-pdf' or 'demo-excel'.",
        )

    possible_paths = [
        os.path.join(base_dir, "tests", "fixtures", target_name),
        os.path.join(base_dir, target_name),
    ]
    file_path = next((p for p in possible_paths if os.path.exists(p)), None)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sample file {target_name} not found.")

    with open(file_path, "rb") as f:
        content = f.read()

    return await _process_statement_bytes(content, filename, db)


# ------------------------------
# Rules Management Endpoints
# ------------------------------

@router.get("/rules", response_model=List[RuleResponse])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all persistent classification rules ordered by priority."""
    result = await db.execute(select(Rule).order_by(Rule.priority.desc(), Rule.hit_count.desc()))
    return result.scalars().all()


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RuleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new merchant regex or counterparty classification rule."""
    pattern = rule_data.pattern.strip().upper()
    existing = await db.execute(select(Rule).where(Rule.pattern == pattern))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule with pattern '{pattern}' already exists.",
        )

    rule = Rule(
        pattern=pattern,
        match_type=rule_data.match_type,
        direction=rule_data.direction,
        element=rule_data.element.lower().replace(" ", "_"),
        priority=rule_data.priority,
        source="user",
        active=True,
        hit_count=0,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a classification rule by ID."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return None


# ------------------------------
# Transaction Review & Override Endpoints
# ------------------------------

@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: str,
    update_data: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a transaction's classified element (user review resolution).
    Creates an Override record for LLM few-shot learning and optionally persists a new Rule.
    """
    query = select(Transaction).where(Transaction.id == transaction_id)
    result = await db.execute(query)
    txn = result.scalars().first()
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    old_element = txn.element
    old_tier = txn.tier

    # Normalize element name (e.g. 'Assets' -> 'asset', 'Needs Review' -> 'needs_review')
    target_element = update_data.element.lower().replace(" ", "_")
    if target_element.endswith("s") and target_element in ["assets", "liabilities", "expenses"]:
        target_element = target_element[:-1]  # 'asset', 'liability', 'expense'

    txn.element = target_element
    txn.tier = "user"
    txn.status = "reviewed"
    txn.confidence = 1.0

    # Record Override for few-shot learning
    override = Override(
        transaction_id=txn.id,
        predicted_element=old_element,
        predicted_tier=old_tier,
        final_element=target_element,
    )
    db.add(override)

    # If requested, save rule
    if update_data.create_rule and update_data.rule_pattern:
        pattern = update_data.rule_pattern.strip().upper()
        if pattern:
            existing_rule = await db.execute(select(Rule).where(Rule.pattern == pattern))
            rule_obj = existing_rule.scalars().first()
            if not rule_obj:
                new_rule = Rule(
                    pattern=pattern,
                    match_type="word_regex",
                    direction=update_data.rule_direction or "any",
                    element=target_element,
                    priority=50,
                    source="user",
                    hit_count=1,
                    active=True,
                )
                db.add(new_rule)
                await db.flush()
                txn.rule_id = new_rule.id
            else:
                rule_obj.element = target_element
                rule_obj.hit_count += 1
                txn.rule_id = rule_obj.id

    await db.commit()
    await db.refresh(txn)
    return txn


# ------------------------------
# Statement Query & Delete Endpoints
# ------------------------------

@router.get("", response_model=List[StatementResponse])
async def list_statements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all uploaded statements with their transactions."""
    query = (
        select(Statement)
        .options(selectinload(Statement.transactions))
        .order_by(Statement.created_at.desc())
    )
    result = await db.execute(query)
    statements = result.scalars().all()

    response = []
    for s in statements:
        response.append(
            StatementResponse(
                id=s.id,
                filename=s.filename,
                bank_name=s.bank_name,
                currency=s.currency,
                period_start=s.period_start,
                period_end=s.period_end,
                opening_balance=s.opening_balance,
                closing_balance=s.closing_balance,
                total_credits=s.total_credits,
                total_debits=s.total_debits,
                math_ok=s.math_ok,
                math_error_detail=s.math_error_detail,
                transaction_count=len(s.transactions),
                transactions=s.transactions,
            )
        )
    return response


@router.get("/{statement_id}", response_model=StatementResponse)
async def get_statement(
    statement_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific statement by ID along with its transactions."""
    query = (
        select(Statement)
        .options(selectinload(Statement.transactions))
        .where(Statement.id == statement_id)
    )
    result = await db.execute(query)
    s = result.scalars().first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found",
        )

    return StatementResponse(
        id=s.id,
        filename=s.filename,
        bank_name=s.bank_name,
        currency=s.currency,
        period_start=s.period_start,
        period_end=s.period_end,
        opening_balance=s.opening_balance,
        closing_balance=s.closing_balance,
        total_credits=s.total_credits,
        total_debits=s.total_debits,
        math_ok=s.math_ok,
        math_error_detail=s.math_error_detail,
        transaction_count=len(s.transactions),
        transactions=s.transactions,
    )


@router.delete("/{statement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_statement(
    statement_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a statement and all its transactions."""
    result = await db.execute(select(Statement).where(Statement.id == statement_id))
    s = result.scalars().first()
    if not s:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found",
        )
    await db.delete(s)
    await db.commit()
    return None
