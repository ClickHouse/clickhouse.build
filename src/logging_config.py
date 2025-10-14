"""
Centralized logging configuration for ClickHouse Build tool.

This module provides a unified logging system that can be used by both
frontend (TUI) and backend components with consistent formatting and output.
"""

import logging
import logging.handlers
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class LogLevel(Enum):
    """Available log levels."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LoggerConfig:
    """Configuration for the centralized logging system."""

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_level: LogLevel = LogLevel.INFO,
        console_output: bool = True,
        file_output: bool = True,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        format_string: Optional[str] = None,
    ):
        """
        Initialize logger configuration.

        Args:
            log_dir: Directory for log files (default: ./logs)
            log_level: Minimum log level to capture
            console_output: Whether to output to console
            file_output: Whether to output to file
            max_file_size: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            format_string: Custom format string for log messages
        """
        self.log_dir = log_dir or Path.cwd() / "logs"
        self.log_level = log_level
        self.console_output = console_output
        self.file_output = file_output
        self.max_file_size = max_file_size
        self.backup_count = backup_count

        # Default format string
        if format_string is None:
            self.format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        else:
            self.format_string = format_string


class CentralizedLogger:
    """Centralized logging system for the application."""

    _instance: Optional["CentralizedLogger"] = None
    _initialized: bool = False

    def __new__(cls) -> "CentralizedLogger":
        """Singleton pattern to ensure only one logger instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the centralized logger (only once)."""
        if not self._initialized:
            self.config: Optional[LoggerConfig] = None
            self.loggers: Dict[str, logging.Logger] = {}
            self.handlers: Dict[str, logging.Handler] = {}
            self._initialized = True

    def setup(self, config: LoggerConfig) -> None:
        """
        Set up the centralized logging system.

        Args:
            config: LoggerConfig instance with logging configuration
        """
        self.config = config

        # Create log directory if it doesn't exist
        if config.file_output:
            config.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(config.log_level.value)

        # Clear existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(config.format_string)

        # Set up file handler
        if config.file_output:
            file_handler = logging.handlers.RotatingFileHandler(
                config.log_dir / "app.log",
                maxBytes=config.max_file_size,
                backupCount=config.backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(config.log_level.value)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            self.handlers["file"] = file_handler

        # Set up console handler
        if config.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(config.log_level.value)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            self.handlers["console"] = console_handler

        # Set up specific loggers for external libraries
        self._configure_external_loggers()

    def _configure_external_loggers(self) -> None:
        """Configure logging levels for external libraries."""
        # Reduce verbosity of external libraries
        external_loggers = {
            "asyncio": logging.WARNING,
            "urllib3": logging.WARNING,
            "requests": logging.WARNING,
            "boto3": logging.WARNING,
            "botocore": logging.WARNING,
            "strands": logging.INFO,
            "textual": logging.WARNING,
        }

        for logger_name, level in external_loggers.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for the specified name.

        Args:
            name: Name of the logger (usually module name)

        Returns:
            logging.Logger: Configured logger instance
        """
        if name not in self.loggers:
            logger = logging.getLogger(name)
            if self.config:
                logger.setLevel(self.config.log_level.value)
            self.loggers[name] = logger

        return self.loggers[name]

    def set_level(self, level: LogLevel) -> None:
        """
        Change the logging level for all loggers.

        Args:
            level: New log level to set
        """
        if self.config:
            self.config.log_level = level

        # Update root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level.value)

        # Update all handlers
        for handler in self.handlers.values():
            handler.setLevel(level.value)

        # Update all managed loggers
        for logger in self.loggers.values():
            logger.setLevel(level.value)

    def enable_console_output(self) -> None:
        """Enable console output."""
        if "console" not in self.handlers and self.config:
            formatter = logging.Formatter(self.config.format_string)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.config.log_level.value)
            console_handler.setFormatter(formatter)

            root_logger = logging.getLogger()
            root_logger.addHandler(console_handler)
            self.handlers["console"] = console_handler

    def add_file_handler(
        self, name: str, file_path: Path, level: LogLevel = LogLevel.INFO
    ) -> None:
        """
        Add an additional file handler for specific logging.

        Args:
            name: Name of the handler
            file_path: Path to the log file
            level: Log level for this handler
        """
        if self.config and name not in self.handlers:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=self.config.max_file_size,
                backupCount=self.config.backup_count,
                encoding="utf-8",
            )
            handler.setLevel(level.value)
            handler.setFormatter(logging.Formatter(self.config.format_string))

            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            self.handlers[name] = handler

    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the logging system.

        Returns:
            Dict with logging statistics
        """
        stats = {
            "initialized": self._initialized,
            "config": {
                "log_dir": str(self.config.log_dir) if self.config else None,
                "log_level": self.config.log_level.name if self.config else None,
                "console_output": self.config.console_output if self.config else None,
                "file_output": self.config.file_output if self.config else None,
            },
            "handlers": list(self.handlers.keys()),
            "loggers": list(self.loggers.keys()),
            "log_files": [],
        }

        # Get log file information
        if self.config and self.config.file_output:
            log_dir = self.config.log_dir
            if log_dir.exists():
                for log_file in log_dir.glob("*.log*"):
                    try:
                        stat = log_file.stat()
                        stats["log_files"].append(
                            {
                                "name": log_file.name,
                                "size": stat.st_size,
                                "modified": stat.st_mtime,
                            }
                        )
                    except Exception:
                        pass

        return stats


# Global logger instance
_central_logger: Optional[CentralizedLogger] = None


def setup_logging(
    log_dir: Optional[Path] = None,
    log_level: LogLevel = LogLevel.INFO,
    console_output: bool = True,
    file_output: bool = True,
) -> CentralizedLogger:
    """
    Set up the centralized logging system.

    Args:
        log_dir: Directory for log files
        log_level: Minimum log level to capture
        console_output: Whether to output to console
        file_output: Whether to output to file

    Returns:
        CentralizedLogger: The configured logger instance
    """
    global _central_logger

    if _central_logger is None:
        _central_logger = CentralizedLogger()

    config = LoggerConfig(
        log_dir=log_dir,
        log_level=log_level,
        console_output=console_output,
        file_output=file_output,
    )

    _central_logger.setup(config)
    return _central_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified name.

    Args:
        name: Name of the logger (usually module name)

    Returns:
        logging.Logger: Configured logger instance
    """
    global _central_logger

    if _central_logger is None:
        # Auto-initialize with default settings
        _central_logger = setup_logging()

    return _central_logger.get_logger(name)


def set_log_level(level: LogLevel) -> None:
    """
    Change the logging level for all loggers.

    Args:
        level: New log level to set
    """
    global _central_logger

    if _central_logger is not None:
        _central_logger.set_level(level)


def enable_console_logging() -> None:
    """Enable console output."""
    global _central_logger

    if _central_logger is not None:
        _central_logger.enable_console_output()


def get_central_logger() -> Optional[CentralizedLogger]:
    """Get the central logger instance."""
    return _central_logger


# Convenience functions for common log levels
def debug(name: str, message: str) -> None:
    """Log a debug message."""
    get_logger(name).debug(message)


def info(name: str, message: str) -> None:
    """Log an info message."""
    get_logger(name).info(message)


def warning(name: str, message: str) -> None:
    """Log a warning message."""
    get_logger(name).warning(message)


def error(name: str, message: str) -> None:
    """Log an error message."""
    get_logger(name).error(message)


def critical(name: str, message: str) -> None:
    """Log a critical message."""
    get_logger(name).critical(message)


# Store the current log file path
_current_log_file: Optional[str] = None


def get_current_log_file() -> Optional[str]:
    """Get the path to the current log file."""
    return _current_log_file


def get_chbuild_logger() -> tuple[logging.Logger, str]:
    """
    Configure colorful logging for CLI scripts using colorlog.

    Returns:
        tuple[logging.Logger, str]: The root logger configured with colorful output and the log file path
    """
    import colorlog
    from datetime import datetime

    # Console handler with colors
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
            secondary_log_colors={},
            style="%",
        )
    )

    # File handler for all logs
    log_dir = Path("/var/log/chbuild")

    # Try to create /var/log/chbuild, fall back to user's home directory if permission denied
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log_dir = Path.home() / ".chbuild" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"scanner_{timestamp}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)  # Capture INFO level and above to file
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set root logger to INFO
    logger.handlers.clear()  # Clear any existing handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    console_handler.setLevel(logging.WARNING)  # Only show warnings and above in console

    # Store the log file path globally
    global _current_log_file
    _current_log_file = str(log_file)

    return logger, str(log_file)
