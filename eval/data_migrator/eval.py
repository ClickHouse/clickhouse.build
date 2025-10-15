#!/usr/bin/env python3
"""
Evaluation script for the data_migrator agent.
Tests against ground truth data and validates ClickPipe configuration accuracy.
"""

import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.data_migrator import run_data_migrator_agent
from src.utils import check_aws_credentials

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Suppress INFO logs during eval
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@dataclass
class EvalMetrics:
    """Metrics for evaluation"""

    database_correct: bool
    destination_correct: bool
    replication_mode_correct: bool
    schema_tables_correct: bool
    table_mappings_correct: bool
    all_correct: bool


def extract_config_from_curl(curl_command: str) -> Dict:
    """Extract the JSON config from the curl command"""
    # Find the --data argument and extract the JSON
    match = re.search(r"--data\s+'({.*})'", curl_command, re.DOTALL)
    if match:
        json_str = match.group(1)
        return json.loads(json_str)
    raise ValueError("Could not extract config from curl command")


def normalize_table_mappings(mappings: List[Dict]) -> List[Dict]:
    """Normalize table mappings for comparison (sort by schema and table)"""
    return sorted(mappings, key=lambda x: (x["sourceSchemaName"], x["sourceTable"]))


def compare_configs(expected: Dict, actual: Dict) -> EvalMetrics:
    """Compare expected and actual ClickPipe configurations"""

    # Extract actual config from curl command
    try:
        actual_config = extract_config_from_curl(actual["command"])
    except Exception as e:
        print(f"Error extracting config from curl: {e}")
        return EvalMetrics(
            database_correct=False,
            destination_correct=False,
            replication_mode_correct=False,
            schema_tables_correct=False,
            table_mappings_correct=False,
            all_correct=False,
        )

    # Check each component
    database_correct = (
        actual_config["source"]["postgres"]["database"] == expected["database_name"]
    )
    destination_correct = (
        actual_config["destination"]["database"] == expected["destination_database"]
    )
    replication_mode_correct = (
        actual_config["source"]["postgres"]["settings"]["replicationMode"]
        == expected["replication_mode"]
    )

    # Compare table mappings
    actual_mappings = normalize_table_mappings(
        actual_config["source"]["postgres"]["tableMappings"]
    )
    expected_mappings = normalize_table_mappings(expected["table_mappings"])
    table_mappings_correct = actual_mappings == expected_mappings

    # Schema tables correctness (derived from table mappings)
    schema_tables_correct = table_mappings_correct

    all_correct = (
        database_correct
        and destination_correct
        and replication_mode_correct
        and schema_tables_correct
        and table_mappings_correct
    )

    return EvalMetrics(
        database_correct=database_correct,
        destination_correct=destination_correct,
        replication_mode_correct=replication_mode_correct,
        schema_tables_correct=schema_tables_correct,
        table_mappings_correct=table_mappings_correct,
        all_correct=all_correct,
    )


def run_single_eval(
    test_case: Dict, base_path: str, fixtures_dir: Path
) -> Dict[str, Any]:
    """Run evaluation for a single test case"""
    name = test_case["name"]
    repo_path = os.path.join(base_path, test_case["repo_path"])
    replication_mode = test_case.get("replication_mode", "cdc")
    expected = test_case["expected"]

    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Using fixture: {name}.json")
    print(f"{'='*60}")

    # Load fixture plan
    fixture_path = fixtures_dir / f"{name}.json"
    if not fixture_path.exists():
        return {
            "name": name,
            "status": "SKIPPED",
            "error": f"Fixture not found: {fixture_path}",
        }

    try:
        # Read the fixture scan
        with open(fixture_path, "r") as f:
            scan_data = json.load(f)

        # Create .chbuild/scanner directory and place fixture there
        scanner_dir = Path(repo_path) / ".chbuild" / "scanner"
        scanner_dir.mkdir(parents=True, exist_ok=True)

        # Write fixture as the "latest" scan
        scan_file = scanner_dir / "scan_fixture.json"
        with open(scan_file, "w") as f:
            json.dump(scan_data, f, indent=2)

        # Run data migrator (it will read the fixture we just placed)
        result_str = run_data_migrator_agent(repo_path, replication_mode)
        result = json.loads(result_str)

        # Result should have "assumptions" and "config" keys
        if "config" not in result:
            raise ValueError(f"Result missing 'config' key: {result}")

        # Handle config being either a string or already parsed dict
        if isinstance(result["config"], str):
            actual = json.loads(result["config"])
        else:
            actual = result["config"]

        assumptions = result.get("assumptions", [])

    except Exception as e:
        return {"name": name, "status": "ERROR", "error": str(e)}

    # Calculate metrics
    metrics = compare_configs(expected, actual)

    # Determine pass/fail
    passed = metrics.all_correct

    result = {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "metrics": {
            "database_correct": metrics.database_correct,
            "destination_correct": metrics.destination_correct,
            "replication_mode_correct": metrics.replication_mode_correct,
            "schema_tables_correct": metrics.schema_tables_correct,
            "table_mappings_correct": metrics.table_mappings_correct,
            "all_correct": metrics.all_correct,
        },
        "assumptions": assumptions,
        "expected": expected,
        "actual": actual,
    }

    # Print summary
    print(f"\nStatus: {result['status']}")
    print(f"Database: {'✓' if metrics.database_correct else '✗'}")
    print(f"Destination: {'✓' if metrics.destination_correct else '✗'}")
    print(f"Replication Mode: {'✓' if metrics.replication_mode_correct else '✗'}")
    print(f"Schema/Tables: {'✓' if metrics.schema_tables_correct else '✗'}")
    print(f"Table Mappings: {'✓' if metrics.table_mappings_correct else '✗'}")

    if assumptions:
        print(f"\nAssumptions made ({len(assumptions)}):")
        for assumption in assumptions:
            print(f"  - {assumption}")

    if not metrics.all_correct:
        print(f"\n⚠️  Issues found:")
        if not metrics.database_correct:
            try:
                actual_config = extract_config_from_curl(actual["command"])
                actual_db = actual_config["source"]["postgres"]["database"]
                print(
                    f"   Database: expected '{expected['database_name']}', got '{actual_db}'"
                )
            except:
                pass
        if not metrics.table_mappings_correct:
            print(f"   Table mappings do not match expected")

    return result


def main():
    """Main evaluation function"""
    print("=" * 60)
    print("DATA MIGRATOR EVALUATION")
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
    fixtures_dir = eval_dir / "fixtures"

    with open(ground_truth_path, "r") as f:
        ground_truth = json.load(f)

    base_path = eval_dir.parent.parent

    # Run evaluations
    results = []
    for test_case in ground_truth["test_cases"]:
        result = run_single_eval(test_case, str(base_path), fixtures_dir)
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

    # Calculate component accuracy
    valid_results = [r for r in results if r["status"] in ["PASS", "FAIL"]]
    if valid_results:
        metrics_summary = {
            "database_accuracy": sum(
                1 for r in valid_results if r["metrics"]["database_correct"]
            )
            / len(valid_results),
            "destination_accuracy": sum(
                1 for r in valid_results if r["metrics"]["destination_correct"]
            )
            / len(valid_results),
            "replication_mode_accuracy": sum(
                1 for r in valid_results if r["metrics"]["replication_mode_correct"]
            )
            / len(valid_results),
            "table_mappings_accuracy": sum(
                1 for r in valid_results if r["metrics"]["table_mappings_correct"]
            )
            / len(valid_results),
        }

        print(f"\nComponent Accuracy:")
        print(f"  Database: {metrics_summary['database_accuracy']:.1%}")
        print(f"  Destination: {metrics_summary['destination_accuracy']:.1%}")
        print(f"  Replication Mode: {metrics_summary['replication_mode_accuracy']:.1%}")
        print(f"  Table Mappings: {metrics_summary['table_mappings_accuracy']:.1%}")

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
