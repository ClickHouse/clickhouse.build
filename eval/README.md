# Code Planner Evaluation Framework

Automated testing and evaluation for the code_planner agent.

## Overview

This eval framework tests the code planner's ability to find analytical queries across different codebases and ORMs.

## Files

- **`ground_truth.json`** - Expected results for each test case
- **`eval.py`** - Evaluation script that runs tests and calculates metrics
- **`eval_results.json`** - Detailed results from last eval run (generated)

## Metrics

The evaluation calculates:

- **Precision**: What % of found queries are correct
- **Recall**: What % of actual queries were found
- **F1 Score**: Harmonic mean of precision and recall
- **True Positives**: Queries correctly identified
- **False Positives**: Incorrect queries reported
- **False Negatives**: Queries that were missed

## Running Evaluations

### Run all tests:
```bash
uv run eval/eval.py
```

### Run with verbose output:
```bash
uv run eval/eval.py --verbose
```

## Adding New Test Cases

1. Create a new test repository in `test/`
2. Add a test case to `ground_truth.json`:

```json
{
  "name": "my-test-case",
  "repo_path": "test/my-test-case",
  "expected": {
    "total_tables": 2,
    "total_queries": 5,
    "tables": ["users", "orders"],
    "queries": [
      {
        "description": "User order count",
        "location": "/api/users/stats.ts:L10-15",
        "has_aggregation": true,
        "query_type": "orm"
      }
    ]
  }
}
```

## Pass Criteria

A test passes if:
- F1 score >= 0.8 (80%)
- Table count is correct
- Query count is within ±1 of expected

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Run Code Planner Evaluations
  run: uv run eval/eval.py
```

The script exits with code 1 if any tests fail.

## Interpreting Results

### Good Results
```
✅ Passed: 3/3
Precision: 100%
Recall: 100%
F1 Score: 100%
```

### Issues to Fix

**High False Positives**: Agent is finding queries that aren't analytical
- Update exclusion rules in prompt
- Add more patterns to filter seed/test files

**High False Negatives**: Agent is missing queries
- Improve grep patterns
- Check if ORM queries are being detected
- Verify file extensions are included

**Wrong Query Counts**: Agent is over/under counting
- Check for duplicate detection
- Verify filtering logic

## Example Output

```
============================================================
Testing: pg-expense-drizzleorm
Repo: test/pg-expense-drizzleorm
============================================================

⏱️  Total execution time: 15.32 seconds

Status: PASS
Precision: 100.0%
Recall: 100.0%
F1 Score: 100.0%
Tables: 1/1
Queries: 4/4

============================================================
OVERALL RESULTS
============================================================

Total Tests: 3
✅ Passed: 3
❌ Failed: 0
⚠️  Errors: 0

Average Metrics:
  Precision: 100.0%
  Recall: 100.0%
  F1 Score: 100.0%

✅ All tests passed!
```
