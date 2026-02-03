"""
Configuration manager for loading and managing system configuration.

This module provides the ConfigManager class that handles loading configuration
from environment variables, files, and default values with proper validation.
"""

import os
import json
from typing import Dict, Optional, Any
from pathlib import Path

from .models import SystemConfig, AWSSettings, ExternalAPIConfig, SiteConfig
from .sites import SITE_CONFIGS, get_site_config_by_domain
from .validation import validate_configuration, ConfigurationError
from .defaults import apply_configuration_defaults, get_default_system_config


class ConfigManager:
    """Manages system configuration loading and validation."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Optional directory path for configuration files
        """
        self.config_dir = Path(config_dir) if config_dir else Path("config")
        self._system_config: Optional[SystemConfig] = None
    
    def load_configuration(self) -> SystemConfig:
        """
        Load complete system configuration from all sources.
        
        Returns:
            SystemConfig object with all loaded settings
        """
        if self._system_config is None:
            self._system_config = self._build_system_config()
        return self._system_config
    
    def _build_system_config(self) -> SystemConfig:
        """Build system configuration from all sources."""
        try:
            # Load AWS settings
            aws_settings = self._load_aws_settings()
            
            # Load external API configuration
            external_api_config = self._load_external_api_config()
            
            # Load site configurations (start with defaults, then override)
            site_configs = self._load_site_configs()
            
            # Create system configuration
            system_config = SystemConfig(
                site_configs=site_configs,
                aws_settings=aws_settings,
                external_api_config=external_api_config
            )
            
            # Apply environment-specific overrides
            self._apply_environment_overrides(system_config)
            
            # Apply defaults for any missing or invalid values
            system_config = apply_configuration_defaults(system_config)
            
            # Validate the final configuration
            validation_errors = validate_configuration(system_config, raise_on_error=False)
            if validation_errors:
                # Log validation errors but don't fail - use defaults
                print(f"Configuration validation warnings: {len(validation_errors)} issues found")
                for error in validation_errors[:5]:  # Show first 5 errors
                    print(f"  - {error}")
                if len(validation_errors) > 5:
                    print(f"  ... and {len(validation_errors) - 5} more")
            
            return system_config
            
        except Exception as e:
            # If configuration loading fails completely, return safe defaults
            print(f"Configuration loading failed: {e}. Using default configuration.")
            return get_default_system_config()
    
    def _load_aws_settings(self) -> AWSSettings:
        """Load AWS settings from environment variables and files."""
        # Start with defaults
        settings = AWSSettings()
        
        # Override with environment variables
        if region := os.getenv("AWS_REGION"):
            settings.region = region
        
        if model_id := os.getenv("BEDROCK_MODEL_ID"):
            settings.bedrock_model_id = model_id
        
        if lang_code := os.getenv("COMPREHEND_LANGUAGE_CODE"):
            settings.comprehend_language_code = lang_code
        
        if max_retries := os.getenv("AWS_MAX_RETRIES"):
            try:
                settings.max_retries = int(max_retries)
            except ValueError:
                pass  # Keep default
        
        if timeout := os.getenv("AWS_TIMEOUT_SECONDS"):
            try:
                settings.timeout_seconds = int(timeout)
            except ValueError:
                pass  # Keep default
        
        # Load from configuration file if exists
        aws_config_file = self.config_dir / "aws_settings.json"
        if aws_config_file.exists():
            try:
                with open(aws_config_file, 'r') as f:
                    file_config = json.load(f)
                    self._update_aws_settings_from_dict(settings, file_config)
            except (json.JSONDecodeError, IOError):
                pass  # Keep current settings
        
        return settings
    
    def _load_external_api_config(self) -> ExternalAPIConfig:
        """Load external API configuration from environment variables."""
        config = ExternalAPIConfig()
        
        if endpoint := os.getenv("EXTERNAL_API_ENDPOINT"):
            config.endpoint_url = endpoint
        
        if auth_header := os.getenv("EXTERNAL_API_AUTH_HEADER"):
            config.auth_header = auth_header
        
        if timeout := os.getenv("EXTERNAL_API_TIMEOUT"):
            try:
                config.timeout_seconds = int(timeout)
            except ValueError:
                pass
        
        if max_retries := os.getenv("EXTERNAL_API_MAX_RETRIES"):
            try:
                config.max_retries = int(max_retries)
            except ValueError:
                pass
        
        return config
    
    def _load_site_configs(self) -> Dict[str, SiteConfig]:
        """Load site configurations from defaults and custom files."""
        # Start with built-in site configurations
        configs = SITE_CONFIGS.copy()
        
        # Load custom site configurations if file exists
        custom_sites_file = self.config_dir / "custom_sites.json"
        if custom_sites_file.exists():
            try:
                with open(custom_sites_file, 'r') as f:
                    custom_configs = json.load(f)
                    for domain, config_data in custom_configs.items():
                        try:
                            site_config = SiteConfig(
                                domain=domain,
                                title_selector=config_data["title_selector"],
                                content_selector=config_data["content_selector"],
                                author_selector=config_data.get("author_selector"),
                                date_selector=config_data.get("date_selector"),
                                fallback_selectors=config_data.get("fallback_selectors", [])
                            )
                            configs[domain] = site_config
                        except (KeyError, ValueError):
                            continue  # Skip invalid configurations
            except (json.JSONDecodeError, IOError):
                pass  # Keep default configurations
        
        return configs
    
    def _apply_environment_overrides(self, config: SystemConfig) -> None:
        """Apply environment-specific configuration overrides."""
        # System-level overrides
        if log_level := os.getenv("LOG_LEVEL"):
            config.log_level = log_level.upper()
        
        if enable_logging := os.getenv("ENABLE_LOGGING"):
            config.enable_logging = enable_logging.lower() in ("true", "1", "yes")
        
        if max_content := os.getenv("MAX_CONTENT_LENGTH"):
            try:
                config.max_content_length = int(max_content)
            except ValueError:
                pass
    
    def _update_aws_settings_from_dict(self, settings: AWSSettings, config_dict: Dict[str, Any]) -> None:
        """Update AWS settings from dictionary data."""
        if "region" in config_dict:
            settings.region = config_dict["region"]
        if "bedrock_model_id" in config_dict:
            settings.bedrock_model_id = config_dict["bedrock_model_id"]
        if "comprehend_language_code" in config_dict:
            settings.comprehend_language_code = config_dict["comprehend_language_code"]
        if "max_retries" in config_dict:
            settings.max_retries = int(config_dict["max_retries"])
        if "timeout_seconds" in config_dict:
            settings.timeout_seconds = int(config_dict["timeout_seconds"])
        if "bedrock_max_tokens" in config_dict:
            settings.bedrock_max_tokens = int(config_dict["bedrock_max_tokens"])
        if "bedrock_temperature" in config_dict:
            settings.bedrock_temperature = float(config_dict["bedrock_temperature"])
        if "comprehend_max_bytes" in config_dict:
            settings.comprehend_max_bytes = int(config_dict["comprehend_max_bytes"])
    
    def get_site_config(self, domain: str) -> SiteConfig:
        """
        Get site configuration for a domain.
        
        Args:
            domain: Domain name to get configuration for
            
        Returns:
            SiteConfig for the domain
        """
        config = self.load_configuration()
        return get_site_config_by_domain(domain)
    
    def reload_configuration(self) -> SystemConfig:
        """Force reload of configuration from all sources."""
        self._system_config = None
        return self.load_configuration()
    
    def validate_current_configuration(self, raise_on_error: bool = False) -> bool:
        """
        Validate the current configuration.
        
        Args:
            raise_on_error: If True, raise ConfigurationError on validation failure
            
        Returns:
            True if configuration is valid, False otherwise
            
        Raises:
            ConfigurationError: If validation fails and raise_on_error is True
        """
        config = self.load_configuration()
        errors = validate_configuration(config, raise_on_error=raise_on_error)
        return len(errors) == 0


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_system_config() -> SystemConfig:
    """Get the current system configuration."""
    return get_config_manager().load_configuration()