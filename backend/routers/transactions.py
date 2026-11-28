import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Category, Override, Rule, Transaction, User
from utils import get_current_user
from schemas import TransactionResponse, TransactionUpdateRequest

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.patch("/{transaction_id}", response_model=TransactionResponse)
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

    # Ensure categories are seeded
    from pipeline.categories import seed_default_categories
    await seed_default_categories(db)

    # P2.6: Validate element against categories table
    if target_element != "needs_review":
        cat_match = await db.execute(select(Category.slug).where(Category.slug == target_element))
        if not cat_match.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid accounting element '{target_element}'. Must be one of the registered categories.",
            )

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

    # P2.6: If requested, save rule with priority=200, escaped word boundaries, and (pattern, direction) match
    if update_data.create_rule and update_data.rule_pattern:
        raw_pattern = update_data.rule_pattern.strip()
        if raw_pattern:
            escaped_pattern = rf"\b{re.escape(raw_pattern)}\b"
            direction = update_data.rule_direction or txn.direction or "any"
            existing_rule = await db.execute(
                select(Rule).where(Rule.pattern == escaped_pattern, Rule.direction == direction)
            )
            rule_obj = existing_rule.scalars().first()
            if not rule_obj:
                new_rule = Rule(
                    pattern=escaped_pattern,
                    match_type="word_regex",
                    direction=direction,
                    element=target_element,
                    priority=200,  # User rules get higher priority than seed rules (80-100)
                    source="user",
                    hit_count=1,
                    active=True,
                )
                db.add(new_rule)
                await db.flush()
                txn.rule_id = new_rule.id
            else:
                rule_obj.element = target_element
                rule_obj.priority = 200
                rule_obj.hit_count += 1
                txn.rule_id = rule_obj.id

    await db.commit()
    await db.refresh(txn)
    return txn
