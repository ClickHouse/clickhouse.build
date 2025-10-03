#!/usr/bin/env python3
"""
Parse and print EventLoopMetrics results in a readable format.
"""

import json
from typing import Any, Dict


def parse_and_print_event_metrics(metrics_obj):
    """
    Parse EventLoopMetrics object and print results in a formatted way.
    
    Args:
        metrics_obj: EventLoopMetrics object from Strands
    """
    print("🔍 EventLoopMetrics Analysis")
    print("=" * 60)
    
    # Get the summary from the metrics object
    if hasattr(metrics_obj, 'get_summary'):
        summary = metrics_obj.get_summary()
    else:
        print("❌ Object doesn't have get_summary() method")
        return
    
    # Print overall execution statistics
    print_execution_overview(summary)
    
    # Print token usage
    print_token_usage(summary)
    
    # Print tool usage details
    print_tool_usage(summary)
    
    # Print performance metrics
    print_performance_metrics(summary)


def print_execution_overview(summary: Dict[str, Any]):
    """Print overall execution statistics."""
    print("\n📊 Execution Overview")
    print("-" * 30)
    
    total_cycles = summary.get('total_cycles', 0)
    total_duration = summary.get('total_duration', 0)
    avg_cycle_time = summary.get('average_cycle_time', 0)
    
    print(f"Total Cycles: {total_cycles}")
    print(f"Total Duration: {total_duration:.3f} seconds")
    print(f"Average Cycle Time: {avg_cycle_time:.3f} seconds")
    
    if total_cycles > 0:
        print(f"Efficiency: {total_duration/total_cycles:.3f} seconds per cycle")


def print_token_usage(summary: Dict[str, Any]):
    """Print token usage statistics."""
    print("\n🎯 Token Usage")
    print("-" * 20)
    
    usage = summary.get('accumulated_usage', {})
    
    input_tokens = usage.get('inputTokens', 0)
    output_tokens = usage.get('outputTokens', 0)
    total_tokens = usage.get('totalTokens', 0)
    
    print(f"Input Tokens: {input_tokens:,}")
    print(f"Output Tokens: {output_tokens:,}")
    print(f"Total Tokens: {total_tokens:,}")
    
    # Cache tokens if available
    cache_read = usage.get('cacheReadInputTokens')
    cache_write = usage.get('cacheWriteInputTokens')
    
    if cache_read is not None:
        print(f"Cache Read Input Tokens: {cache_read:,}")
    if cache_write is not None:
        print(f"Cache Write Input Tokens: {cache_write:,}")
    
    # Calculate ratios
    if total_tokens > 0:
        input_ratio = (input_tokens / total_tokens) * 100
        output_ratio = (output_tokens / total_tokens) * 100
        print(f"Input/Output Ratio: {input_ratio:.1f}% / {output_ratio:.1f}%")


def print_tool_usage(summary: Dict[str, Any]):
    """Print detailed tool usage statistics."""
    print("\n🛠 Tool Usage Details")
    print("-" * 25)
    
    tool_usage = summary.get('tool_usage', {})
    
    if not tool_usage:
        print("No tools were used in this execution.")
        return
    
    for tool_name, tool_data in tool_usage.items():
        print(f"\n🔧 {tool_name}")
        print("   " + "─" * (len(tool_name) + 2))
        
        tool_info = tool_data.get('tool_info', {})
        exec_stats = tool_data.get('execution_stats', {})
        
        # Tool information
        tool_use_id = tool_info.get('tool_use_id', 'N/A')
        input_params = tool_info.get('input_params', {})
        
        print(f"   Tool Use ID: {tool_use_id}")
        if input_params:
            print(f"   Input Parameters: {json.dumps(input_params, indent=6)}")
        
        # Execution statistics
        call_count = exec_stats.get('call_count', 0)
        success_count = exec_stats.get('success_count', 0)
        error_count = exec_stats.get('error_count', 0)
        total_time = exec_stats.get('total_time', 0)
        avg_time = exec_stats.get('average_time', 0)
        success_rate = exec_stats.get('success_rate', 0)
        
        print(f"   Calls: {call_count}")
        print(f"   Successes: {success_count}")
        print(f"   Errors: {error_count}")
        print(f"   Success Rate: {success_rate:.1%}")
        print(f"   Total Time: {total_time:.3f} seconds")
        print(f"   Average Time: {avg_time:.3f} seconds")
        
        # Performance assessment
        if success_rate >= 0.9:
            status = "✅ Excellent"
        elif success_rate >= 0.7:
            status = "⚠️ Good"
        else:
            status = "❌ Needs Attention"
        print(f"   Status: {status}")


def print_execution_traces(summary: Dict[str, Any]):
    """Print execution trace information."""
    print("\n📋 Execution Traces")
    print("-" * 20)
    
    traces = summary.get('traces', [])
    
    if not traces:
        print("No execution traces available.")
        return
    
    for i, trace in enumerate(traces, 1):
        print(f"\n🔄 Trace {i}: {trace.get('name', 'Unknown')}")
        print_trace_details(trace, indent=1) 

def print_performance_metrics(summary: Dict[str, Any]):
    """Print performance metrics."""
    print("\n⚡ Performance Metrics")
    print("-" * 25)
    
    metrics = summary.get('accumulated_metrics', {})
    latency = metrics.get('latencyMs', 0)
    
    print(f"Total Latency: {latency} ms")
    
    # Calculate derived metrics
    total_cycles = summary.get('total_cycles', 0)
    if total_cycles > 0:
        avg_latency = latency / total_cycles
        print(f"Average Latency per Cycle: {avg_latency:.2f} ms")
    
    # Performance assessment
    if latency < 1000:  # Less than 1 second
        perf_status = "🚀 Excellent"
    elif latency < 5000:  # Less than 5 seconds
        perf_status = "✅ Good"
    elif latency < 15000:  # Less than 15 seconds
        perf_status = "⚠️ Acceptable"
    else:
        perf_status = "❌ Slow"
    
    print(f"Performance Status: {perf_status}")


def print_metrics_as_json(metrics_obj):
    """Print the raw metrics as formatted JSON."""
    print("\n📄 Raw Metrics (JSON)")
    print("-" * 25)
    
    if hasattr(metrics_obj, 'get_summary'):
        summary = metrics_obj.get_summary()
        print(json.dumps(summary, indent=2, default=str))
    else:
        print("❌ Cannot extract summary from metrics object")