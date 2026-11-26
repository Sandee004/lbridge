from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Rule, User
from utils import get_current_user
from schemas import RuleCreateRequest, RuleResponse

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=List[RuleResponse])
async def list_rules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all persistent classification rules ordered by priority."""
    result = await db.execute(select(Rule).order_by(Rule.priority.desc(), Rule.hit_count.desc()))
    return result.scalars().all()


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
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
