#!/usr/bin/env python3
"""
Evaluation script for the code_migrator agent.
Tests against ground truth data.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.code_migrator import agent_code_migrator
from src.utils import check_aws_credentials

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs during eval
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@dataclass
class EvalMetrics:
    """Metrics for evaluation"""

    message_correct: bool


def compare_results(expected: Dict, actual: str) -> EvalMetrics:
    """Compare expected and actual results"""

    # Simple string matching for now (hello world)
    message_correct = expected["message"] in actual

    return EvalMetrics(message_correct=message_correct)


def run_single_eval(test_case: Dict, base_path: str) -> Dict[str, Any]:
    """Run evaluation for a single test case"""
    name = test_case["name"]
    repo_path = os.path.join(base_path, test_case["repo_path"])
    expected = test_case["expected"]

    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Repo: {repo_path}")
    print(f"{'='*60}")

    # Verify path exists
    if not os.path.exists(repo_path):
        return {
            "name": name,
            "status": "SKIPPED",
            "error": f"Repository path does not exist: {repo_path}",
        }

    try:
        result = agent_code_migrator(repo_path)
    except Exception as e:
        return {"name": name, "status": "ERROR", "error": str(e)}

    # Calculate metrics
    metrics = compare_results(expected, result)

    # Determine pass/fail
    passed = metrics.message_correct

    result_data = {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "metrics": {"message_correct": metrics.message_correct},
        "expected": expected,
        "actual": result,
    }

    # Print summary
    print(f"\nStatus: {result_data['status']}")
    print(f"Message correct: {'✓' if metrics.message_correct else '✗'}")

    if not metrics.message_correct:
        print(f"\n⚠️  Expected: {expected['message']}")
        print(f"   Got: {result[:100]}...")

    return result_data


def main():
    """Main evaluation function"""
    print("=" * 60)
    print("CODE MIGRATOR EVALUATION")
    print("=" * 60)

    # Check AWS credentials
    print("\nChecking AWS credentials...")
    creds_available, error_message = check_aws_credentials()
    if not creds_available:
        print(f"Error: {error_message}")
        sys.exit(1)
    print("✓ AWS credentials found and valid\n")

    # Load ground truth
    eval_dir = Path(__file__).parent
    ground_truth_path = eval_dir / "ground_truth.json"

    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)

    base_path = eval_dir.parent.parent

    # Run evaluations
    results = []
    for test_case in ground_truth["test_cases"]:
        result = run_single_eval(test_case, str(base_path))
        results.append(result)

    # Calculate overall metrics
    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)

    total_tests = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")

    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Errors: {errors}")
    print(f"⏭️  Skipped: {skipped}")

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
                    "skipped": skipped,
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
