"""
Logs Widget for displaying real-time logs in the chat interface.
"""

from textual.widgets import RichLog, Static
from textual.containers import Vertical
from textual.reactive import reactive
from textual.binding import Binding
from rich.text import Text
from datetime import datetime
from typing import List, Dict, Any
import logging


class LogsWidget(Vertical):
    """Widget for displaying real-time logs with filtering capabilities."""
    
    # Reactive attributes
    log_count = reactive(0)
    visible = reactive(True)
    
    BINDINGS = [
        Binding("c", "clear_logs", "Clear", show=True),
        Binding("f", "toggle_filter", "Filter", show=True),
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_entries: List[Dict[str, Any]] = []
        self.log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.current_filter = "INFO"  # Show INFO and above by default
        self.max_logs = 1000  # Limit log entries to prevent memory issues
        
    def compose(self):
        """Create the logs widget layout."""
        yield Static("📋 Migration Logs", classes="logs-title")
        yield RichLog(
            id="logs-display",
            classes="logs-display",
            markup=True,
            highlight=True,
            auto_scroll=True
        )
        yield Static(
            f"Filter: {self.current_filter}+ | Count: {self.log_count} | 'c'=clear, 'f'=filter | Ctrl+↑/↓=resize",
            id="logs-status",
            classes="logs-status"
        )
    
    def add_log_entry(self, level: str, message: str, logger_name: str = "", timestamp: datetime = None) -> None:
        """Add a log entry to the display."""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Check if log level should be displayed
        if not self._should_show_level(level):
            return
        
        # Store log entry
        log_entry = {
            'level': level,
            'message': message,
            'logger_name': logger_name,
            'timestamp': timestamp
        }
        
        self.log_entries.append(log_entry)
        
        # Limit log entries
        if len(self.log_entries) > self.max_logs:
            self.log_entries = self.log_entries[-self.max_logs:]
        
        # Display the log entry
        self._display_log_entry(log_entry)
        
        self.log_count += 1
        self._update_status()
    
    def _should_show_level(self, level: str) -> bool:
        """Check if a log level should be displayed based on current filter."""
        try:
            level_num = getattr(logging, level.upper())
            filter_num = getattr(logging, self.current_filter.upper())
            return level_num >= filter_num
        except AttributeError:
            return True  # Show unknown levels
    
    def _display_log_entry(self, log_entry: Dict[str, Any]) -> None:
        """Display a single log entry in the logs display."""
        logs_display = self.query_one("#logs-display", RichLog)
        
        timestamp_str = log_entry['timestamp'].strftime("%H:%M:%S")
        level = log_entry['level']
        message = log_entry['message']
        logger_name = log_entry['logger_name']
        
        # Color coding for different log levels
        level_colors = {
            'DEBUG': 'dim white',
            'INFO': 'cyan',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold red'
        }
        
        level_color = level_colors.get(level.upper(), 'white')
        
        # Format the log entry
        log_text = Text()
        log_text.append(f"[{timestamp_str}] ", style="dim")
        log_text.append(f"{level:8} ", style=level_color)
        
        if logger_name:
            log_text.append(f"{logger_name}: ", style="dim blue")
        
        log_text.append(message, style="white")
        
        logs_display.write(log_text)
    
    def _update_status(self) -> None:
        """Update the status bar."""
        status_widget = self.query_one("#logs-status", Static)
        status_text = f"Filter: {self.current_filter}+ | Count: {self.log_count} | Press 'c' to clear, 'f' to filter"
        status_widget.update(status_text)
    
    def action_clear_logs(self) -> None:
        """Clear all log entries."""
        logs_display = self.query_one("#logs-display", RichLog)
        logs_display.clear()
        self.log_entries.clear()
        self.log_count = 0
        self._update_status()
    
    def action_toggle_filter(self) -> None:
        """Toggle between different log level filters."""
        current_index = self.log_levels.index(self.current_filter)
        next_index = (current_index + 1) % len(self.log_levels)
        self.current_filter = self.log_levels[next_index]
        
        # Refresh display with new filter
        self.refresh_display()
        self._update_status()
    
    def refresh_display(self) -> None:
        """Refresh the display with current filter settings."""
        logs_display = self.query_one("#logs-display", RichLog)
        logs_display.clear()
        
        # Re-display all log entries that match current filter
        for log_entry in self.log_entries:
            if self._should_show_level(log_entry['level']):
                self._display_log_entry(log_entry)
    
    def set_filter_level(self, level: str) -> None:
        """Set the log filter level."""
        if level.upper() in self.log_levels:
            self.current_filter = level.upper()
            self.refresh_display()
            self._update_status()
    
    def toggle_visibility(self) -> None:
        """Toggle the visibility of the logs widget."""
        self.visible = not self.visible
        if self.visible:
            self.display = True
            self.add_class("logs-visible")
            self.remove_class("logs-hidden")
        else:
            self.display = False
            self.add_class("logs-hidden")
            self.remove_class("logs-visible")
    
    def get_log_summary(self) -> Dict[str, int]:
        """Get a summary of log counts by level."""
        summary = {level: 0 for level in self.log_levels}
        
        for log_entry in self.log_entries:
            level = log_entry['level'].upper()
            if level in summary:
                summary[level] += 1
        
        return summary


class LogHandler(logging.Handler):
    """Custom log handler that sends logs to the LogsWidget."""
    
    def __init__(self, logs_widget: LogsWidget):
        super().__init__()
        self.logs_widget = logs_widget
        
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the logs widget."""
        try:
            message = self.format(record)
            level = record.levelname
            logger_name = record.name
            timestamp = datetime.fromtimestamp(record.created)
            
            # Send to logs widget
            self.logs_widget.add_log_entry(level, message, logger_name, timestamp)
            
        except Exception:
            # Don't let logging errors crash the app
            pass