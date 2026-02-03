"""
Configuration management module for Open News Insights.

This module provides configuration management capabilities including:
- Site-specific scraping configurations
- AWS service settings
- External API configuration
- Environment variable and file-based configuration loading
- Configuration validation and defaults
"""

from .models import SiteConfig, AWSSettings, ExternalAPIConfig, SystemConfig
from .manager import ConfigManager, get_config_manager, get_system_config
from .sites import (
    GUARDIAN_CONFIG, 
    TIMES_OF_INDIA_CONFIG, 
    GENERIC_CONFIG,
    get_site_config_by_domain,
    get_all_supported_domains
)
from .validation import (
    ConfigValidator,
    ValidationError,
    ConfigurationError,
    validate_configuration
)
from .defaults import (
    get_default_aws_settings,
    get_default_external_api_config,
    get_default_site_config,
    get_default_system_config,
    apply_configuration_defaults,
    create_minimal_config,
    create_development_config,
    create_production_config,
    create_test_config
)

__all__ = [
    # Data models
    "SiteConfig",
    "AWSSettings", 
    "ExternalAPIConfig",
    "SystemConfig",
    
    # Configuration manager
    "ConfigManager",
    "get_config_manager",
    "get_system_config",
    
    # Site configurations
    "GUARDIAN_CONFIG",
    "TIMES_OF_INDIA_CONFIG", 
    "GENERIC_CONFIG",
    "get_site_config_by_domain",
    "get_all_supported_domains",
    
    # Validation
    "ConfigValidator",
    "ValidationError",
    "ConfigurationError",
    "validate_configuration",
    
    # Defaults
    "get_default_aws_settings",
    "get_default_external_api_config",
    "get_default_site_config",
    "get_default_system_config",
    "apply_configuration_defaults",
    "create_minimal_config",
    "create_development_config",
    "create_production_config",
    "create_test_config"
]