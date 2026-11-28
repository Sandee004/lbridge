import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pytest
from eval.run import run_eval


def test_p5_8_ci_eval_gate():
    """
    P5.8 CI Regression Gate:
    Runs Config E on dev set and fails if the auto-accept error rate
    exceeds the baseline margin of 2.0%.
    """
    config_path = str(BASE_DIR / "eval" / "configs" / "E.yaml")
    dataset_path = str(BASE_DIR / "eval" / "data" / "dev.jsonl")
    reports_dir = str(BASE_DIR / "eval" / "reports")

    metrics, _ = run_eval(config_path, dataset_path, warm=False, output_dir=reports_dir)

    # 1. Primary Safety Gate: Auto-accept error rate must stay < 2.0%
    assert metrics["auto_accept_error_rate"] <= 2.0, (
        f"CI Gate Failed: auto_accept_error_rate is {metrics['auto_accept_error_rate']}%, "
        "exceeding maximum safety tolerance of 2.0%."
    )

    # 2. Healthy Triage Rate: Needs Review must not exceed 25% on dev
    assert metrics["needs_review_rate"] <= 25.0, (
        f"CI Gate Failed: needs_review_rate is {metrics['needs_review_rate']}%, "
        "exceeding triage bound of 25.0%."
    )

    # 3. Model Accuracy / Balance: Macro-F1 must remain >= 80%
    assert metrics["macro_f1"] >= 80.0, (
        f"CI Gate Failed: macro_f1 is {metrics['macro_f1']}%, below acceptable floor of 80.0%."
    )
