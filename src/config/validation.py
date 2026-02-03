"""
Configuration validation utilities.

This module provides validation functions and error classes for configuration
management, ensuring that all configuration values are valid and complete.
"""

from typing import List, Dict, Any, Optional
import re
from urllib.parse import urlparse

from .models import SiteConfig, AWSSettings, ExternalAPIConfig, SystemConfig


class ConfigurationError(Exception):
    """Base exception for configuration-related errors."""
    pass


class ValidationError(ConfigurationError):
    """Exception raised when configuration validation fails."""
    
    def __init__(self, field: str, message: str, value: Any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Validation error for '{field}': {message}")


class ConfigValidator:
    """Validates configuration objects and provides detailed error reporting."""
    
    @staticmethod
    def validate_site_config(config: SiteConfig) -> List[ValidationError]:
        """
        Validate a SiteConfig object.
        
        Args:
            config: SiteConfig to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate domain
        if not config.domain or not config.domain.strip():
            errors.append(ValidationError("domain", "Domain cannot be empty"))
        elif config.domain != "*":  # Allow wildcard domain
            if not ConfigValidator._is_valid_domain(config.domain):
                errors.append(ValidationError("domain", "Invalid domain format", config.domain))
        
        # Validate selectors
        if not config.title_selector or not config.title_selector.strip():
            errors.append(ValidationError("title_selector", "Title selector cannot be empty"))
        
        if not config.content_selector or not config.content_selector.strip():
            errors.append(ValidationError("content_selector", "Content selector cannot be empty"))
        
        # Validate CSS selector syntax (basic check)
        for selector_name, selector_value in [
            ("title_selector", config.title_selector),
            ("content_selector", config.content_selector),
            ("author_selector", config.author_selector),
            ("date_selector", config.date_selector)
        ]:
            if selector_value and not ConfigValidator._is_valid_css_selector(selector_value):
                errors.append(ValidationError(
                    selector_name, 
                    "Invalid CSS selector syntax", 
                    selector_value
                ))
        
        # Validate fallback selectors
        if config.fallback_selectors:
            for i, selector in enumerate(config.fallback_selectors):
                if not selector or not selector.strip():
                    errors.append(ValidationError(
                        f"fallback_selectors[{i}]", 
                        "Fallback selector cannot be empty"
                    ))
                elif not ConfigValidator._is_valid_css_selector(selector):
                    errors.append(ValidationError(
                        f"fallback_selectors[{i}]", 
                        "Invalid CSS selector syntax", 
                        selector
                    ))
        
        return errors
    
    @staticmethod
    def validate_aws_settings(settings: AWSSettings) -> List[ValidationError]:
        """
        Validate AWSSettings object.
        
        Args:
            settings: AWSSettings to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate region
        if not settings.region or not settings.region.strip():
            errors.append(ValidationError("region", "AWS region cannot be empty"))
        elif not ConfigValidator._is_valid_aws_region(settings.region):
            errors.append(ValidationError("region", "Invalid AWS region format", settings.region))
        
        # Validate model ID
        if not settings.bedrock_model_id or not settings.bedrock_model_id.strip():
            errors.append(ValidationError("bedrock_model_id", "Bedrock model ID cannot be empty"))
        
        # Validate language code
        if not settings.comprehend_language_code or not settings.comprehend_language_code.strip():
            errors.append(ValidationError("comprehend_language_code", "Language code cannot be empty"))
        elif not ConfigValidator._is_valid_language_code(settings.comprehend_language_code):
            errors.append(ValidationError(
                "comprehend_language_code", 
                "Invalid language code format", 
                settings.comprehend_language_code
            ))
        
        # Validate numeric values
        if settings.max_retries < 0:
            errors.append(ValidationError("max_retries", "Max retries must be non-negative", settings.max_retries))
        elif settings.max_retries > 10:
            errors.append(ValidationError("max_retries", "Max retries should not exceed 10", settings.max_retries))
        
        if settings.timeout_seconds <= 0:
            errors.append(ValidationError("timeout_seconds", "Timeout must be positive", settings.timeout_seconds))
        elif settings.timeout_seconds > 300:
            errors.append(ValidationError("timeout_seconds", "Timeout should not exceed 300 seconds", settings.timeout_seconds))
        
        if settings.bedrock_max_tokens <= 0:
            errors.append(ValidationError("bedrock_max_tokens", "Max tokens must be positive", settings.bedrock_max_tokens))
        
        if not (0.0 <= settings.bedrock_temperature <= 1.0):
            errors.append(ValidationError("bedrock_temperature", "Temperature must be between 0.0 and 1.0", settings.bedrock_temperature))
        
        if settings.comprehend_max_bytes <= 0:
            errors.append(ValidationError("comprehend_max_bytes", "Max bytes must be positive", settings.comprehend_max_bytes))
        
        return errors
    
    @staticmethod
    def validate_external_api_config(config: ExternalAPIConfig) -> List[ValidationError]:
        """
        Validate ExternalAPIConfig object.
        
        Args:
            config: ExternalAPIConfig to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate endpoint URL if provided
        if config.endpoint_url:
            if not ConfigValidator._is_valid_url(config.endpoint_url):
                errors.append(ValidationError("endpoint_url", "Invalid URL format", config.endpoint_url))
        
        # Validate numeric values
        if config.timeout_seconds <= 0:
            errors.append(ValidationError("timeout_seconds", "Timeout must be positive", config.timeout_seconds))
        
        if config.max_retries < 0:
            errors.append(ValidationError("max_retries", "Max retries must be non-negative", config.max_retries))
        elif config.max_retries > 20:
            errors.append(ValidationError("max_retries", "Max retries should not exceed 20", config.max_retries))
        
        if config.retry_delay_seconds < 0:
            errors.append(ValidationError("retry_delay_seconds", "Retry delay must be non-negative", config.retry_delay_seconds))
        
        return errors
    
    @staticmethod
    def validate_system_config(config: SystemConfig) -> List[ValidationError]:
        """
        Validate complete SystemConfig object.
        
        Args:
            config: SystemConfig to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate AWS settings
        errors.extend(ConfigValidator.validate_aws_settings(config.aws_settings))
        
        # Validate external API config
        errors.extend(ConfigValidator.validate_external_api_config(config.external_api_config))
        
        # Validate all site configs
        for domain, site_config in config.site_configs.items():
            site_errors = ConfigValidator.validate_site_config(site_config)
            # Prefix errors with domain for clarity
            for error in site_errors:
                errors.append(ValidationError(
                    f"site_configs[{domain}].{error.field}",
                    error.message,
                    error.value
                ))
        
        # Validate system-level settings
        if config.default_timeout_seconds <= 0:
            errors.append(ValidationError("default_timeout_seconds", "Default timeout must be positive", config.default_timeout_seconds))
        
        if config.max_content_length <= 0:
            errors.append(ValidationError("max_content_length", "Max content length must be positive", config.max_content_length))
        
        if config.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            errors.append(ValidationError("log_level", "Invalid log level", config.log_level))
        
        return errors
    
    @staticmethod
    def _is_valid_domain(domain: str) -> bool:
        """Check if domain has valid format."""
        domain_pattern = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
        )
        return bool(domain_pattern.match(domain))
    
    @staticmethod
    def _is_valid_css_selector(selector: str) -> bool:
        """Basic validation of CSS selector syntax."""
        if not selector or not selector.strip():
            return False
        
        # Basic checks for common CSS selector patterns
        # This is a simplified validation - real CSS parsing would be more complex
        invalid_chars = ['<', '>', '{', '}', '(', ')']
        return not any(char in selector for char in invalid_chars)
    
    @staticmethod
    def _is_valid_aws_region(region: str) -> bool:
        """Check if AWS region has valid format."""
        region_pattern = re.compile(r'^[a-z0-9-]+$')
        return bool(region_pattern.match(region)) and len(region) >= 3
    
    @staticmethod
    def _is_valid_language_code(code: str) -> bool:
        """Check if language code has valid format (ISO 639-1)."""
        return len(code) == 2 and code.isalpha() and code.islower()
    
    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if URL has valid format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False


def validate_configuration(config: SystemConfig, raise_on_error: bool = False) -> List[ValidationError]:
    """
    Validate a complete system configuration.
    
    Args:
        config: SystemConfig to validate
        raise_on_error: If True, raise ConfigurationError on validation failure
        
    Returns:
        List of validation errors (empty if valid)
        
    Raises:
        ConfigurationError: If validation fails and raise_on_error is True
    """
    errors = ConfigValidator.validate_system_config(config)
    
    if errors and raise_on_error:
        error_messages = [str(error) for error in errors]
        raise ConfigurationError(f"Configuration validation failed:\n" + "\n".join(error_messages))
    
    return errors