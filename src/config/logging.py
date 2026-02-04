"""
Comprehensive logging configuration for Open News Insights.

This module provides structured logging with timing information, error details,
and troubleshooting information for all significant operations.
"""

import json
import logging
import logging.config
import time
from typing import Dict, Any, Optional, Union
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, asdict


@dataclass
class LogContext:
    """Context information for structured logging."""
    
    request_id: Optional[str] = None
    url: Optional[str] = None
    feature_flags: Optional[Dict[str, bool]] = None
    processing_step: Optional[str] = None
    component: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class TimingInfo:
    """Timing information for operations."""
    
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    
    def finish(self) -> None:
        """Mark operation as finished and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None
        }


class StructuredLogger:
    """
    Structured logger with context and timing support.
    
    Provides consistent structured logging across all components with
    context information, timing data, and error details.
    """
    
    def __init__(self, name: str, context: Optional[LogContext] = None):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (typically module name)
            context: Optional context information
        """
        self.logger = logging.getLogger(name)
        self.context = context or LogContext()
        self._active_timings: Dict[str, TimingInfo] = {}
    
    def set_context(self, **kwargs) -> None:
        """Update logging context."""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
    
    def _format_message(self, message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format message with context and extra data."""
        log_data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "context": self.context.to_dict()
        }
        
        if extra:
            log_data.update(extra)
        
        return log_data
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with structured data."""
        log_data = self._format_message(message, kwargs)
        self.logger.info(json.dumps(log_data, default=str))
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with structured data."""
        log_data = self._format_message(message, kwargs)
        self.logger.warning(json.dumps(log_data, default=str))
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs) -> None:
        """Log error message with structured data and error details."""
        log_data = self._format_message(message, kwargs)
        
        if error:
            log_data["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "details": getattr(error, 'details', {})
            }
        
        self.logger.error(json.dumps(log_data, default=str))
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with structured data."""
        log_data = self._format_message(message, kwargs)
        self.logger.debug(json.dumps(log_data, default=str))
    
    def start_timing(self, operation: str) -> str:
        """Start timing an operation."""
        timing_id = f"{operation}_{int(time.time() * 1000)}"
        self._active_timings[timing_id] = TimingInfo(
            operation=operation,
            start_time=time.time()
        )
        
        self.debug(f"Started {operation}", timing_id=timing_id)
        return timing_id
    
    def end_timing(self, timing_id: str, success: bool = True, **kwargs) -> Optional[TimingInfo]:
        """End timing an operation and log results."""
        if timing_id not in self._active_timings:
            self.warning(f"Unknown timing ID: {timing_id}")
            return None
        
        timing = self._active_timings.pop(timing_id)
        timing.finish()
        
        log_level = "info" if success else "warning"
        status = "completed" if success else "failed"
        
        getattr(self, log_level)(
            f"Operation {timing.operation} {status}",
            timing=timing.to_dict(),
            success=success,
            **kwargs
        )
        
        return timing
    
    @contextmanager
    def timed_operation(self, operation: str, **kwargs):
        """Context manager for timing operations."""
        timing_id = self.start_timing(operation)
        success = False
        error = None
        
        try:
            yield
            success = True
        except Exception as e:
            error = e
            raise
        finally:
            self.end_timing(timing_id, success=success, error=str(error) if error else None, **kwargs)
    
    def log_metrics(self, metrics: Dict[str, Union[int, float, str]], operation: Optional[str] = None) -> None:
        """Log performance and processing metrics."""
        self.info(
            f"Metrics for {operation or 'operation'}",
            metrics=metrics,
            metric_type="performance"
        )
    
    def log_aws_service_call(
        self,
        service: str,
        operation: str,
        duration_ms: int,
        success: bool,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log AWS service call with timing and result information."""
        self.info(
            f"AWS {service} {operation} {'succeeded' if success else 'failed'}",
            aws_service=service,
            aws_operation=operation,
            duration_ms=duration_ms,
            success=success,
            error=error,
            **kwargs
        )
    
    def log_http_request(
        self,
        method: str,
        url: str,
        status_code: int,
        duration_ms: int,
        success: bool,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log HTTP request with timing and result information."""
        self.info(
            f"HTTP {method} {url} -> {status_code}",
            http_method=method,
            http_url=url,
            http_status=status_code,
            duration_ms=duration_ms,
            success=success,
            error=error,
            **kwargs
        )


def configure_logging(log_level: str = "INFO", enable_structured: bool = True) -> None:
    """
    Configure application logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_structured: Whether to enable structured JSON logging
    """
    if enable_structured:
        # Structured JSON logging configuration
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structured": {
                    "format": "%(message)s"
                },
                "simple": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "structured" if enable_structured else "simple",
                    "stream": "ext://sys.stdout"
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["console"]
            },
            "loggers": {
                "boto3": {
                    "level": "WARNING"
                },
                "botocore": {
                    "level": "WARNING"
                },
                "urllib3": {
                    "level": "WARNING"
                },
                "requests": {
                    "level": "WARNING"
                }
            }
        }
    else:
        # Simple logging configuration
        config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "simple": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "simple",
                    "stream": "ext://sys.stdout"
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["console"]
            }
        }
    
    logging.config.dictConfig(config)


def get_logger(name: str, context: Optional[LogContext] = None) -> StructuredLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        context: Optional context information
        
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name, context)


# Initialize logging on module import
configure_logging()