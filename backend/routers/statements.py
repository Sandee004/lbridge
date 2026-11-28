import hashlib
import os
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Statement, Transaction, User
from utils import get_current_user
from parser import parse_pdf_statement, parse_excel_or_csv_statement
from pipeline import run_classification_pipeline
from pipeline.export import export_flat_csv, export_journal_csv, export_excel_workbook
from schemas import StatementResponse, UploadSummaryResponse

router = APIRouter(tags=["statements"])


async def process_statement_bytes(content: bytes, filename: str, db: AsyncSession) -> UploadSummaryResponse:
    """Core statement ingestion and classification logic shared between file upload and sample loading."""
    ext = os.path.splitext(filename)[1].lower()
    supported_exts = [".pdf", ".xlsx", ".xls", ".csv"]
    if ext not in supported_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. LedgerBridge supports: {', '.join(supported_exts)}.",
        )

    # 0. Check if this exact file content was already uploaded with transactions
    source_hash = hashlib.sha256(content).hexdigest()
    stmt_match = await db.execute(
        select(Statement).options(selectinload(Statement.transactions)).where(Statement.source_hash == source_hash)
    )
    existing_file_stmt = stmt_match.scalars().first()
    if existing_file_stmt and len(existing_file_stmt.transactions) > 0:
        return UploadSummaryResponse(
            statement_id=existing_file_stmt.id,
            filename=existing_file_stmt.filename,
            bank_name=existing_file_stmt.bank_name,
            currency=existing_file_stmt.currency,
            math_ok=existing_file_stmt.math_ok,
            math_error_detail=existing_file_stmt.math_error_detail,
            opening_balance=existing_file_stmt.opening_balance,
            closing_balance=existing_file_stmt.closing_balance,
            total_credits=existing_file_stmt.total_credits,
            total_debits=existing_file_stmt.total_debits,
            total_rows_parsed=len(existing_file_stmt.transactions),
            new_rows_stored=0,
            duplicates_skipped=len(existing_file_stmt.transactions),
            rules_count=0,
            llm_count=0,
            needs_review_count=sum(1 for t in existing_file_stmt.transactions if t.element == "needs_review"),
            message=f"Statement '{existing_file_stmt.filename}' is already active with {len(existing_file_stmt.transactions)} transactions.",
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
        source_hash=source_hash,
    )
    db.add(statement)
    await db.flush()

    raw_txns = parsed_data.get("transactions", [])

    # P2.5: Deduplicate within the same upload first
    seen_fps = set()
    unique_txns = []
    intra_file_duplicates = 0
    for t in raw_txns:
        fp = t["fingerprint"]
        if fp in seen_fps:
            intra_file_duplicates += 1
        else:
            seen_fps.add(fp)
            unique_txns.append(t)

    # P2.5: Check existing fingerprints in SQLite in ONE query before running classification pipeline
    all_fps = list(seen_fps)
    existing_fps = set()
    if all_fps:
        stmt_fps = await db.execute(select(Transaction.fingerprint).where(Transaction.fingerprint.in_(all_fps)))
        existing_fps = set(stmt_fps.scalars().all())

    new_txns = [t for t in unique_txns if t["fingerprint"] not in existing_fps]
    duplicates_skipped = intra_file_duplicates + len(existing_fps)

    # If no new transactions to classify because all exist in database:
    if not new_txns and raw_txns:
        await db.rollback()
        sample_fp = raw_txns[0]["fingerprint"]
        match = await db.execute(select(Transaction.statement_id).where(Transaction.fingerprint == sample_fp))
        s_id = match.scalars().first()
        existing_stmt = None
        if s_id:
            s_res = await db.execute(select(Statement).options(selectinload(Statement.transactions)).where(Statement.id == s_id))
            existing_stmt = s_res.scalars().first()

        if existing_stmt:
            return UploadSummaryResponse(
                statement_id=existing_stmt.id,
                filename=existing_stmt.filename,
                bank_name=existing_stmt.bank_name,
                currency=existing_stmt.currency,
                math_ok=existing_stmt.math_ok,
                math_error_detail=existing_stmt.math_error_detail,
                opening_balance=existing_stmt.opening_balance,
                closing_balance=existing_stmt.closing_balance,
                total_credits=existing_stmt.total_credits,
                total_debits=existing_stmt.total_debits,
                total_rows_parsed=len(raw_txns),
                new_rows_stored=0,
                duplicates_skipped=duplicates_skipped,
                rules_count=0,
                llm_count=0,
                needs_review_count=sum(1 for t in existing_stmt.transactions if t.element == "needs_review"),
                message=f"All {duplicates_skipped} transactions are already present in '{existing_stmt.filename}'. Re-selected existing statement.",
            )

    # 2. Run Classification Pipeline ONLY on new, deduplicated rows (Tier 1: Rules -> Tier 2: Ollama -> Guardrails)
    classified_txns = await run_classification_pipeline(new_txns, db)

    # 3. Persist new transactions
    new_rows_stored = 0
    rules_count = 0
    llm_count = 0
    needs_review_count = 0

    for item in classified_txns:
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
            fingerprint=item["fingerprint"],
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
    Verifies statement math, runs the multi-tier classification funnel,
    deduplicates rows against SQLite, and stores records in the database.
    """
    filename = file.filename or "statement.pdf"
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )
    return await process_statement_bytes(content, filename, db)


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

    return await process_statement_bytes(content, filename, db)


@router.get("", response_model=List[StatementResponse])
@router.get("/", response_model=List[StatementResponse], include_in_schema=False)
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
        if len(s.transactions) == 0:
            continue
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


@router.get("/{statement_id}/export")
async def export_statement(
    statement_id: str,
    format: str = "csv",
    mode: str = "flat",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    P4.1 - P4.4: Export statement transactions as CSV (flat or journal) or XLSX.
    """
    fmt = format.lower()
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{format}'. Supported formats: 'csv', 'xlsx'.",
        )

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

    safe_name = s.bank_name.replace(" ", "_")

    if fmt == "csv":
        m = mode.lower()
        if m not in ("flat", "journal"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported mode '{mode}'. Supported modes: 'flat', 'journal'.",
            )
        if m == "journal":
            try:
                content = export_journal_csv(s.transactions)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e),
                )
            filename = f"{safe_name}_{s.id[:8]}_journal.csv"
        else:
            content = export_flat_csv(s.transactions)
            filename = f"{safe_name}_{s.id[:8]}_clean_ledger.csv"

        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # XLSX format
    content_bytes = export_excel_workbook(s.transactions)
    filename = f"{safe_name}_{s.id[:8]}_audit.xlsx"
    return Response(
        content=content_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
