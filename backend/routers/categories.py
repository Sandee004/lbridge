from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Category, User
from utils import get_current_user
from pipeline.categories import seed_default_categories, slugify
from schemas import CategoryCreate, CategoryResponse

router = APIRouter()


@router.get("", response_model=List[CategoryResponse])
async def list_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all standard and custom accounting categories."""
    await seed_default_categories(db)
    result = await db.execute(select(Category).order_by(Category.is_system.desc(), Category.id.asc()))
    return result.scalars().all()


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom accounting category."""
    name = category_data.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category name cannot be empty.")

    slug = slugify(name)
    existing = await db.execute(select(Category).where((Category.name == name) | (Category.slug == slug)))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{name}' already exists.",
        )

    cat = Category(
        name=name,
        slug=slug,
        direction=category_data.direction,
        color=category_data.color,
        description=category_data.description,
        is_system=False,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom accounting category."""
    result = await db.execute(select(Category).where(Category.id == category_id))
    cat = result.scalars().first()
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    if cat.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System core categories cannot be deleted.",
        )

    await db.delete(cat)
    await db.commit()
    return None
