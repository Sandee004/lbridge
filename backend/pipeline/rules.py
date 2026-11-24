import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import models

# Standard seed rules with rich Nigerian & global merchant coverage
SEED_RULES = [
    # -------------------------------------------------------------
    # 1. EXPENSES (Debits only)
    # -------------------------------------------------------------
    # Bank Charges, Taxes & Levies
    {
        "pattern": r"\b(sms alert|stamp duty|maintenance fee|card fee|token renewal|commission mobile trf|vat mobile trf|cot|bank charge|fgn stamp duty)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "expense",
        "priority": 100,
    },
    # Internet & Telecommunications
    {
        "pattern": r"\b(spectranet|mtn|airtel|glo|9mobile|starlink|smile communications|fiber broadband|internet)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "expense",
        "priority": 90,
    },
    # Electricity, Power & Utilities
    {
        "pattern": r"\b(ikedc|ekedc|ibedc|aedc|eedc|buypower|prepaid token|ikeja electric|eko electricity)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "expense",
        "priority": 90,
    },
    # Fuel, Transport & Logistics
    {
        "pattern": r"\b(totalenergies|bovas|nnpc|conoil|oando|mrs petroleum|uber|bolt|taxify|gig logistics|dhl|fedex|filling station)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "expense",
        "priority": 85,
    },
    # Cloud Infrastructure & Developer SaaS
    {
        "pattern": r"\b(aws|amazon web services|google cloud|google workspace|gsuite|github|gitlab|heroku|digitalocean|slack|zoom|notion|figma|canva|mailchimp)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "expense",
        "priority": 85,
    },
    # Food, Groceries & Office Consumables
    {
        "pattern": r"\b(shoprite|choppies|just rite|spar|foodco|the place|mega chicken|dominos|mr biggs|kfc|staples|stationery|office cleaning)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "expense",
        "priority": 80,
    },

    # -------------------------------------------------------------
    # 2. INCOME (Credits only)
    # -------------------------------------------------------------
    # Fintech Payouts, POS Settlements & Gateways
    {
        "pattern": r"\b(paystack|flutterwave|moniepoint|opay|palmpay|remita|pos settlement|merchant deposit|sales payout)\b",
        "match_type": "word_regex",
        "direction": "credit",
        "element": "income",
        "priority": 95,
    },
    # Client Payments & Revenues
    {
        "pattern": r"\b(consulting fee|retainer|client payment|oct invoice|nov invoice|dec invoice|sales proceeds|services rendered)\b",
        "match_type": "word_regex",
        "direction": "credit",
        "element": "income",
        "priority": 90,
    },
    # Dividends & Interest
    {
        "pattern": r"\b(dividend|interim div|interest paid|interest received)\b",
        "match_type": "word_regex",
        "direction": "credit",
        "element": "income",
        "priority": 90,
    },

    # -------------------------------------------------------------
    # 3. ASSETS (Debits only - Long-term property & equipment)
    # -------------------------------------------------------------
    {
        "pattern": r"\b(slot systems|hp laptop|macbook pro|apple store|dell computers|office furniture|desks|office copier|equipment lease|plant and machinery)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "asset",
        "priority": 85,
    },

    # -------------------------------------------------------------
    # 4. LIABILITIES (Debits for repayments, Credits for loan proceeds)
    # -------------------------------------------------------------
    {
        "pattern": r"\b(term loan repayment|quick loan repayment|loan principal|credit card repayment|bank loan payable)\b",
        "match_type": "word_regex",
        "direction": "any",
        "element": "liability",
        "priority": 90,
    },

    # -------------------------------------------------------------
    # 5. CAPITAL (Equity contributions and owner drawings)
    # -------------------------------------------------------------
    {
        "pattern": r"\b(director equity|owner injection|capital injection|share capital)\b",
        "match_type": "word_regex",
        "direction": "credit",
        "element": "capital",
        "priority": 95,
    },
    {
        "pattern": r"\b(director withdrawal|owner drawing|personal drawing)\b",
        "match_type": "word_regex",
        "direction": "debit",
        "element": "capital",
        "priority": 95,
    },
]


async def seed_default_rules(db: AsyncSession) -> int:
    """Populates the rules table with default seed rules if empty."""
    existing = await db.execute(select(models.Rule).limit(1))
    if existing.scalars().first():
        return 0

    count = 0
    for r in SEED_RULES:
        rule = models.Rule(
            pattern=r["pattern"],
            match_type=r.get("match_type", "word_regex"),
            direction=r.get("direction", "any"),
            element=r["element"],
            priority=r.get("priority", 10),
            source="seed",
            hit_count=0,
            active=True,
        )
        db.add(rule)
        count += 1

    await db.commit()
    return count


def match_single_rule(description_norm: str, direction: str, rule: models.Rule) -> bool:
    """Checks if a normalized transaction description and direction match a rule."""
    if not rule.active:
        return False

    # 1. Direction check
    if rule.direction != "any" and rule.direction != direction:
        return False

    # 2. Pattern check
    pattern = rule.pattern
    if rule.match_type == "exact_counterparty":
        return pattern.lower() in description_norm
    else:
        # word_regex or standard regex
        try:
            return bool(re.search(pattern, description_norm, re.IGNORECASE))
        except re.error:
            return pattern.lower() in description_norm


async def apply_rules_to_transactions(
    transactions: List[Dict[str, Any]],
    db: AsyncSession
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Applies active database rules to a list of transaction dictionaries.
    Returns:
        (matched_transactions, unmatched_transactions)
    Updates rule hit counts in SQLite.
    """
    # Fetch all active rules ordered by priority descending
    rules_res = await db.execute(
        select(models.Rule).where(models.Rule.active == True).order_by(models.Rule.priority.desc(), models.Rule.id.asc())
    )
    rules: List[models.Rule] = list(rules_res.scalars().all())

    matched: List[Dict[str, Any]] = []
    unmatched: List[Dict[str, Any]] = []
    rule_hits: Dict[int, int] = {}

    for txn in transactions:
        desc_norm = txn.get("description_norm", "").lower()
        direction = txn.get("direction", "debit")

        found_match = False
        for r in rules:
            if match_single_rule(desc_norm, direction, r):
                txn["element"] = r.element
                txn["tier"] = "rule"
                txn["rule_id"] = r.id
                txn["confidence"] = 1.0
                txn["reason"] = f"Tier-1 Rule hit: {r.element.upper()} on '{r.pattern[:35]}'"
                matched.append(txn)
                rule_hits[r.id] = rule_hits.get(r.id, 0) + 1
                found_match = True
                break

        if not found_match:
            unmatched.append(txn)

    # Batch update hit counts
    for rule_id, hits in rule_hits.items():
        await db.execute(
            update(models.Rule)
            .where(models.Rule.id == rule_id)
            .values(hit_count=models.Rule.hit_count + hits)
        )
    if rule_hits:
        await db.commit()

    return matched, unmatched
