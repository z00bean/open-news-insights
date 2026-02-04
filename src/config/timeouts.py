"""
Comprehensive timeout configuration for all external calls.

This module provides centralized timeout management for HTTP requests,
AWS service calls, and external API interactions with appropriate
timeout values for different operation types.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import os


@dataclass
class TimeoutConfig:
    """Comprehensive timeout configuration for all external operations."""
    
    # HTTP request timeouts
    http_connect_timeout: int = 10  # Connection establishment timeout
    http_read_timeout: int = 30     # Data read timeout
    http_total_timeout: int = 45    # Total request timeout
    
    # AWS service timeouts
    aws_connect_timeout: int = 10   # AWS service connection timeout
    aws_read_timeout: int = 60      # AWS service read timeout (longer for LLM calls)
    aws_bedrock_timeout: int = 90   # Bedrock-specific timeout (LLM processing)
    aws_comprehend_timeout: int = 30 # Comprehend-specific timeout
    
    # External API timeouts
    external_api_connect_timeout: int = 5   # External API connection timeout
    external_api_read_timeout: int = 15     # External API read timeout
    external_api_total_timeout: int = 20    # Total external API timeout
    
    # Lambda execution timeouts
    lambda_max_execution_time: int = 900    # 15 minutes (AWS Lambda max)
    lambda_warning_threshold: int = 600     # 10 minutes (warn when approaching limit)
    
    # Retry timeouts
    retry_base_delay: float = 1.0           # Base delay between retries
    retry_max_delay: float = 30.0           # Maximum delay between retries
    retry_exponential_base: float = 2.0     # Exponential backoff multiplier
    
    @classmethod
    def from_environment(cls) -> 'TimeoutConfig':
        """Create timeout configuration from environment variables."""
        return cls(
            # HTTP timeouts
            http_connect_timeout=int(os.getenv('HTTP_CONNECT_TIMEOUT', '10')),
            http_read_timeout=int(os.getenv('HTTP_READ_TIMEOUT', '30')),
            http_total_timeout=int(os.getenv('HTTP_TOTAL_TIMEOUT', '45')),
            
            # AWS timeouts
            aws_connect_timeout=int(os.getenv('AWS_CONNECT_TIMEOUT', '10')),
            aws_read_timeout=int(os.getenv('AWS_READ_TIMEOUT', '60')),
            aws_bedrock_timeout=int(os.getenv('AWS_BEDROCK_TIMEOUT', '90')),
            aws_comprehend_timeout=int(os.getenv('AWS_COMPREHEND_TIMEOUT', '30')),
            
            # External API timeouts
            external_api_connect_timeout=int(os.getenv('EXTERNAL_API_CONNECT_TIMEOUT', '5')),
            external_api_read_timeout=int(os.getenv('EXTERNAL_API_READ_TIMEOUT', '15')),
            external_api_total_timeout=int(os.getenv('EXTERNAL_API_TOTAL_TIMEOUT', '20')),
            
            # Lambda timeouts
            lambda_max_execution_time=int(os.getenv('LAMBDA_MAX_EXECUTION_TIME', '900')),
            lambda_warning_threshold=int(os.getenv('LAMBDA_WARNING_THRESHOLD', '600')),
            
            # Retry timeouts
            retry_base_delay=float(os.getenv('RETRY_BASE_DELAY', '1.0')),
            retry_max_delay=float(os.getenv('RETRY_MAX_DELAY', '30.0')),
            retry_exponential_base=float(os.getenv('RETRY_EXPONENTIAL_BASE', '2.0'))
        )
    
    def get_http_timeout_tuple(self) -> tuple:
        """Get HTTP timeout as (connect, read) tuple for requests library."""
        return (self.http_connect_timeout, self.http_read_timeout)
    
    def get_aws_timeout_dict(self, service: str = "default") -> Dict[str, int]:
        """Get AWS timeout configuration for boto3 Config."""
        if service == "bedrock":
            read_timeout = self.aws_bedrock_timeout
        elif service == "comprehend":
            read_timeout = self.aws_comprehend_timeout
        else:
            read_timeout = self.aws_read_timeout
        
        return {
            'connect_timeout': self.aws_connect_timeout,
            'read_timeout': read_timeout
        }
    
    def get_external_api_timeout_tuple(self) -> tuple:
        """Get external API timeout as (connect, read) tuple."""
        return (self.external_api_connect_timeout, self.external_api_read_timeout)
    
    def validate(self) -> None:
        """Validate timeout configuration values."""
        if self.http_connect_timeout <= 0:
            raise ValueError("HTTP connect timeout must be positive")
        if self.http_read_timeout <= 0:
            raise ValueError("HTTP read timeout must be positive")
        if self.http_total_timeout <= self.http_connect_timeout:
            raise ValueError("HTTP total timeout must be greater than connect timeout")
        
        if self.aws_connect_timeout <= 0:
            raise ValueError("AWS connect timeout must be positive")
        if self.aws_read_timeout <= 0:
            raise ValueError("AWS read timeout must be positive")
        if self.aws_bedrock_timeout <= 0:
            raise ValueError("AWS Bedrock timeout must be positive")
        if self.aws_comprehend_timeout <= 0:
            raise ValueError("AWS Comprehend timeout must be positive")
        
        if self.external_api_connect_timeout <= 0:
            raise ValueError("External API connect timeout must be positive")
        if self.external_api_read_timeout <= 0:
            raise ValueError("External API read timeout must be positive")
        if self.external_api_total_timeout <= self.external_api_connect_timeout:
            raise ValueError("External API total timeout must be greater than connect timeout")
        
        if self.lambda_max_execution_time <= 0:
            raise ValueError("Lambda max execution time must be positive")
        if self.lambda_warning_threshold >= self.lambda_max_execution_time:
            raise ValueError("Lambda warning threshold must be less than max execution time")
        
        if self.retry_base_delay < 0:
            raise ValueError("Retry base delay must be non-negative")
        if self.retry_max_delay < self.retry_base_delay:
            raise ValueError("Retry max delay must be greater than or equal to base delay")
        if self.retry_exponential_base <= 1:
            raise ValueError("Retry exponential base must be greater than 1")


class TimeoutManager:
    """
    Centralized timeout management for the application.
    
    Provides timeout configuration and monitoring capabilities
    for all external operations.
    """
    
    def __init__(self, config: Optional[TimeoutConfig] = None):
        """
        Initialize timeout manager.
        
        Args:
            config: Optional timeout configuration. If None, loads from environment.
        """
        self.config = config or TimeoutConfig.from_environment()
        self.config.validate()
    
    def get_http_timeout(self, operation_type: str = "default") -> tuple:
        """
        Get HTTP timeout configuration for specific operation types.
        
        Args:
            operation_type: Type of HTTP operation (scraping, api_call, etc.)
            
        Returns:
            Tuple of (connect_timeout, read_timeout)
        """
        if operation_type == "scraping":
            # Longer timeout for scraping operations
            return (self.config.http_connect_timeout, self.config.http_read_timeout)
        elif operation_type == "api_call":
            # Shorter timeout for API calls
            return (self.config.external_api_connect_timeout, self.config.external_api_read_timeout)
        else:
            return self.config.get_http_timeout_tuple()
    
    def get_aws_timeout(self, service: str) -> Dict[str, int]:
        """
        Get AWS service timeout configuration.
        
        Args:
            service: AWS service name (bedrock, comprehend, etc.)
            
        Returns:
            Dictionary with timeout configuration for boto3
        """
        return self.config.get_aws_timeout_dict(service)
    
    def get_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff.
        
        Args:
            attempt: Retry attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = self.config.retry_base_delay * (self.config.retry_exponential_base ** attempt)
        return min(delay, self.config.retry_max_delay)
    
    def is_lambda_timeout_approaching(self, elapsed_seconds: float) -> bool:
        """
        Check if Lambda execution is approaching timeout.
        
        Args:
            elapsed_seconds: Seconds elapsed since Lambda start
            
        Returns:
            True if approaching timeout threshold
        """
        return elapsed_seconds >= self.config.lambda_warning_threshold
    
    def get_remaining_lambda_time(self, elapsed_seconds: float) -> float:
        """
        Get remaining Lambda execution time.
        
        Args:
            elapsed_seconds: Seconds elapsed since Lambda start
            
        Returns:
            Remaining seconds before timeout
        """
        return max(0, self.config.lambda_max_execution_time - elapsed_seconds)


# Global timeout manager instance
_timeout_manager: Optional[TimeoutManager] = None


def get_timeout_manager() -> TimeoutManager:
    """Get the global timeout manager instance."""
    global _timeout_manager
    if _timeout_manager is None:
        _timeout_manager = TimeoutManager()
    return _timeout_manager


def configure_timeouts(config: Optional[TimeoutConfig] = None) -> None:
    """Configure global timeout manager."""
    global _timeout_manager
    _timeout_manager = TimeoutManager(config)