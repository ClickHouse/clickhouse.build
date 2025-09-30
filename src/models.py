"""
Data models for the ClickHouse migration orchestrator.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class QueryConversion:
    """Represents a SQL query conversion from PostgreSQL to ClickHouse."""
    file_path: str
    original_query: str
    converted_query: str
    success: bool = True
    warnings: List[str] = None
    line_number: int = 0
    conversion_type: str = "postgresql_to_clickhouse"
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class FileModification:
    """Represents a file modification during migration."""
    path: str
    changes_count: int
    success: bool = True
    backup_path: Optional[str] = None
    operation: str = "update"  # "create", "update", "delete"
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class MigrationResults:
    """Represents the complete results of a migration process."""
    success: bool
    repo_path: str
    mode: str
    start_time: datetime
    end_time: datetime
    duration: str
    converted_queries: List[QueryConversion]
    modified_files: List[FileModification]
    clickpipe_config: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    orchestrator_output: str
    tool_results: Dict[str, Any]
    
    def __post_init__(self):
        if not hasattr(self, 'converted_queries') or self.converted_queries is None:
            self.converted_queries = []
        if not hasattr(self, 'modified_files') or self.modified_files is None:
            self.modified_files = []
        if not hasattr(self, 'warnings') or self.warnings is None:
            self.warnings = []
        if not hasattr(self, 'errors') or self.errors is None:
            self.errors = []
        if not hasattr(self, 'clickpipe_config') or self.clickpipe_config is None:
            self.clickpipe_config = {}
        if not hasattr(self, 'tool_results') or self.tool_results is None:
            self.tool_results = {}