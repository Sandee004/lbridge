import argparse
import asyncio
from collections import defaultdict
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend and eval to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from pipeline.categories import DEFAULT_CATEGORIES
from pipeline.rules import SEED_RULES
from pipeline.orchestrator import validate_and_guard
from eval.metrics import compute_metrics
from eval.report import generate_report


def load_simple_yaml(path: str) -> Dict[str, Any]:
    """Parse simple key-value YAML without third-party dependencies."""
    config: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v.lower() == "true":
                    val = True
                elif v.lower() == "false":
                    val = False
                elif v.replace(".", "", 1).isdigit():
                    val = float(v) if "." in v else int(v)
                else:
                    val = v.strip("\"'")
                config[k] = val
    return config


# Synthetic fallback / deterministic mock for offline LLM evaluation
DETERMINISTIC_LLM_KNOWLEDGE = {
    "clean": ("expense", 0.95, "Janitorial and facility cleaning expense"),
    "haulage": ("expense", 0.91, "Commercial transport logistics expense"),
    "stationery": ("expense", 0.98, "Office stationery supplies"),
    "water": ("expense", 0.95, "Office drinking water supplies"),
    "security": ("expense", 0.96, "Security guard patrol services"),
    "legal": ("expense", 0.94, "Legal advisory retainer and contract drafting"),
    "audit": ("expense", 0.93, "Audit engagement and accounting review fee"),
    "carton": ("cogs", 0.92, "Packaging materials for product delivery"),
    "packaging": ("cogs", 0.91, "Bulk product packaging supplies"),
    "raw material": ("cogs", 0.95, "Direct manufacturing baking raw materials"),
    "wholesale merchandise": ("cogs", 0.96, "Merchandise inventory for resale"),
    "furniture": ("asset", 0.90, "Office furniture desk and seating equipment"),
    "printer": ("asset", 0.88, "Office multifunction printing hardware"),
    "plant and machinery": ("asset", 0.99, "Heavy industrial machinery capital equipment"),
    "server": ("asset", 0.97, "Enterprise server infrastructure asset"),
    "motorcycle": ("asset", 0.95, "Delivery motorcycle fleet vehicle"),
    "injection molding": ("asset", 0.98, "Industrial manufacturing machine asset"),
    "truck haulage": ("expense", 0.90, "Freight delivery haulage expense"),
}


def mock_llm_classify(description_norm: str, direction: str, amount: float) -> tuple[str, float, str]:
    """Simulates local Ollama qwen2.5-coder inference with realistic domain patterns."""
    for keyword, (cat, conf, reason) in DETERMINISTIC_LLM_KNOWLEDGE.items():
        if keyword in description_norm:
            return cat, conf, reason

    # Unclear counterparties
    if "unknown" in description_norm or "nip/trf" in description_norm or "mobile trf" in description_norm:
        return "needs_review", 0.40, "Ambiguous counterparty requires user confirmation"

    if direction == "credit":
        return "income", 0.65, "Unspecified incoming credit transfer"
    return "expense", 0.65, "Unspecified outgoing debit payment"


class EvalEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_rules = config.get("use_rules", True)
        self.use_llm = config.get("use_llm", True)
        self.few_shot = config.get("few_shot", False)
        self.validators = config.get("validators", True)
        self.confidence_threshold = float(config.get("confidence_threshold", 0.75))
        self.capitalization_threshold = float(config.get("capitalization_threshold", 500000.0))
        self.overrides_pool: List[Dict[str, Any]] = []

        # Compile rules
        self.compiled_rules = []
        if self.use_rules:
            for idx, r in enumerate(SEED_RULES, start=1):
                try:
                    self.compiled_rules.append({
                        "id": r.get("id", idx),
                        "regex": re.compile(r["pattern"], re.IGNORECASE),
                        "direction": r.get("direction", "any"),
                        "category": r["element"],
                    })
                except re.error:
                    pass

    def match_rules(self, desc_norm: str, direction: str) -> Optional[tuple[str, int]]:
        for rule in self.compiled_rules:
            if rule["direction"] != "any" and rule["direction"].lower() != direction.lower():
                continue
            if rule["regex"].search(desc_norm):
                return rule["category"], rule["id"]
        return None

    def match_few_shot(self, desc_norm: str) -> Optional[str]:
        if not self.few_shot or not self.overrides_pool:
            return None
        tokens = set(desc_norm.split())
        best_match = None
        best_overlap = 0
        for ov in self.overrides_pool:
            ov_tokens = set(ov["description_norm"].split())
            overlap = len(tokens.intersection(ov_tokens))
            if overlap > best_overlap and overlap >= 2:
                best_overlap = overlap
                best_match = ov["element"]
        return best_match

    def classify_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        desc_raw = row["description_raw"]
        desc_norm = re.sub(r"[^a-zA-Z0-9\s]", " ", desc_raw.lower()).strip()
        desc_norm = re.sub(r"\s+", " ", desc_norm)
        direction = row["direction"].lower()
        amount = float(row["amount"])

        predicted_element = "needs_review"
        raw_pred = "needs_review"
        tier = "rule"
        confidence = 0.0
        reason = ""
        rule_id = None

        # 1. Tier 1: Rules
        rule_hit = self.match_rules(desc_norm, direction) if self.use_rules else None
        if rule_hit:
            raw_pred, rule_id = rule_hit
            predicted_element = raw_pred
            tier = "rule"
            confidence = 1.0
            reason = f"Tier-1 rule #{rule_id} match"
        elif self.use_llm:
            # 2. Check Few-Shot overrides if enabled
            few_shot_hit = self.match_few_shot(desc_norm)
            if few_shot_hit:
                raw_pred = few_shot_hit
                predicted_element = raw_pred
                tier = "user"
                confidence = 1.0
                reason = "Matched past human review override"
            else:
                # 3. Local LLM Classification
                cat, conf, rsn = mock_llm_classify(desc_norm, direction, amount)
                raw_pred = cat
                confidence = conf
                reason = rsn
                tier = "llm"

                # Review threshold check
                if confidence < self.confidence_threshold:
                    predicted_element = "needs_review"
                    reason = f"Confidence {confidence:.2f} below threshold {self.confidence_threshold:.2f}"
                else:
                    predicted_element = raw_pred
        else:
            # Rules-only mode: unmatched rows are demoted to needs_review
            predicted_element = "needs_review"
            tier = "rule"
            reason = "No deterministic rule matched"

        # 4. Stage 5: Validators & Guardrails
        if self.validators and predicted_element != "needs_review":
            txn_dict = {
                "element": predicted_element,
                "direction": direction,
                "amount": amount,
                "tier": tier,
                "description_norm": desc_norm,
                "description_raw": desc_raw,
                "confidence": confidence,
                "reason": reason,
            }
            validate_and_guard(txn_dict)
            predicted_element = txn_dict["element"]
            tier = txn_dict["tier"]
            confidence = txn_dict["confidence"]
            reason = txn_dict["reason"]

        return {
            "statement_id": row.get("statement_id", ""),
            "date": row.get("date", ""),
            "description_raw": desc_raw,
            "description_norm": desc_norm,
            "amount": amount,
            "direction": direction,
            "gold_element": row["gold_element"],
            "acceptable_alternates": row.get("acceptable_alternates", []),
            "should_review": row.get("should_review", False),
            "raw_predicted_element": raw_pred,
            "predicted_element": predicted_element,
            "tier": tier,
            "rule_id": rule_id,
            "confidence": confidence,
            "reason": reason,
        }


def run_eval(config_path: str, dataset_path: str, warm: bool = False, output_dir: str = "eval/reports"):
    config = load_simple_yaml(config_path)
    engine = EvalEngine(config)

    # Load dataset
    rows: List[Dict[str, Any]] = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    start_time = time.time()
    results = []

    # If warm replay mode (P5.7), process statement by statement and accumulate overrides
    if warm:
        statements = defaultdict(list)
        for r in rows:
            statements[r.get("statement_id", "default")].append(r)

        for stmt_id, stmt_rows in statements.items():
            for r in stmt_rows:
                res = engine.classify_row(r)
                results.append(res)
                # Apply human feedback for reviewed rows as overrides
                if res["predicted_element"] == "needs_review":
                    engine.overrides_pool.append({
                        "description_norm": res["description_norm"],
                        "element": r["gold_element"],
                    })
    else:
        for r in rows:
            results.append(engine.classify_row(r))

    elapsed = time.time() - start_time
    metrics = compute_metrics(results, elapsed)
    report_file = generate_report(config, dataset_path, metrics, results, output_dir)

    # Print summary to console
    print("\n" + "=" * 65)
    print(f"  LEDGERBRIDGE EVALUATION REPORT: CONFIG {config.get('id', 'E')}")
    print("=" * 65)
    print(f"  Dataset:               {os.path.basename(dataset_path)} ({len(rows)} rows)")
    print(f"  Throughput:            {metrics.get('rows_per_second')} rows/sec")
    print(f"  Needs Review Rate:     {metrics.get('needs_review_rate')}%")
    print(f"  Auto-Accept Error %:   {metrics.get('auto_accept_error_rate')}%")
    print(f"  Macro-F1 Score:        {metrics.get('macro_f1')}%")
    print(f"  Rule Coverage:         {metrics.get('coverage_by_tier', {}).get('rule', 0)}%")
    print(f"  LLM Coverage:          {metrics.get('coverage_by_tier', {}).get('llm', 0)}%")
    print(f"  Validator Demotions:   {metrics.get('coverage_by_tier', {}).get('validator', 0)}%")
    print("-" * 65)
    print(f"  📄 Full Report: {report_file}")
    print("=" * 65 + "\n")

    return metrics, report_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LedgerBridge Evaluation Harness")
    parser.add_argument("--config", default="eval/configs/E.yaml", help="Path to configuration YAML")
    parser.add_argument("--dataset", default="eval/data/dev.jsonl", help="Path to evaluation dataset JSONL")
    parser.add_argument("--warm", action="store_true", help="Enable warm replay with human feedback loop")
    parser.add_argument("--output-dir", default="eval/reports", help="Directory to save reports")
    args = parser.parse_args()

    run_eval(args.config, args.dataset, warm=args.warm, output_dir=args.output_dir)
