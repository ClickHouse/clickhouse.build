#!/usr/bin/env python3
"""
Evaluation script for the code_planner agent.
Tests against ground truth data and calculates precision, recall, and F1 scores.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.planner import agent_planner
from src.utils import check_aws_credentials

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs during eval
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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

def normalize_location(location: str) -> str:
    """Normalize location to file:start_line format for comparison"""
    # Keep file path and starting line number
    if ':L' in location:
        parts = location.split(':L')
        if len(parts) == 2:
            file_path = parts[0]
            # Extract just the starting line number (before any dash or comma)
            line_part = parts[1].split('-')[0].split(',')[0]
            return f"{file_path}:L{line_part}"
    return location

def are_locations_similar(loc1: str, loc2: str, line_tolerance: int = 3) -> bool:
    """Check if two locations are similar (same file, within N lines)"""
    norm1 = normalize_location(loc1)
    norm2 = normalize_location(loc2)

    # Extract file path and line number
    try:
        file1, line1_str = norm1.rsplit(':L', 1)
        file2, line2_str = norm2.rsplit(':L', 1)

        # Check if same file
        if file1 != file2:
            return False

        # Check if lines are within tolerance
        line1 = int(line1_str)
        line2 = int(line2_str)

        return abs(line1 - line2) <= line_tolerance
    except (ValueError, AttributeError):
        # Fallback to exact match
        return norm1 == norm2

def calculate_metrics(expected: Dict, actual: Dict) -> EvalMetrics:
    """Calculate precision, recall, and F1 score"""

    # Extract locations from expected and actual
    expected_locations = [q['location'] for q in expected['queries']]
    actual_locations = [q['location'] for q in actual['queries']]

    # Find matches using similarity (within 3 lines)
    matched_expected = set()
    matched_actual = set()

    for i, actual_loc in enumerate(actual_locations):
        for j, expected_loc in enumerate(expected_locations):
            if j not in matched_expected and are_locations_similar(actual_loc, expected_loc):
                matched_expected.add(j)
                matched_actual.add(i)
                break

    # Calculate true positives, false positives, false negatives
    true_positives = len(matched_actual)
    false_positives = len(actual_locations) - len(matched_actual)
    false_negatives = len(expected_locations) - len(matched_expected)

    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return EvalMetrics(
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        total_expected=len(expected_locations),
        total_found=len(actual_locations)
    )

def run_single_eval(test_case: Dict, base_path: str) -> Dict[str, Any]:
    """Run evaluation for a single test case"""
    name = test_case['name']
    repo_path = os.path.join(base_path, test_case['repo_path'])
    expected = test_case['expected']

    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Repo: {repo_path}")
    print(f"{'='*60}")

    # Verify path exists
    if not os.path.exists(repo_path):
        return {
            'name': name,
            'status': 'SKIPPED',
            'error': f"Repository path does not exist: {repo_path}"
        }

    try:
        result_json = agent_planner(repo_path)
        actual = json.loads(result_json)
    except Exception as e:
        return {
            'name': name,
            'status': 'ERROR',
            'error': str(e)
        }

    # Calculate metrics
    metrics = calculate_metrics(expected, actual)

    # Check table counts
    table_count_correct = actual.get('total_tables') == expected['total_tables']
    query_count_correct = actual.get('total_queries') == expected['total_queries']

    # Determine pass/fail
    passed = (
        metrics.f1_score >= 0.8 and  # F1 score threshold
        table_count_correct and
        abs(actual.get('total_queries', 0) - expected['total_queries']) <= 1  # Allow 1 query difference
    )

    result = {
        'name': name,
        'status': 'PASS' if passed else 'FAIL',
        'metrics': {
            'precision': round(metrics.precision, 3),
            'recall': round(metrics.recall, 3),
            'f1_score': round(metrics.f1_score, 3),
            'true_positives': metrics.true_positives,
            'false_positives': metrics.false_positives,
            'false_negatives': metrics.false_negatives
        },
        'counts': {
            'expected_tables': expected['total_tables'],
            'actual_tables': actual.get('total_tables', 0),
            'expected_queries': expected['total_queries'],
            'actual_queries': actual.get('total_queries', 0),
            'table_count_correct': table_count_correct,
            'query_count_correct': query_count_correct
        },
        'expected': expected,
        'actual': actual
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
        expected_locations = [q['location'] for q in expected['queries']]
        actual_locations = [q['location'] for q in actual['queries']]

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
        expected_locations = [q['location'] for q in expected['queries']]
        actual_locations = [q['location'] for q in actual['queries']]

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
    print("="*60)
    print("CODE PLANNER EVALUATION")
    print("="*60)

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

    with open(ground_truth_path, 'r') as f:
        ground_truth = json.load(f)

    base_path = eval_dir.parent.parent

    # Run evaluations
    results = []
    for test_case in ground_truth['test_cases']:
        result = run_single_eval(test_case, str(base_path))
        results.append(result)

    # Calculate overall metrics
    print("\n" + "="*60)
    print("OVERALL RESULTS")
    print("="*60)

    total_tests = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    skipped = sum(1 for r in results if r['status'] == 'SKIPPED')

    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Errors: {errors}")
    print(f"⏭️  Skipped: {skipped}")

    # Calculate average metrics
    valid_results = [r for r in results if r['status'] in ['PASS', 'FAIL']]
    if valid_results:
        avg_precision = sum(r['metrics']['precision'] for r in valid_results) / len(valid_results)
        avg_recall = sum(r['metrics']['recall'] for r in valid_results) / len(valid_results)
        avg_f1 = sum(r['metrics']['f1_score'] for r in valid_results) / len(valid_results)

        print(f"\nAverage Metrics:")
        print(f"  Precision: {avg_precision:.1%}")
        print(f"  Recall: {avg_recall:.1%}")
        print(f"  F1 Score: {avg_f1:.1%}")

    # Save detailed results
    results_path = eval_dir / "eval_results.json"
    with open(results_path, 'w') as f:
        json.dump({
            'summary': {
                'total_tests': total_tests,
                'passed': passed,
                'failed': failed,
                'errors': errors,
                'skipped': skipped,
                'pass_rate': passed / total_tests if total_tests > 0 else 0
            },
            'results': results
        }, f, indent=2)

    print(f"\nDetailed results saved to: {results_path}")

    # Exit with appropriate code
    if failed > 0 or errors > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
