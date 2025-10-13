#!/usr/bin/env python3
"""
Evaluation script for the code_planner agent.
Tests against ground truth data and calculates precision, recall, and F1 scores.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.planner import agent_planner
from src.utils import check_aws_credentials

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs during eval
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@dataclass
class EvalMetrics:
    """Metrics for evaluation"""

    precision: float
    recall: float
    f1_score: float
    true_positives: int
    false_positives: int
    false_negatives: int
    total_expected: int
    total_found: int


def paths_match(path1: str, path2: str) -> bool:
    """Check if two paths match, handling absolute vs relative paths"""
    # Normalize separators
    path1 = path1.replace("\\", "/")
    path2 = path2.replace("\\", "/")

    # If paths are exactly equal
    if path1 == path2:
        return True

    # Check if one path ends with the other (handles absolute vs relative)
    # This handles cases where one path is /full/path/to/app/file.ts
    # and the other is /app/file.ts
    return path1.endswith(path2) or path2.endswith(path1)


def extract_line_range(location: str) -> tuple:
    """Extract file path and line range from location string"""
    if ":L" not in location:
        return None, None, None

    parts = location.split(":L")
    if len(parts) != 2:
        return None, None, None

    file_path = parts[0]
    line_part = parts[1]

    # Parse line range (e.g., "27-30" or "27" or "27-L30")
    if "-" in line_part:
        start, end = line_part.split("-", 1)
        # Remove 'L' prefix if present
        start = start.lstrip("L")
        end = end.lstrip("L")
        return file_path, int(start), int(end)
    else:
        line = int(line_part)
        return file_path, line, line


def calculate_line_overlap(loc1: str, loc2: str) -> float:
    """Calculate the overlap ratio between two line ranges (0.0 to 1.0)"""
    file1, start1, end1 = extract_line_range(loc1)
    file2, start2, end2 = extract_line_range(loc2)

    if file1 is None or file2 is None:
        return 0.0

    # Check if same file (handles absolute vs relative paths)
    if not paths_match(file1, file2):
        return 0.0

    # Calculate overlap
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    overlap = max(0, overlap_end - overlap_start + 1)

    # Calculate union
    union_start = min(start1, start2)
    union_end = max(end1, end2)
    union = union_end - union_start + 1

    # Return IoU (Intersection over Union)
    return overlap / union if union > 0 else 0.0


def are_locations_similar(loc1: str, loc2: str, overlap_threshold: float = 0.5) -> bool:
    """Check if two locations are similar based on line range overlap"""
    overlap = calculate_line_overlap(loc1, loc2)
    return overlap >= overlap_threshold


def calculate_metrics(expected: Dict, actual: Dict) -> EvalMetrics:
    """Calculate precision, recall, and F1 score"""

    # Extract locations from expected and actual
    expected_locations = [q["location"] for q in expected["queries"]]
    actual_locations = [q["location"] for q in actual["queries"]]

    # Find matches using similarity (within 3 lines)
    matched_expected = set()
    matched_actual = set()

    for i, actual_loc in enumerate(actual_locations):
        for j, expected_loc in enumerate(expected_locations):
            if j not in matched_expected and are_locations_similar(
                actual_loc, expected_loc
            ):
                matched_expected.add(j)
                matched_actual.add(i)
                break

    # Calculate true positives, false positives, false negatives
    true_positives = len(matched_actual)
    false_positives = len(actual_locations) - len(matched_actual)
    false_negatives = len(expected_locations) - len(matched_expected)

    # Calculate metrics
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0
    )
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0
    )

    return EvalMetrics(
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        total_expected=len(expected_locations),
        total_found=len(actual_locations),
    )


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
        result_json = agent_planner(repo_path)
        actual = json.loads(result_json)
    except Exception as e:
        return {"name": name, "status": "ERROR", "error": str(e)}

    # Calculate metrics
    metrics = calculate_metrics(expected, actual)

    # Check table counts
    table_count_correct = actual.get("total_tables") == expected["total_tables"]
    query_count_correct = actual.get("total_queries") == expected["total_queries"]

    # Determine pass/fail
    passed = (
        metrics.f1_score >= 0.8  # F1 score threshold
        and table_count_correct
        and abs(actual.get("total_queries", 0) - expected["total_queries"])
        <= 1  # Allow 1 query difference
    )

    result = {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "metrics": {
            "precision": round(metrics.precision, 3),
            "recall": round(metrics.recall, 3),
            "f1_score": round(metrics.f1_score, 3),
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
        },
        "counts": {
            "expected_tables": expected["total_tables"],
            "actual_tables": actual.get("total_tables", 0),
            "expected_queries": expected["total_queries"],
            "actual_queries": actual.get("total_queries", 0),
            "table_count_correct": table_count_correct,
            "query_count_correct": query_count_correct,
        },
        "expected": expected,
        "actual": actual,
    }

    # Print summary
    print(f"\nStatus: {result['status']}")
    print(f"Precision: {metrics.precision:.1%}")
    print(f"Recall: {metrics.recall:.1%}")
    print(f"F1 Score: {metrics.f1_score:.1%}")
    print(f"Tables: {actual.get('total_tables', 0)}/{expected['total_tables']}")
    print(f"Queries: {actual.get('total_queries', 0)}/{expected['total_queries']}")

    if metrics.false_positives > 0:
        print(f"\n⚠️  False Positives: {metrics.false_positives}")
        # Show which locations were false positives
        expected_locations = [q["location"] for q in expected["queries"]]
        actual_locations = [q["location"] for q in actual["queries"]]

        for actual_loc in actual_locations:
            is_matched = False
            for expected_loc in expected_locations:
                if are_locations_similar(actual_loc, expected_loc):
                    is_matched = True
                    break
            if not is_matched:
                print(f"   - {actual_loc}")

    if metrics.false_negatives > 0:
        print(f"\n⚠️  False Negatives (Missed): {metrics.false_negatives}")
        expected_locations = [q["location"] for q in expected["queries"]]
        actual_locations = [q["location"] for q in actual["queries"]]

        for expected_loc in expected_locations:
            is_matched = False
            for actual_loc in actual_locations:
                if are_locations_similar(actual_loc, expected_loc):
                    is_matched = True
                    break
            if not is_matched:
                print(f"   - {expected_loc}")

    return result


def main():
    """Main evaluation function"""
    print("=" * 60)
    print("CODE PLANNER EVALUATION")
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

    # Calculate average metrics
    valid_results = [r for r in results if r["status"] in ["PASS", "FAIL"]]
    if valid_results:
        avg_precision = sum(r["metrics"]["precision"] for r in valid_results) / len(
            valid_results
        )
        avg_recall = sum(r["metrics"]["recall"] for r in valid_results) / len(
            valid_results
        )
        avg_f1 = sum(r["metrics"]["f1_score"] for r in valid_results) / len(
            valid_results
        )

        print(f"\nAverage Metrics:")
        print(f"  Precision: {avg_precision:.1%}")
        print(f"  Recall: {avg_recall:.1%}")
        print(f"  F1 Score: {avg_f1:.1%}")

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
