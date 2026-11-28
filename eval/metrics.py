from collections import defaultdict
from typing import Any, Dict, List, Set


def compute_metrics(
    rows: List[Dict[str, Any]],
    elapsed_seconds: float,
    elements: List[str] = None,
) -> Dict[str, Any]:
    """
    Computes rigorous evaluation metrics as specified in Section 7.3 of mvp.md:
    - Coverage by tier
    - Needs Review rate
    - Auto-accept error rate (the primary safety metric)
    - Per-tier accuracy
    - Review precision & error capture
    - Macro-F1 & confusion matrix
    - Operational throughput (rows/sec)
    """
    if elements is None:
        elements = [
            "asset",
            "liability",
            "income",
            "expense",
            "capital",
            "cogs",
            "transfer",
            "taxes",
        ]

    total_rows = len(rows)
    if total_rows == 0:
        return {}

    tier_counts = defaultdict(int)
    resolved_by_tier = defaultdict(list)
    auto_accepted_rows = []
    reviewed_rows = []

    for r in rows:
        pred = r["predicted_element"]
        gold = r["gold_element"]
        alts = set(r.get("acceptable_alternates") or [])
        tier = r.get("tier", "unknown")
        should_review = bool(r.get("should_review", False))

        is_match = (pred == gold) or (pred in alts)

        tier_counts[tier] += 1
        resolved_by_tier[tier].append((pred, gold, is_match))

        if pred == "needs_review":
            reviewed_rows.append(r)
        else:
            auto_accepted_rows.append(r)

    # Coverage by tier
    coverage_by_tier = {
        tier: round((count / total_rows) * 100, 2)
        for tier, count in tier_counts.items()
    }

    # Needs Review rate
    needs_review_rate = round((len(reviewed_rows) / total_rows) * 100, 2)

    # Auto-accept error rate: errors among rows NOT sent to review
    auto_errors = 0
    for r in auto_accepted_rows:
        pred = r["predicted_element"]
        gold = r["gold_element"]
        alts = set(r.get("acceptable_alternates") or [])
        if pred != gold and pred not in alts:
            auto_errors += 1

    auto_accept_count = len(auto_accepted_rows)
    auto_accept_error_rate = (
        round((auto_errors / auto_accept_count) * 100, 2)
        if auto_accept_count > 0
        else 0.0
    )

    # Per-tier accuracy (excluding needs_review)
    per_tier_accuracy = {}
    for tier, items in resolved_by_tier.items():
        if tier in ("validator", "needs_review"):
            continue
        tier_matches = sum(1 for _, _, is_match in items if is_match)
        if items:
            per_tier_accuracy[tier] = round((tier_matches / len(items)) * 100, 2)

    # Review precision: of rows sent to review, % that were actually wrong or should_review
    review_correct_demotions = 0
    for r in reviewed_rows:
        gold = r["gold_element"]
        alts = set(r.get("acceptable_alternates") or [])
        raw_pred = r.get("raw_predicted_element", r["predicted_element"])
        should_review = bool(r.get("should_review", False))
        if should_review or (raw_pred != gold and raw_pred not in alts):
            review_correct_demotions += 1

    review_precision = (
        round((review_correct_demotions / len(reviewed_rows)) * 100, 2)
        if reviewed_rows
        else 100.0
    )

    # Error capture: of all rows that were wrong or should_review, % sent to review
    all_flawed_cases = 0
    flawed_caught_in_review = 0
    for r in rows:
        gold = r["gold_element"]
        alts = set(r.get("acceptable_alternates") or [])
        raw_pred = r.get("raw_predicted_element", r["predicted_element"])
        should_review = bool(r.get("should_review", False))

        is_flawed = should_review or (raw_pred != gold and raw_pred not in alts)
        if is_flawed:
            all_flawed_cases += 1
            if r["predicted_element"] == "needs_review":
                flawed_caught_in_review += 1

    error_capture = (
        round((flawed_caught_in_review / all_flawed_cases) * 100, 2)
        if all_flawed_cases > 0
        else 100.0
    )

    # Macro-F1 and Confusion Matrix
    # We calculate per-element precision, recall, and F1 across auto-accepted rows
    # plus needs_review as a separate column/row
    matrix_labels = list(elements) + ["needs_review"]
    confusion = {g: {p: 0 for p in matrix_labels} for g in matrix_labels}

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for r in rows:
        gold = r["gold_element"]
        pred = r["predicted_element"]
        if gold in confusion and pred in confusion[gold]:
            confusion[gold][pred] += 1

        if pred == gold:
            tp[gold] += 1
        else:
            fp[pred] += 1
            fn[gold] += 1

    per_element_f1 = {}
    f1_list = []
    for elem in elements:
        p = tp[elem] / (tp[elem] + fp[elem]) if (tp[elem] + fp[elem]) > 0 else 0.0
        rec = tp[elem] / (tp[elem] + fn[elem]) if (tp[elem] + fn[elem]) > 0 else 0.0
        f1 = (2 * p * rec) / (p + rec) if (p + rec) > 0 else 0.0
        per_element_f1[elem] = {
            "precision": round(p * 100, 2),
            "recall": round(rec * 100, 2),
            "f1": round(f1 * 100, 2),
            "support": tp[elem] + fn[elem],
        }
        if (tp[elem] + fn[elem]) > 0:
            f1_list.append(f1)

    macro_f1 = round((sum(f1_list) / len(f1_list)) * 100, 2) if f1_list else 0.0
    rows_per_second = (
        round(total_rows / elapsed_seconds, 2) if elapsed_seconds > 0 else 0.0
    )

    return {
        "total_rows": total_rows,
        "auto_accepted_count": auto_accept_count,
        "reviewed_count": len(reviewed_rows),
        "coverage_by_tier": coverage_by_tier,
        "needs_review_rate": needs_review_rate,
        "auto_accept_error_rate": auto_accept_error_rate,
        "per_tier_accuracy": per_tier_accuracy,
        "review_precision": review_precision,
        "error_capture": error_capture,
        "macro_f1": macro_f1,
        "per_element_metrics": per_element_f1,
        "confusion_matrix": confusion,
        "matrix_labels": matrix_labels,
        "rows_per_second": rows_per_second,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }
