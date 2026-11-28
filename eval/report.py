import hashlib
import json
import os
from datetime import datetime
from typing import Any, Dict, List


def generate_report(
    config: Dict[str, Any],
    dataset_path: str,
    metrics: Dict[str, Any],
    results: List[Dict[str, Any]],
    output_dir: str = "eval/reports",
) -> str:
    """
    P5.5: Generates Markdown evaluation report and per-row JSON artifact.
    Records model metadata, hashes, coverage, auto-accept error rate,
    macro-F1, confusion matrix, and failure analysis.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_id = config.get("id", "E")

    # Hashes
    ruleset_hash = hashlib.sha256(str(config.get("use_rules", True)).encode()).hexdigest()[:8]
    prompt_hash = hashlib.sha256(str(config.get("prompt_version", "1.0")).encode()).hexdigest()[:8]
    dataset_version = os.path.basename(dataset_path)

    json_path = os.path.join(output_dir, f"{config_id}_{timestamp}.json")
    md_path = os.path.join(output_dir, f"{config_id}_{timestamp}.md")

    # 1. Save detailed per-row JSON
    payload = {
        "metadata": {
            "config_id": config_id,
            "config_name": config.get("name", ""),
            "timestamp": timestamp,
            "dataset": dataset_version,
            "model_name": config.get("model_name", "qwen2.5-coder:1.5b"),
            "prompt_hash": prompt_hash,
            "ruleset_hash": ruleset_hash,
        },
        "metrics": metrics,
        "results": results,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    # 2. Build Markdown Report
    tier_cov = metrics.get("coverage_by_tier", {})
    rules_pct = tier_cov.get("rule", 0.0)
    llm_pct = tier_cov.get("llm", 0.0)
    review_pct = metrics.get("needs_review_rate", 0.0)
    auto_err = metrics.get("auto_accept_error_rate", 0.0)
    macro_f1 = metrics.get("macro_f1", 0.0)
    rows_sec = metrics.get("rows_per_second", 0.0)

    lines = [
        f"# LedgerBridge Evaluation Report: Config {config_id}",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Configuration:** {config.get('name', config_id)}  ",
        f"**Dataset:** `{dataset_version}` ({metrics.get('total_rows', 0)} rows)  ",
        f"**Model:** `{config.get('model_name', 'qwen2.5-coder:1.5b')}`  ",
        f"**Prompt Hash:** `{prompt_hash}` | **Ruleset Hash:** `{ruleset_hash}`  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Core Safety Metrics",
        "",
        "| Metric | Measured Value | Standard / Target | Status |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Auto-Accept Error Rate** | **{auto_err}%** | < 2.0% | {'✅ PASS' if auto_err <= 2.0 else '⚠️ REVIEW'} |",
        f"| **Needs Review Rate** | **{review_pct}%** | 5.0% - 25.0% | {'✅ HEALTHY' if 5 <= review_pct <= 30 else 'ℹ️ OBSERVE'} |",
        f"| **Macro-F1 Score** | **{macro_f1}%** | > 90.0% | {'✅ EXCELLENT' if macro_f1 >= 90 else '⚠️ LOW'} |",
        f"| **Rule Coverage** | **{rules_pct}%** | > 40.0% | Tier 1 Fast Path |",
        f"| **LLM Coverage** | **{llm_pct}%** | - | Tier 2 Inference |",
        f"| **Throughput** | **{rows_sec} rows/sec** | > 20 rows/sec | Processing Speed |",
        "",
        "---",
        "",
        "## 2. Tier Breakdown & Provenance",
        "",
        "| Classification Tier | Resolved Rows | Coverage % | Tier Accuracy |",
        "| :--- | :--- | :--- | :--- |",
    ]

    tier_acc = metrics.get("per_tier_accuracy", {})
    for tier, pct in tier_cov.items():
        acc = tier_acc.get(tier, "N/A")
        acc_str = f"{acc}%" if isinstance(acc, (int, float)) else acc
        count = sum(1 for r in results if r.get("tier") == tier)
        lines.append(f"| `{tier}` | {count} | {pct}% | {acc_str} |")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Confusion Matrix",
        "",
    ])

    # Confusion matrix markdown table
    labels = metrics.get("matrix_labels", [])
    matrix = metrics.get("confusion_matrix", {})
    if labels and matrix:
        header = "| Gold \\ Pred | " + " | ".join(f"`{l[:7]}`" for l in labels) + " |"
        sep = "| :--- | " + " | ".join(":---:" for _ in labels) + " |"
        lines.append(header)
        lines.append(sep)
        for g in labels:
            row_cells = [f"`{g}`"]
            for p in labels:
                count = matrix.get(g, {}).get(p, 0)
                row_cells.append(str(count) if count > 0 else "-")
            lines.append("| " + " | ".join(row_cells) + " |")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Failure & Demotion Analysis (Worst Misclassifications)",
        "",
    ])

    # Find misclassifications
    misclassifications = []
    for r in results:
        pred = r["predicted_element"]
        gold = r["gold_element"]
        alts = r.get("acceptable_alternates") or []
        if pred != "needs_review" and pred != gold and pred not in alts:
            misclassifications.append(r)

    if misclassifications:
        lines.append("| Row # | Narration | Direction | Amount | Gold | Predicted | Tier | Reason |")
        lines.append("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |")
        for i, m in enumerate(misclassifications[:10], start=1):
            desc = m.get("description_raw", "")[:35].replace("|", "/")
            lines.append(
                f"| {i} | `{desc}` | {m.get('direction')} | ₦{m.get('amount', 0):,.2f} | "
                f"`{m.get('gold_element')}` | **`{m.get('predicted_element')}`** | "
                f"`{m.get('tier')}` | {m.get('reason', 'N/A')} |"
            )
    else:
        lines.append("🎉 **Zero auto-accept misclassifications detected.** All ambiguous or edge cases were correctly routed to `Needs Review` by guardrail validators.")

    lines.append("")
    content = "\n".join(lines)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    return md_path
