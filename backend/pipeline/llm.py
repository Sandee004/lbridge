import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
import models

logger = logging.getLogger("ledgerbridge.llm")

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
                "enum": ["asset", "liability", "income", "expense", "capital", "needs_review"]
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
Your job is to classify bank transaction descriptions into the 5 core accounting elements or flag for review:
1. asset: Durable property, computing hardware, office machinery, vehicles, long-term capital investments (> ₦100,000 / $100 with multi-year life).
2. liability: Third-party commercial debt, bank overdraft repayments, credit facility settlements, loan principal obligations.
3. income: Direct client sales revenue, customer invoice settlements, POS sales settlements, consulting fees, service retainers (MUST be credit / money in).
4. expense: Day-to-day operational expenditures, SaaS tooling, cloud hosting, utilities, data/telecom, office supplies, food, local transport, statutory bank charges (MUST be debit / money out).
5. capital: Founder/shareholder equity injections, director loan capital introductions, or personal owner drawings.
6. needs_review: Ambiguous peer-to-peer transfers, personal names without merchant context, vague abbreviations, or transactions requiring human audit.

CRITICAL FINANCIAL & AUDIT RULES:
- DIRECTION INTEGRITY: Income CANNOT be a debit (money out). Expense CANNOT be a credit (money in) unless clearly marked as a vendor refund.
- CAPITALIZATION VS EXPENSE: Routine recurring consumables, software licenses, and repairs under ₦100,000 are "expense". Fixed equipment (MacBooks, servers, machinery) is "asset".
- DIRECT TRANSFERS & VENDOR CONTEXT: If a description is an individual's personal name with no commercial invoice or merchant context (e.g. "MOBILE TRF TO PPL /...", "ATM WDL", "TRF/FRM/..."), classify as "needs_review" with confidence < 0.80.
- CONFIDENCE BENCHMARK: Be realistic with confidence. If you are less than 80% confident (confidence < 0.80), designate element as "needs_review".
- CONSTRAINTS: Do not guess or hallucinate. Return strictly a JSON object conforming to the schema.
"""


async def get_few_shot_examples(db: AsyncSession, limit: int = 5) -> str:
    """Retrieves up to `limit` recent user manual overrides to use as few-shot training examples."""
    query = (
        select(models.Override, models.Transaction)
        .join(models.Transaction, models.Override.transaction_id == models.Transaction.id)
        .order_by(models.Override.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return ""

    lines = ["Here are examples of how the user previously resolved similar ambiguous transactions:"]
    for override, txn in rows:
        lines.append(
            f'- "{txn.description_raw}" ({txn.direction.upper()}, ₦{txn.amount:,.2f}) '
            f'-> {override.final_element.upper()} (User corrected from {override.predicted_element or "unknown"})'
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

    # Prepare batch JSON payload for model
    txns_payload = []
    for idx, t in enumerate(batch):
        tid = str(t.get("fingerprint") or idx)
        txns_payload.append({
            "id": tid,
            "direction": t.get("direction", "debit"),
            "amount": t.get("amount", 0.0),
            "description": t.get("description_raw") or t.get("description_norm", "")
        })

    prompt_content = (
        few_shot_text +
        "Classify each of the following transactions into asset, liability, income, expense, capital, or needs_review.\n"
        "Return strictly a JSON object with this exact shape: "
        '{"results": [{"id": "...", "element": "...", "confidence": 0.85, "reason": "max 5 words"}]}\n'
        "Transactions:\n" + json.dumps(txns_payload, indent=2)
    )

    ollama_request = {
        "model": model,
        "stream": False,
        "format": "json",
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

            # Map predictions back by ID
            pred_map = {str(item.get("id")): item for item in results_list if isinstance(item, dict)}

            for idx, t in enumerate(batch):
                tid = str(t.get("fingerprint") or idx)
                if tid in pred_map:
                    item = pred_map[tid]
                    elem = item.get("element", "needs_review")
                    conf = float(item.get("confidence", 0.0))
                    reason = item.get("reason", "Classified by local LLM")

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
        logger.info("Local classification service offline. Routing unmatched rows to needs_review.")
        return _fallback_all(batch, "Ambiguous counterparty requiring confirmation")
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
    """
    if not unmatched_transactions:
        return []

    few_shot = await get_few_shot_examples(db)
    batch_size = config.BATCH_SIZE
    classified: List[Dict[str, Any]] = []

    for i in range(0, len(unmatched_transactions), batch_size):
        chunk = unmatched_transactions[i:i + batch_size]
        res = await classify_batch_with_ollama(
            batch=chunk,
            few_shot_text=few_shot,
            model_name=model_name
        )
        classified.extend(res)

    return classified
