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
        
        # Run workflow with interleaved thinking
        print("Starting intelligent workflow ...")
        result = orchestrator.run_workflow(repo_path)
        
        print("\nWorkflow Result:")
        print("=" * 60)
        print(result)
        
    except Exception as e:
        print(f"Exception in write_new_content: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    main()