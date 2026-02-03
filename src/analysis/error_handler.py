"""
Error handling utilities for AWS Bedrock integration.

This module provides retry logic, timeout handling, and error classification
for robust AWS service integration.
"""

import time
import logging
from typing import Callable, Any, Optional, Type
from functools import wraps
from dataclasses import dataclass

from botocore.exceptions import ClientError, BotoCoreError, ReadTimeoutError, ConnectTimeoutError


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class BedrockError(Exception):
    """Base exception for Bedrock-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable


class BedrockTimeoutError(BedrockError):
    """Exception for Bedrock timeout errors."""
    
    def __init__(self, message: str = "Bedrock request timed out"):
        super().__init__(message, error_code="TIMEOUT", retryable=True)


class BedrockRateLimitError(BedrockError):
    """Exception for Bedrock rate limit errors."""
    
    def __init__(self, message: str = "Bedrock rate limit exceeded"):
        super().__init__(message, error_code="RATE_LIMIT", retryable=True)


class BedrockServiceError(BedrockError):
    """Exception for Bedrock service errors."""
    
    def __init__(self, message: str, error_code: str, retryable: bool = False):
        super().__init__(message, error_code=error_code, retryable=retryable)


def classify_bedrock_error(error: Exception) -> BedrockError:
    """
    Classify AWS errors into appropriate Bedrock error types.
    
    Args:
        error: Original exception from AWS SDK
        
    Returns:
        Classified BedrockError with retry information
    """
    if isinstance(error, (ReadTimeoutError, ConnectTimeoutError)):
        return BedrockTimeoutError("Request timed out")
    
    if isinstance(error, ClientError):
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        
        # Retryable errors
        if error_code in ['ThrottlingException', 'TooManyRequestsException']:
            return BedrockRateLimitError(f"Rate limit: {error_message}")
        
        if error_code in ['InternalServerError', 'ServiceUnavailableException']:
            return BedrockServiceError(
                f"Service error: {error_message}",
                error_code=error_code,
                retryable=True
            )
        
        # Non-retryable errors
        if error_code in ['ValidationException', 'AccessDeniedException']:
            return BedrockServiceError(
                f"Client error: {error_message}",
                error_code=error_code,
                retryable=False
            )
        
        # Default to non-retryable for unknown client errors
        return BedrockServiceError(
            f"Unknown client error: {error_message}",
            error_code=error_code,
            retryable=False
        )
    
    if isinstance(error, BotoCoreError):
        return BedrockServiceError(
            f"SDK error: {str(error)}",
            error_code="SDK_ERROR",
            retryable=True
        )
    
    # Unknown error - assume non-retryable
    return BedrockServiceError(
        f"Unknown error: {str(error)}",
        error_code="UNKNOWN",
        retryable=False
    )


def with_retry(retry_config: RetryConfig):
    """
    Decorator to add retry logic to functions.
    
    Args:
        retry_config: Retry configuration
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None
            
            for attempt in range(retry_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    classified_error = classify_bedrock_error(e)
                    last_error = classified_error
                    
                    if attempt == retry_config.max_retries:
                        logger.error(f"Max retries ({retry_config.max_retries}) exceeded for {func.__name__}")
                        raise classified_error
                    
                    if not classified_error.retryable:
                        logger.error(f"Non-retryable error in {func.__name__}: {classified_error}")
                        raise classified_error
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        retry_config.base_delay * (retry_config.exponential_base ** attempt),
                        retry_config.max_delay
                    )
                    
                    if retry_config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{retry_config.max_retries + 1} failed for {func.__name__}: "
                        f"{classified_error}. Retrying in {delay:.2f}s"
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_error or BedrockServiceError("Unknown retry error")
        
        return wrapper
    return decorator