#!/usr/bin/env python3
"""
Evaluation script for the qa_code_migrator tool.
Tests the QA approval system against various code patterns.
"""

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.qa_code_migrator import qa_approve
from src.utils import check_aws_credentials

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs during eval
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@dataclass
class EvalMetrics:
    """Metrics for evaluation"""

    approval_correct: bool


def compare_results(expected: Dict, actual_result: str) -> EvalMetrics:
    """Compare expected and actual QA results"""

    try:
        actual = json.loads(actual_result)
    except json.JSONDecodeError:
        return EvalMetrics(approval_correct=False)

    # Check if approval matches expected
    approval_correct = actual.get("approved") == expected["approved"]

    return EvalMetrics(approval_correct=approval_correct)


def run_single_eval(test_case: Dict) -> Dict[str, Any]:
    """Run evaluation for a single test case"""
    name = test_case["name"]
    file_path = test_case["file_path"]
    code = test_case["code"]
    purpose = test_case["purpose"]
    expected = test_case["expected"]

    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"File: {file_path}")
    print(f"{'='*60}")

    try:
        # Call qa_approve with the code snippet
        result = qa_approve(file_path, code, purpose)
    except Exception as e:
        return {"name": name, "status": "ERROR", "error": str(e)}

    # Calculate metrics
    metrics = compare_results(expected, result)

    # Determine pass/fail
    passed = metrics.approval_correct

    result_data = {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "metrics": {
            "approval_correct": metrics.approval_correct,
        },
        "expected": expected,
        "actual": json.loads(result) if result else None,
    }

    # Print summary
    print(f"\nStatus: {result_data['status']}")
    print(f"Approval correct: {'✓' if metrics.approval_correct else '✗'}")

    try:
        actual_json = json.loads(result)
        print(
            f"\nExpected: {expected['approved']} | Got: {actual_json.get('approved')}"
        )
        print(f"Reason: {actual_json.get('reason', 'N/A')}")
    except:
        pass

    if not metrics.approval_correct:
        print("\n⚠️  Approval decision incorrect")

    return result_data


def main():
    """Main evaluation function"""
    print("=" * 60)
    print("QA CODE MIGRATOR EVALUATION")
    print("=" * 60)

    # Check AWS credentials
    print("\nChecking AWS credentials...")
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        print(f"Error: {error_message}")
        sys.exit(1)
    print("✓ AWS credentials loaded\n")

    # Load ground truth
    eval_dir = Path(__file__).parent
    ground_truth_path = eval_dir / "ground_truth.json"

    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)

    # Run evaluations
    results = []
    for test_case in ground_truth["test_cases"]:
        result = run_single_eval(test_case)
        results.append(result)

    # Calculate overall metrics
    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)

    total_tests = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Errors: {errors}")

    # Calculate component accuracy
    valid_results = [r for r in results if r["status"] in ["PASS", "FAIL"]]
    if valid_results:
        approval_accuracy = sum(
            1 for r in valid_results if r["metrics"]["approval_correct"]
        ) / len(valid_results)

        print(f"\nApproval Accuracy: {approval_accuracy:.1%}")

    # Save detailed results
    results_path = eval_dir / "eval_results.json"
    with open(results_path, "w") as f:
        json.dump(
            {
                "summary": {
                    "total_tests": total_tests,
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                    "pass_rate": passed / total_tests if total_tests > 0 else 0,
                },
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\nDetailed results saved to: {results_path}")

    # Exit with appropriate code
    if failed > 0 or errors > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
