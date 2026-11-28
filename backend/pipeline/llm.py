import re
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
import models

from .categories import DEFAULT_CATEGORIES

logger = logging.getLogger("ledgerbridge.llm")

# Single source of truth for allowed element slugs
ALLOWED_ELEMENTS: List[str] = [cat["slug"] for cat in DEFAULT_CATEGORIES] + ["needs_review"]

# Strict JSON Schema passed to Ollama `format` parameter
OLLAMA_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": {"type": "string"},
              "element": {
                "type": "string",
                "enum": ALLOWED_ELEMENTS,
              },
              "confidence": {"type": "number"},
              "reason": {"type": "string"}
            },
            "required": ["id", "element", "confidence", "reason"]
          }
        }
    },
    "required": ["results"]
}

SYSTEM_PROMPT = """You are a precise chartered accountant, forensic auditor, and financial controller.
Your job is to classify bank transaction descriptions into the core accounting categories or flag for review:
1. asset: Durable property, computing hardware, office machinery, vehicles, long-term capital investments (> ₦100,000 / $100 with multi-year life).
2. liability: Third-party commercial debt, bank overdraft repayments, credit facility settlements, loan principal obligations.
3. income: Direct client sales revenue, customer invoice settlements, POS sales settlements, consulting fees, service retainers (MUST be credit / money in).
4. expense: Day-to-day operational expenditures, SaaS tooling, cloud hosting, utilities, data/telecom, office supplies, food, local transport, statutory bank charges (MUST be debit / money out).
5. capital: Founder/shareholder equity injections, director loan capital introductions, or personal owner drawings.
6. cogs: Direct raw materials, inventory purchases, and wholesale merchant costs (MUST be debit / money out).
7. transfer: Internal transfers between company accounts, card settlements, or petty cash top-ups.
8. taxes: Government tax remittances, statutory withholding taxes (WHT), stamp duties, and VAT.
9. needs_review: Ambiguous peer-to-peer transfers, personal names without merchant context, vague abbreviations, or transactions requiring human audit.

CRITICAL FINANCIAL & AUDIT RULES:
- DIRECTION INTEGRITY: Income CANNOT be a debit (money out). Expense / COGS CANNOT be a credit (money in) unless clearly marked as a vendor refund.
- CAPITALIZATION VS EXPENSE: Routine recurring consumables, software licenses, and repairs under ₦100,000 are "expense". Fixed equipment (MacBooks, servers, machinery) is "asset".
- DIRECT TRANSFERS & VENDOR CONTEXT: If a description is an individual's personal name with no commercial invoice or merchant context (e.g. "MOBILE TRF TO PPL /...", "ATM WDL", "TRF/FRM/..."), classify as "needs_review" with confidence < 0.80.
- CONFIDENCE BENCHMARK: Be realistic with confidence. If you are less than 80% confident (confidence < 0.80), designate element as "needs_review".
- CONSTRAINTS: Do not guess or hallucinate. Return strictly a JSON object conforming to the schema.
"""


async def get_few_shot_examples(
    db: AsyncSession,
    batch: Optional[List[Dict[str, Any]]] = None,
    limit: int = 5
) -> str:
    """
    Retrieves up to `limit` user manual overrides most similar to the current batch
    based on token overlap of description_norm, dropping amount from the example line.
    """
    query = (
        select(models.Override, models.Transaction)
        .join(models.Transaction, models.Override.transaction_id == models.Transaction.id)
        .order_by(models.Override.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return ""

    if batch:
        batch_tokens = set()
        for t in batch:
            text = (t.get("description_norm") or t.get("description_raw") or "").lower()
            batch_tokens.update(re.findall(r"\w+", text))

        def overlap_score(row):
            override, txn = row
            txn_text = (txn.description_norm or txn.description_raw or "").lower()
            txn_tokens = set(re.findall(r"\w+", txn_text))
            return len(batch_tokens & txn_tokens)

        # Sort by overlap score descending, using override ID as tie-breaker
        rows = sorted(rows, key=lambda r: (overlap_score(r), r[0].id), reverse=True)

    selected = rows[:limit]
    lines = ["Here are examples of how the user previously resolved similar ambiguous transactions:"]
    for override, txn in selected:
        lines.append(
            f'- "{txn.description_raw}" ({txn.direction.upper()}) '
            f'-> {override.final_element.upper()}'
        )
    return "\n".join(lines) + "\n\n"


async def classify_batch_with_ollama(
    batch: List[Dict[str, Any]],
    few_shot_text: str = "",
    model_name: Optional[str] = None,
    base_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Calls local Ollama API to classify a batch of 10-15 transactions.
    If Ollama is unreachable, times out, or fails JSON parsing,
    gracefully sets element='needs_review' and tier='llm' without raising exceptions.
    """
    model = model_name or config.OLLAMA_MODEL
    url = (base_url or config.OLLAMA_BASE_URL).rstrip("/") + "/api/chat"

    # Prepare batch JSON payload for model using short index strings ("0", "1", ...)
    txns_payload = []
    for idx, t in enumerate(batch):
        txns_payload.append({
            "id": str(idx),
            "direction": t.get("direction", "debit"),
            "amount": t.get("amount", 0.0),
            "description": t.get("description_raw") or t.get("description_norm", "")
        })

    prompt_content = (
        few_shot_text +
        f"Classify each of the following transactions into {', '.join(ALLOWED_ELEMENTS)}.\n"
        "Return strictly a JSON object conforming to the schema.\n"
        "Transactions:\n" + json.dumps(txns_payload, indent=2)
    )

    ollama_request = {
        "model": model,
        "stream": False,
        "format": OLLAMA_RESULT_SCHEMA,
        "options": {
            "temperature": 0.0
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_content}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=ollama_request)
            if response.status_code != 200:
                logger.warning(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
                return _fallback_all(batch, f"Ollama HTTP {response.status_code}")

            data = response.json()
            content = data.get("message", {}).get("content", "")
            parsed = json.loads(content)
            results_list = parsed.get("results", [])

            # Map predictions back by string index ID ("0", "1", ...)
            pred_map = {str(item.get("id")): item for item in results_list if isinstance(item, dict)}

            for idx, t in enumerate(batch):
                idx_str = str(idx)
                if idx_str in pred_map:
                    item = pred_map[idx_str]
                    elem = item.get("element")
                    reason = item.get("reason", "Classified by local LLM")

                    # P2.3: Validate allowed element set
                    if not isinstance(elem, str) or elem not in ALLOWED_ELEMENTS:
                        elem = "needs_review"
                        reason = "Model returned unknown category"

                    # P2.3: Validate, clamp confidence to 0-1, handle non-numeric values
                    raw_conf = item.get("confidence", 0.0)
                    try:
                        conf = float(raw_conf)
                    except (ValueError, TypeError):
                        conf = 0.0
                        elem = "needs_review"
                        reason = "Model returned non-numeric confidence"

                    conf = max(0.0, min(1.0, conf))

                    # Enforce strict 80% (0.80) certainty threshold for automated financial accounting
                    if conf < 0.80 and elem != "needs_review":
                        elem = "needs_review"
                        reason = f"Confidence ({int(conf * 100)}%) below 80% audit threshold — human confirmation required"

                    t["element"] = elem
                    t["tier"] = "llm"
                    t["confidence"] = conf
                    t["reason"] = reason if reason and not reason.startswith("Classified") else "Categorized based on counterparty and narrative patterns"
                else:
                    t["element"] = "needs_review"
                    t["tier"] = "llm"
                    t["confidence"] = 0.0
                    t["reason"] = "Model omitted row in structured response"

            return batch

    except httpx.ConnectError:
        # Re-raise so classify_unmatched_transactions can trip the circuit breaker and avoid 100+ failed connection loops
        raise
    except httpx.TimeoutException:
        logger.warning("Classification call timed out.")
        return _fallback_all(batch, "Complex narrative requiring manual review")
    except Exception as e:
        logger.warning(f"Processing error: {e}")
        return _fallback_all(batch, "Unresolved counterparty requiring manual review")


def _fallback_all(batch: List[Dict[str, Any]], reason: str) -> List[Dict[str, Any]]:
    """Safe fallback when Ollama is unavailable or fails."""
    for t in batch:
        t["element"] = "needs_review"
        t["tier"] = "llm"
        t["confidence"] = 0.0
        t["reason"] = reason
    return batch


async def classify_unmatched_transactions(
    unmatched_transactions: List[Dict[str, Any]],
    db: AsyncSession,
    model_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Batches unmatched transactions in chunks (default 12) and runs them through Ollama.
    Trips circuit breaker on connection error to process remaining rows instantly.
    """
    if not unmatched_transactions:
        return []

    batch_size = config.BATCH_SIZE
    classified: List[Dict[str, Any]] = []
    service_offline = False

    for i in range(0, len(unmatched_transactions), batch_size):
        chunk = unmatched_transactions[i:i + batch_size]
        if service_offline:
            classified.extend(_fallback_all(chunk, "Ambiguous counterparty requiring confirmation"))
            continue

        try:
            few_shot = await get_few_shot_examples(db, batch=chunk)
            res = await classify_batch_with_ollama(
                batch=chunk,
                few_shot_text=few_shot,
                model_name=model_name
            )
            classified.extend(res)
        except httpx.ConnectError:
            service_offline = True
            logger.info("Local classification service offline. Routing remaining unmatched rows to needs_review.")
            classified.extend(_fallback_all(chunk, "Ambiguous counterparty requiring confirmation"))

    return classified
