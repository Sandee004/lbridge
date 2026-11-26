from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Override, Rule, Transaction, User
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
