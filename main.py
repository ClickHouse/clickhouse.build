#!/usr/bin/env python3

import os
from src.orchestrator import WorkflowOrchestrator

def main():

    # Repository path to analyze
    repo_path = ""

    print("ClickHouse Build: PostgreSQL to ClickHouse Migration Tool")
    print("=" * 60)
    print(f"Repository: {repo_path}")
    print()

    try:
        # Create orchestrator
        orchestrator = WorkflowOrchestrator()
        
        # Run in conversational mode
        orchestrator.run_conversational(repo_path)
        
    except Exception as e:
        print(f"Exception in write_new_content: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
