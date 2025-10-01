"""
Steps Widget for displaying migration progress.
"""

from textual.widgets import Static
from textual.containers import Vertical
from textual.reactive import reactive
from rich.text import Text
from typing import List, Dict, Any


class StepsWidget(Vertical):
    """Widget for displaying migration steps and their status."""
    
    # Reactive attributes
    current_step = reactive(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Define migration steps
        self.steps = [
            "Install ClickHouse Client",
            "Analyze Repository", 
            "Convert Queries",
            "Write Updated Files",
            "Generate ClickPipe Config"
        ]
        
        # Track step status
        self.step_status = ['pending'] * len(self.steps)
        self.step_details = [''] * len(self.steps)
        
    def compose(self):
        """Create the steps display."""
        # Create step displays
        for i, step in enumerate(self.steps):
            yield Static(
                self._format_step(i, step, 'pending', ''),
                id=f"step-{i}",
                classes="step-item"
            )
        
        # Overall progress summary
        yield Static("", id="progress-summary")
    
    def _format_step(self, index: int, step: str, status: str, detail: str) -> Text:
        """Format a step with appropriate styling."""
        text = Text()
        
        # Status icons
        icons = {
            'pending': '[PENDING]',
            'running': '[RUNNING]',
            'completed': '[COMPLETED]',
            'failed': '[FAILED]',
            'skipped': '[SKIPPED]'
        }
        
        # Colors
        colors = {
            'pending': 'dim white',
            'running': 'bold yellow',
            'completed': 'bold green',
            'failed': 'bold red',
            'skipped': 'dim yellow'
        }
        
        icon = icons.get(status, '⏳')
        color = colors.get(status, 'white')
        
        # Format: "✅ 1. Install ClickHouse Client"
        text.append(f"{icon} {index + 1}. ", style=color)
        text.append(step, style=color)
        
        # Add detail if available
        if detail:
            text.append(f"\n   {detail}", style="dim")
        
        return text
    
    def set_step_status(self, step_index: int, status: str, detail: str = "") -> None:
        """Update the status of a specific step."""
        if 0 <= step_index < len(self.steps):
            self.step_status[step_index] = status
            self.step_details[step_index] = detail
            
            # Update the step display
            step_widget = self.query_one(f"#step-{step_index}", Static)
            formatted_step = self._format_step(
                step_index, 
                self.steps[step_index], 
                status, 
                detail
            )
            step_widget.update(formatted_step)
            
            # Update current step tracker
            if status == 'running':
                self.current_step = step_index
            
            # Update progress summary
            self._update_progress_summary()
    
    def _update_progress_summary(self) -> None:
        """Update the overall progress summary."""
        completed = sum(1 for status in self.step_status if status == 'completed')
        failed = sum(1 for status in self.step_status if status == 'failed')
        running = sum(1 for status in self.step_status if status == 'running')
        
        summary_text = Text()
        summary_text.append("\n📊 Progress: ", style="bold white")
        summary_text.append(f"{completed}/{len(self.steps)} completed", style="green")
        
        if failed > 0:
            summary_text.append(f", {failed} failed", style="red")
        if running > 0:
            summary_text.append(f", {running} running", style="yellow")
        
        # Calculate percentage
        percentage = (completed / len(self.steps)) * 100
        summary_text.append(f"\n🎯 {percentage:.0f}% complete", style="cyan")
        
        summary_widget = self.query_one("#progress-summary", Static)
        summary_widget.update(summary_text)
    
    def reset_all_steps(self) -> None:
        """Reset all steps to pending status."""
        for i in range(len(self.steps)):
            self.set_step_status(i, 'pending', '')
        
        self.current_step = 0
    
    def get_current_step(self) -> int:
        """Get the index of the currently running step."""
        return self.current_step
    
    def get_step_status(self, step_index: int) -> str:
        """Get the status of a specific step."""
        if 0 <= step_index < len(self.step_status):
            return self.step_status[step_index]
        return 'pending'
    
    def is_migration_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(status == 'completed' for status in self.step_status)
    
    def has_failures(self) -> bool:
        """Check if any steps have failed."""
        return any(status == 'failed' for status in self.step_status)