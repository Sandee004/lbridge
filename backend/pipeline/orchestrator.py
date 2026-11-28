from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

import config
from .rules import seed_default_rules, apply_rules_to_transactions
from .llm import classify_unmatched_transactions
from .categories import seed_default_categories


def validate_and_guard(txn: Dict[str, Any]) -> None:
    """
    Applies deterministic sanity guardrails to prevent accounting contradictions:
    - Amount must be > 0.
    - Income CANNOT be a debit.
    - Asset, COGS, Taxes MUST be debits (cannot be credit).
    - Expense CANNOT be a credit.
    - Capital requires a configured owner name match; if unset or unmatched, demote to needs_review.
    - Asset below CAPITALIZATION_THRESHOLD is demoted to needs_review (policy chosen for audit safety).
    - When demoting, set tier="validator", keep original prediction in reason, set confidence=0.0.
    """
    direction = txn.get("direction", "debit")
    element = txn.get("element", "needs_review")
    orig_tier = txn.get("tier", "ingestion")
    amount = txn.get("amount", 0.0)
    desc_norm = (txn.get("description_norm") or txn.get("description_raw") or "").lower()

    def demote(msg: str):
        txn["element"] = "needs_review"
        txn["tier"] = "validator"
        txn["confidence"] = 0.0
        txn["reason"] = f"Guardrail: {msg} (Original prediction: {element} via {orig_tier})"

    if amount <= 0:
        demote("Transaction amount is zero or negative")
        return

    elem_lower = str(element).lower().replace(" ", "_")

    # 1. Direction guardrails
    if elem_lower == "income" and direction == "debit":
        demote("Income cannot be a debit (money out)")
        return
    elif elem_lower in ["expense", "cogs", "asset", "taxes"] and direction == "credit":
        demote(f"{element.capitalize()} cannot be a credit (money in)")
        return

    # 2. Capitalization threshold for assets (P2.8)
    if elem_lower == "asset" and amount < config.CAPITALIZATION_THRESHOLD:
        demote(f"Asset purchase amount ₦{amount:,.2f} is below capitalization threshold (₦{config.CAPITALIZATION_THRESHOLD:,.2f})")
        return

    # 3. Capital owner name verification (P2.9)
    if elem_lower == "capital":
        owner_names = getattr(config, "OWNER_NAMES", [])
        if not owner_names or not any(name in desc_norm for name in owner_names):
            demote("Capital entry requires a configured owner name match")
            return


async def run_classification_pipeline(
    transactions: List[Dict[str, Any]],
    db: AsyncSession
) -> List[Dict[str, Any]]:
    """
    Orchestrates the multi-tier classification funnel:
    1. Ensures default categories and rules are seeded.
    2. Tier-1: Fast, deterministic word-boundary regex rules (0ms, 100% precision).
    3. Tier-2: Local Ollama model (Qwen) with batching, few-shot memory, and JSON schema.
    4. Guardrails: Accounting sanity validators.
    """
    if not transactions:
        return []

    # 1. Seed categories & rules if database is fresh
    await seed_default_categories(db)
    await seed_default_rules(db)

    # 2. Tier 1: Rules & Memory
    # Add a temporary tracking index so we can restore exact original statement order
    for idx, t in enumerate(transactions):
        t["_orig_idx"] = idx

    matched_by_rules, unmatched = await apply_rules_to_transactions(transactions, db)

    # 3. Tier 2: Local Ollama (Qwen) on unmatched rows
    if unmatched:
        classified_by_llm = await classify_unmatched_transactions(unmatched, db)
    else:
        classified_by_llm = []

    # 4. Merge and restore original statement row ordering
    all_classified = matched_by_rules + classified_by_llm
    all_classified.sort(key=lambda x: x.get("_orig_idx", 0))

    # 5. Apply accounting sanity guardrails
    for txn in all_classified:
        txn.pop("_orig_idx", None)
        validate_and_guard(txn)

    return all_classified
