import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Category, Rule, User
from utils import get_current_user
from schemas import RuleCreateRequest, RuleResponse
from pipeline.rules import seed_default_rules

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=List[RuleResponse])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all persistent classification rules ordered by priority."""
    await seed_default_rules(db)
    result = await db.execute(select(Rule).order_by(Rule.priority.desc(), Rule.hit_count.desc()))
    return result.scalars().all()


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RuleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new merchant regex or counterparty classification rule."""
    raw_pattern = rule_data.pattern.strip()
    if not raw_pattern:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rule pattern cannot be empty.")

    # P2.6: Wrap in \b...\b with re.escape if word_regex and not already wrapped
    if rule_data.match_type == "word_regex" and not (raw_pattern.startswith(r"\b") and raw_pattern.endswith(r"\b")):
        pattern = rf"\b{re.escape(raw_pattern.upper())}\b"
    else:
        pattern = raw_pattern.upper()

    target_element = rule_data.element.lower().replace(" ", "_")
    if target_element.endswith("s") and target_element in ["assets", "liabilities", "expenses"]:
        target_element = target_element[:-1]

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

    direction = rule_data.direction or "any"
    # P2.6: Lookup must match on (pattern, direction)
    existing = await db.execute(select(Rule).where(Rule.pattern == pattern, Rule.direction == direction))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule with pattern '{pattern}' and direction '{direction}' already exists.",
        )

    priority = rule_data.priority if rule_data.priority > 100 else 200

    rule = Rule(
        pattern=pattern,
        match_type=rule_data.match_type,
        direction=direction,
        element=target_element,
        priority=priority,
        source="user",
        active=True,
        hit_count=0,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
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
