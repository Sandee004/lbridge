from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from .rules import seed_default_rules, apply_rules_to_transactions
from .llm import classify_unmatched_transactions
from .categories import seed_default_categories


def validate_and_guard(txn: Dict[str, Any]) -> None:
    """
    Applies deterministic sanity guardrails to prevent accounting contradictions:
    - Income CANNOT be a debit.
    - Expense / COGS CANNOT be a credit (might be an expense refund, but not direct cost).
    - Amount must be > 0.
    """
    direction = txn.get("direction", "debit")
    element = txn.get("element", "needs_review")
    amount = txn.get("amount", 0.0)

    if amount <= 0:
        txn["element"] = "needs_review"
        txn["reason"] = "Sanity check failed: Transaction amount is zero or negative."
        return

    elem_lower = str(element).lower().replace(" ", "_")
    if elem_lower == "income" and direction == "debit":
        txn["element"] = "needs_review"
        txn["reason"] = "Guardrail: Income cannot be a debit (money out). Demoted to Needs Review."
    elif elem_lower in ["expense", "cogs"] and direction == "credit":
        txn["element"] = "needs_review"
        txn["reason"] = f"Guardrail: {element} cannot be a credit (money in) — possible refund. Demoted to Needs Review."


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
