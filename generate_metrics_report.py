#!/usr/bin/env python3
"""
Generate comprehensive metrics reports from EventLoopMetrics objects.
"""

import json
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def generate_comprehensive_metrics_report(
    metrics_obj, 
    workflow_name: str, 
    repo_path: str, 
    output_dir: str = ".chbuild/metrics_reports"
) -> str:
    """
    Generate a comprehensive metrics report and save it to file.
    
    Args:
        metrics_obj: EventLoopMetrics object from Strands
        workflow_name: Name of the workflow (e.g., "MAIN_WORKFLOW", "PLANNING_WORKFLOW")
        repo_path: Path to the repository being analyzed
        output_dir: Directory to save the report
        
    Returns:
        Path to the generated report file
    """
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workflow_clean = workflow_name.lower().replace(" ", "_")
    report_file = output_path / f"metrics_report_{workflow_clean}_{timestamp}.md"
    
    # Generate report content
    report_content = _generate_report_content(metrics_obj, workflow_name, repo_path)
    
    # Write to file
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📊 Comprehensive metrics report saved to: {report_file}")
    return str(report_file)


def _generate_report_content(metrics_obj, workflow_name: str, repo_path: str) -> str:
    """Generate the full report content."""
    
    # Header
    content = f"""# Metrics Report: {workflow_name}

**Generated:** {datetime.now().isoformat()}  
**Repository:** {repo_path}  
**Workflow:** {workflow_name}

---

"""
    
    # Executive Summary
    content += _generate_executive_summary(metrics_obj)
    
    # Detailed Analysis
    content += _generate_detailed_analysis(metrics_obj)
    
    # Performance Assessment
    content += _generate_performance_assessment(metrics_obj)
    
    # Recommendations
    content += _generate_recommendations(metrics_obj)
    
    # Raw Data
    content += _generate_raw_data_section(metrics_obj)
    
    return content


def _generate_executive_summary(metrics_obj) -> str:
    """Generate executive summary section."""
    
    try:
        summary = metrics_obj.get_summary()
        
        total_duration = summary.get('total_duration', 0)
        total_cycles = summary.get('total_cycles', 0)
        total_tokens = summary.get('accumulated_usage', {}).get('totalTokens', 0)
        tool_count = len(summary.get('tool_usage', {}))
        
        # Calculate success rate
        tool_usage = summary.get('tool_usage', {})
        total_calls = sum(data['execution_stats']['call_count'] for data in tool_usage.values())
        total_successes = sum(data['execution_stats']['success_count'] for data in tool_usage.values())
        success_rate = (total_successes / total_calls * 100) if total_calls > 0 else 0
        
        content = f"""## 📊 Executive Summary

| Metric | Value |
|--------|-------|
| **Total Duration** | {total_duration:.2f} seconds |
| **Execution Cycles** | {total_cycles} |
| **Tools Used** | {tool_count} |
| **Total Token Usage** | {total_tokens:,} |
| **Overall Success Rate** | {success_rate:.1f}% |
| **Average Cycle Time** | {summary.get('average_cycle_time', 0):.2f} seconds |

"""
        
    except Exception as e:
        content = f"""## 📊 Executive Summary

❌ **Error generating summary:** {e}

"""
    
    return content


def _generate_detailed_analysis(metrics_obj) -> str:
    """Generate detailed analysis using the parse_event_metrics functions."""
    
    content = "## 🔍 Detailed Analysis\n\n"
    
    try:
        from parse_event_metrics import (
            print_execution_overview, 
            print_token_usage, 
            print_tool_usage, 
            print_execution_traces, 
            print_performance_metrics
        )
        
        # Capture the detailed analysis output
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        # Get summary for detailed analysis
        summary = metrics_obj.get_summary()
        
        print_execution_overview(summary)
        print_token_usage(summary)
        print_tool_usage(summary)
        print_execution_traces(summary)
        print_performance_metrics(summary)
        
        # Restore stdout and get the captured output
        sys.stdout = old_stdout
        detailed_analysis = captured_output.getvalue()
        
        # Convert to markdown format
        content += "```\n" + detailed_analysis + "\n```\n\n"
        
    except ImportError:
        content += "⚠️ **Detailed analysis not available.** Install `parse_event_metrics.py` for enhanced analysis.\n\n"
    except Exception as e:
        content += f"❌ **Error generating detailed analysis:** {e}\n\n"
    
    return content


def _generate_performance_assessment(metrics_obj) -> str:
    """Generate performance assessment and bottleneck analysis."""
    
    content = "## ⚡ Performance Assessment\n\n"
    
    try:
        summary = metrics_obj.get_summary()
        tool_usage = summary.get('tool_usage', {})
        
        content += "### Tool Performance Analysis\n\n"
        content += "| Tool | Calls | Success Rate | Avg Time | Status |\n"
        content += "|------|-------|--------------|----------|--------|\n"
        
        for tool_name, data in tool_usage.items():
            stats = data['execution_stats']
            success_rate = stats['success_rate'] * 100
            avg_time = stats['average_time']
            
            # Determine status
            if success_rate >= 95 and avg_time < 10:
                status = "🟢 Excellent"
            elif success_rate >= 85 and avg_time < 30:
                status = "🟡 Good"
            elif success_rate >= 70:
                status = "🟠 Acceptable"
            else:
                status = "🔴 Issues"
            
            content += f"| {tool_name} | {stats['call_count']} | {success_rate:.1f}% | {avg_time:.2f}s | {status} |\n"
        
        content += "\n"
        
        # Identify bottlenecks
        content += "### Bottleneck Analysis\n\n"
        
        slowest_tools = sorted(
            tool_usage.items(), 
            key=lambda x: x[1]['execution_stats']['average_time'], 
            reverse=True
        )[:3]
        
        if slowest_tools:
            content += "**Slowest Tools:**\n"
            for tool_name, data in slowest_tools:
                avg_time = data['execution_stats']['average_time']
                content += f"- **{tool_name}**: {avg_time:.2f}s average\n"
            content += "\n"
        
        # Token efficiency
        usage = summary.get('accumulated_usage', {})
        input_tokens = usage.get('inputTokens', 0)
        output_tokens = usage.get('outputTokens', 0)
        
        if input_tokens > 0 and output_tokens > 0:
            efficiency = output_tokens / input_tokens
            content += f"**Token Efficiency:** {efficiency:.2f} (output/input ratio)\n\n"
        
    except Exception as e:
        content += f"❌ **Error generating performance assessment:** {e}\n\n"
    
    return content


def _generate_recommendations(metrics_obj) -> str:
    """Generate optimization recommendations."""
    
    content = "## 💡 Optimization Recommendations\n\n"
    
    try:
        summary = metrics_obj.get_summary()
        tool_usage = summary.get('tool_usage', {})
        total_duration = summary.get('total_duration', 0)
        
        recommendations = []
        
        # Check for slow tools
        for tool_name, data in tool_usage.items():
            stats = data['execution_stats']
            if stats['average_time'] > 30:
                recommendations.append(f"🐌 **Optimize {tool_name}**: Average execution time is {stats['average_time']:.1f}s")
        
        # Check for low success rates
        for tool_name, data in tool_usage.items():
            stats = data['execution_stats']
            if stats['success_rate'] < 0.9:
                recommendations.append(f"⚠️ **Improve {tool_name} reliability**: Success rate is {stats['success_rate']:.1%}")
        
        # Check token usage
        usage = summary.get('accumulated_usage', {})
        total_tokens = usage.get('totalTokens', 0)
        if total_tokens > 50000:
            recommendations.append(f"💰 **Optimize token usage**: {total_tokens:,} tokens used - consider caching or prompt optimization")
        
        # Check overall duration
        if total_duration > 120:
            recommendations.append(f"⏱️ **Reduce execution time**: Total duration is {total_duration:.1f}s - consider parallel processing")
        
        # Check cycle efficiency
        cycles = summary.get('total_cycles', 0)
        if cycles > 5:
            recommendations.append(f"🔄 **Optimize workflow**: {cycles} cycles executed - consider consolidating operations")
        
        if recommendations:
            for rec in recommendations:
                content += f"- {rec}\n"
        else:
            content += "✅ **No major optimization opportunities identified.** Performance looks good!\n"
        
        content += "\n"
        
        # General best practices
        content += "### General Best Practices\n\n"
        content += "- Monitor token usage to control costs\n"
        content += "- Implement caching for repeated operations\n"
        content += "- Add retry logic for unreliable tools\n"
        content += "- Use parallel processing where possible\n"
        content += "- Regularly review and optimize slow tools\n\n"
        
    except Exception as e:
        content += f"❌ **Error generating recommendations:** {e}\n\n"
    
    return content


def _generate_raw_data_section(metrics_obj) -> str:
    """Generate raw data section."""
    
    content = "## 📄 Raw Metrics Data\n\n"
    
    try:
        summary = metrics_obj.get_summary()
        
        content += "```json\n"
        content += json.dumps(summary, indent=2, default=str)
        content += "\n```\n\n"
        
    except Exception as e:
        content += f"❌ **Error generating raw data:** {e}\n\n"
    
    return content


def main():
    """Example usage of the metrics report generator."""
    print("""
📊 Metrics Report Generator

This tool generates comprehensive metrics reports from EventLoopMetrics objects.

Usage:
    from generate_metrics_report import generate_comprehensive_metrics_report
    
    # After running your agent
    result = agent(prompt)
    if hasattr(result, 'metrics'):
        report_path = generate_comprehensive_metrics_report(
            result.metrics,
            "MY_WORKFLOW",
            "/path/to/repo"
        )
        print(f"Report saved to: {report_path}")

The generated report includes:
- Executive summary with key metrics
- Detailed analysis of execution, tokens, and tools
- Performance assessment and bottleneck analysis
- Optimization recommendations
- Raw metrics data in JSON format
""")


if __name__ == "__main__":
    main()