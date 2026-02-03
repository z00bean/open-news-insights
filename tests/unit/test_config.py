"""
Unit tests for configuration management functionality.
"""

import pytest
import os
from unittest.mock import patch, mock_open
from src.config.manager import ConfigManager, get_config_manager, get_system_config
from src.config.models import SystemConfig, AWSSettings, ExternalAPIConfig
from src.config.sites import get_site_config_by_domain, get_all_supported_domains
from src.config.validation import ConfigValidator, ValidationError


class TestConfigManager:
    """Test cases for ConfigManager class."""
    
    def test_init_default(self):
        """Test config manager initialization with defaults."""
        manager = ConfigManager()
        assert manager.config_dir.name == "config"
        assert manager._system_config is None
    
    def test_init_custom_dir(self):
        """Test config manager initialization with custom directory."""
        manager = ConfigManager("/custom/config")
        assert str(manager.config_dir) == "/custom/config"
    
    @patch.dict(os.environ, {
        'AWS_REGION': 'us-west-2',
        'BEDROCK_MODEL_ID': 'custom-model',
        'LOG_LEVEL': 'DEBUG'
    })
    def test_load_configuration_from_env(self):
        """Test loading configuration from environment variables."""
        manager = ConfigManager()
        config = manager.load_configuration()
        
        assert isinstance(config, SystemConfig)
        assert config.aws_settings.region == 'us-west-2'
        assert config.aws_settings.bedrock_model_id == 'custom-model'
        assert config.log_level == 'DEBUG'
    
    def test_load_configuration_caching(self):
        """Test that configuration is cached after first load."""
        manager = ConfigManager()
        
        # First load
        config1 = manager.load_configuration()
        
        # Second load should return same instance
        config2 = manager.load_configuration()
        
        assert config1 is config2
    
    def test_reload_configuration(self):
        """Test configuration reloading."""
        manager = ConfigManager()
        
        # Load initial config
        config1 = manager.load_configuration()
        
        # Reload should create new instance
        config2 = manager.reload_configuration()
        
        assert config1 is not config2
        assert isinstance(config2, SystemConfig)
    
    def test_get_site_config(self):
        """Test site configuration retrieval."""
        manager = ConfigManager()
        
        # Test known domain
        config = manager.get_site_config("theguardian.com")
        assert config.domain == "theguardian.com"
        
        # Test unknown domain (should get generic)
        config = manager.get_site_config("unknown.com")
        assert config.domain == "*"
    
    @patch('builtins.open', mock_open(read_data='{"region": "eu-west-1"}'))
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_aws_settings_from_file(self, mock_exists):
        """Test loading AWS settings from configuration file."""
        manager = ConfigManager()
        settings = manager._load_aws_settings()
        
        assert settings.region == "eu-west-1"
    
    @patch.dict(os.environ, {
        'EXTERNAL_API_ENDPOINT': 'https://api.example.com',
        'EXTERNAL_API_TIMEOUT': '45'
    })
    def test_load_external_api_config(self):
        """Test loading external API configuration."""
        manager = ConfigManager()
        config = manager._load_external_api_config()
        
        assert config.endpoint_url == 'https://api.example.com'
        assert config.timeout_seconds == 45


class TestSiteConfiguration:
    """Test cases for site configuration functionality."""
    
    def test_get_site_config_by_domain(self):
        """Test site configuration retrieval by domain."""
        # Test Guardian
        config = get_site_config_by_domain("theguardian.com")
        assert config.domain == "theguardian.com"
        assert "headline" in config.title_selector
        
        # Test with www prefix
        config = get_site_config_by_domain("www.theguardian.com")
        assert config.domain == "theguardian.com"
        
        # Test Times of India
        config = get_site_config_by_domain("timesofindia.indiatimes.com")
        assert config.domain == "timesofindia.indiatimes.com"
        
        # Test unknown domain
        config = get_site_config_by_domain("unknown.com")
        assert config.domain == "*"
    
    def test_get_all_supported_domains(self):
        """Test getting all supported domains."""
        domains = get_all_supported_domains()
        
        assert isinstance(domains, list)
        assert len(domains) > 0
        assert "theguardian.com" in domains
        assert "timesofindia.indiatimes.com" in domains
        assert "*" not in domains  # Generic config should not be included


class TestConfigValidation:
    """Test cases for configuration validation."""
    
    def test_validate_site_config_valid(self):
        """Test validation of valid site configuration."""
        from src.config.models import SiteConfig
        
        config = SiteConfig(
            domain="example.com",
            title_selector="h1",
            content_selector="article p",
            author_selector=".author",
            date_selector="time"
        )
        
        errors = ConfigValidator.validate_site_config(config)
        assert len(errors) == 0
    
    def test_validate_site_config_invalid(self):
        """Test validation of invalid site configuration."""
        from src.config.models import SiteConfig
        
        # Test with invalid domain - should raise ValueError during construction
        with pytest.raises(ValueError, match="Domain cannot be empty"):
            SiteConfig(
                domain="",  # Invalid empty domain
                title_selector="h1",
                content_selector="article p"
            )
        
        # Test with invalid title selector - should raise ValueError during construction
        with pytest.raises(ValueError, match="Title selector cannot be empty"):
            SiteConfig(
                domain="example.com",
                title_selector="",  # Invalid empty selector
                content_selector="article p"
            )
        
        # Test validation of a valid config with the validator
        config = SiteConfig(
            domain="example.com",
            title_selector="h1",
            content_selector="article p"
        )
        
        errors = ConfigValidator.validate_site_config(config)
        assert len(errors) == 0  # Should be valid
    
    def test_validate_aws_settings_valid(self):
        """Test validation of valid AWS settings."""
        settings = AWSSettings(
            region="us-east-1",
            bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
            comprehend_language_code="en"
        )
        
        errors = ConfigValidator.validate_aws_settings(settings)
        assert len(errors) == 0
    
    def test_validate_aws_settings_invalid(self):
        """Test validation of invalid AWS settings."""
        settings = AWSSettings(
            region="invalid-region",  # Invalid region format
            bedrock_model_id="",  # Empty model ID
            comprehend_language_code="invalid"  # Invalid language code
        )
        
        errors = ConfigValidator.validate_aws_settings(settings)
        assert len(errors) > 0


class TestGlobalConfigFunctions:
    """Test cases for global configuration functions."""
    
    def test_get_config_manager_singleton(self):
        """Test that get_config_manager returns singleton instance."""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, ConfigManager)
    
    def test_get_system_config(self):
        """Test get_system_config function."""
        config = get_system_config()
        
        assert isinstance(config, SystemConfig)
        assert hasattr(config, 'aws_settings')
        assert hasattr(config, 'site_configs')
        assert hasattr(config, 'external_api_config')