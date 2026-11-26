import datetime
import re
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import models

def slugify(text: str) -> str:
    """Generate a clean slug for category identifiers."""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\s-]", "", cleaned)
    return re.sub(r"[-\s]+", "_", cleaned)

DEFAULT_CATEGORIES: List[Dict[str, Any]] = [
    {
        "name": "Assets",
        "slug": "asset",
        "direction": "debit",
        "color": "sky",
        "description": "Long-term equipment, vehicles, cash accounts, and business property.",
        "is_system": True,
    },
    {
        "name": "Liabilities",
        "slug": "liability",
        "direction": "any",
        "color": "purple",
        "description": "Loans, credit card balances, mortgages, and debts owed to third parties.",
        "is_system": True,
    },
    {
        "name": "Income",
        "slug": "income",
        "direction": "credit",
        "color": "emerald",
        "description": "Customer payments, consulting revenues, product sales, and trading inflows.",
        "is_system": True,
    },
    {
        "name": "Expenses",
        "slug": "expense",
        "direction": "debit",
        "color": "rose",
        "description": "Operating costs, SaaS subscriptions, utilities, rent, and overheads.",
        "is_system": True,
    },
    {
        "name": "Capital",
        "slug": "capital",
        "direction": "any",
        "color": "teal",
        "description": "Owner contributions, share equity, and personal drawings.",
        "is_system": True,
    },
    {
        "name": "Cost of Goods Sold",
        "slug": "cogs",
        "direction": "debit",
        "color": "amber",
        "description": "Direct costs of materials, supplier inventory, and wholesale goods.",
        "is_system": True,
    },
    {
        "name": "Internal Transfer",
        "slug": "transfer",
        "direction": "any",
        "color": "indigo",
        "description": "Transfers between own bank accounts, card repayments, or petty cash.",
        "is_system": True,
    },
    {
        "name": "Taxes & VAT",
        "slug": "taxes",
        "direction": "debit",
        "color": "orange",
        "description": "Government tax remittances, withholding taxes, stamp duties, and VAT.",
        "is_system": True,
    },
]


async def seed_default_categories(db: AsyncSession) -> None:
    """Ensure standard accounting categories are present in the database."""
    res = await db.execute(select(models.Category))
    existing = {cat.slug: cat for cat in res.scalars().all()}

    new_cats = []
    for item in DEFAULT_CATEGORIES:
        if item["slug"] not in existing:
            cat = models.Category(
                name=item["name"],
                slug=item["slug"],
                direction=item["direction"],
                color=item["color"],
                description=item["description"],
                is_system=item["is_system"],
            )
            new_cats.append(cat)

    if new_cats:
        db.add_all(new_cats)
        await db.commit()
