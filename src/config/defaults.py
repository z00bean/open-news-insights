"""
Default configuration values and factory functions.

This module provides default configurations and factory functions for creating
configuration objects with sensible defaults when values are missing or invalid.
"""

import os
from typing import Dict, Optional

from .models import SiteConfig, AWSSettings, ExternalAPIConfig, SystemConfig


def get_default_aws_settings() -> AWSSettings:
    """
    Get default AWS settings with environment-aware defaults.
    
    Returns:
        AWSSettings with sensible defaults
    """
    # Determine default region based on environment
    default_region = "us-east-1"
    if aws_region := os.getenv("AWS_DEFAULT_REGION"):
        default_region = aws_region
    elif aws_region := os.getenv("AWS_REGION"):
        default_region = aws_region
    
    return AWSSettings(
        region=default_region,
        bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
        comprehend_language_code="en",
        max_retries=3,
        timeout_seconds=30,
        bedrock_max_tokens=1000,
        bedrock_temperature=0.1,
        comprehend_max_bytes=5000
    )


def get_default_external_api_config() -> ExternalAPIConfig:
    """
    Get default external API configuration.
    
    Returns:
        ExternalAPIConfig with sensible defaults
    """
    return ExternalAPIConfig(
        endpoint_url=None,  # Must be configured by user
        auth_header=None,   # Must be configured by user
        timeout_seconds=15,
        max_retries=5,
        retry_delay_seconds=1.0
    )


def get_default_site_config(domain: str) -> SiteConfig:
    """
    Get a default site configuration for unknown domains.
    
    Args:
        domain: Domain name for the configuration
        
    Returns:
        SiteConfig with generic selectors
    """
    return SiteConfig(
        domain=domain,
        title_selector="h1, .title, .headline, .article-title",
        content_selector="article p, .content p, .article-body p, .story p, .post-content p",
        author_selector=".author, .byline, .writer, .author-name",
        date_selector="time, .date, .published, .publish-date, .timestamp",
        fallback_selectors=[
            "p",
            "div p", 
            "main p",
            "section p",
            ".text p",
            ".body p"
        ]
    )


def get_default_system_config() -> SystemConfig:
    """
    Get complete default system configuration.
    
    Returns:
        SystemConfig with all default values
    """
    from .sites import SITE_CONFIGS
    
    return SystemConfig(
        site_configs=SITE_CONFIGS.copy(),
        aws_settings=get_default_aws_settings(),
        external_api_config=get_default_external_api_config(),
        default_timeout_seconds=30,
        max_content_length=1000000,  # 1MB
        enable_logging=True,
        log_level="INFO"
    )


def apply_configuration_defaults(config: SystemConfig) -> SystemConfig:
    """
    Apply default values to missing or invalid configuration fields.
    
    Args:
        config: SystemConfig to apply defaults to
        
    Returns:
        SystemConfig with defaults applied
    """
    defaults = get_default_system_config()
    
    # Apply AWS settings defaults
    if not config.aws_settings.region:
        config.aws_settings.region = defaults.aws_settings.region
    
    if not config.aws_settings.bedrock_model_id:
        config.aws_settings.bedrock_model_id = defaults.aws_settings.bedrock_model_id
    
    if not config.aws_settings.comprehend_language_code:
        config.aws_settings.comprehend_language_code = defaults.aws_settings.comprehend_language_code
    
    if config.aws_settings.max_retries < 0:
        config.aws_settings.max_retries = defaults.aws_settings.max_retries
    
    if config.aws_settings.timeout_seconds <= 0:
        config.aws_settings.timeout_seconds = defaults.aws_settings.timeout_seconds
    
    # Apply external API defaults
    if config.external_api_config.timeout_seconds <= 0:
        config.external_api_config.timeout_seconds = defaults.external_api_config.timeout_seconds
    
    if config.external_api_config.max_retries < 0:
        config.external_api_config.max_retries = defaults.external_api_config.max_retries
    
    if config.external_api_config.retry_delay_seconds < 0:
        config.external_api_config.retry_delay_seconds = defaults.external_api_config.retry_delay_seconds
    
    # Apply system-level defaults
    if config.default_timeout_seconds <= 0:
        config.default_timeout_seconds = defaults.default_timeout_seconds
    
    if config.max_content_length <= 0:
        config.max_content_length = defaults.max_content_length
    
    if not config.log_level or config.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        config.log_level = defaults.log_level
    
    # Ensure we have at least the default site configurations
    if not config.site_configs:
        config.site_configs = defaults.site_configs.copy()
    else:
        # Add missing default site configs
        for domain, site_config in defaults.site_configs.items():
            if domain not in config.site_configs:
                config.site_configs[domain] = site_config
    
    return config


def create_minimal_config() -> SystemConfig:
    """
    Create a minimal configuration suitable for testing or development.
    
    Returns:
        SystemConfig with minimal settings
    """
    return SystemConfig(
        site_configs={
            "*": get_default_site_config("*")
        },
        aws_settings=AWSSettings(
            region="us-east-1",
            bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
            comprehend_language_code="en"
        ),
        external_api_config=ExternalAPIConfig(),
        default_timeout_seconds=10,
        max_content_length=100000,  # 100KB for testing
        enable_logging=False,
        log_level="WARNING"
    )


# Environment-specific configuration factories
def create_development_config() -> SystemConfig:
    """Create configuration optimized for development environment."""
    config = get_default_system_config()
    config.enable_logging = True
    config.log_level = "DEBUG"
    config.aws_settings.timeout_seconds = 10  # Shorter timeouts for dev
    config.external_api_config.timeout_seconds = 5
    return config


def create_production_config() -> SystemConfig:
    """Create configuration optimized for production environment."""
    config = get_default_system_config()
    config.enable_logging = True
    config.log_level = "INFO"
    config.aws_settings.max_retries = 5  # More retries in production
    config.external_api_config.max_retries = 10
    return config


def create_test_config() -> SystemConfig:
    """Create configuration optimized for testing."""
    config = create_minimal_config()
    config.enable_logging = False
    config.log_level = "CRITICAL"  # Minimal logging during tests
    config.aws_settings.timeout_seconds = 1  # Very short timeouts
    config.external_api_config.timeout_seconds = 1
    return config