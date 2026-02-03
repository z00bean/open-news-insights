"""
Configuration data models for Open News Insights system.

This module defines the core data structures used for configuration management,
including site-specific scraping configurations and AWS service settings.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class SiteConfig:
    """Configuration for site-specific news scraping."""
    
    domain: str
    title_selector: str
    content_selector: str
    author_selector: Optional[str] = None
    date_selector: Optional[str] = None
    fallback_selectors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.domain:
            raise ValueError("Domain cannot be empty")
        if not self.title_selector:
            raise ValueError("Title selector cannot be empty")
        if not self.content_selector:
            raise ValueError("Content selector cannot be empty")


@dataclass
class AWSSettings:
    """Configuration for AWS service integration."""
    
    region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    comprehend_language_code: str = "en"
    max_retries: int = 3
    timeout_seconds: int = 30
    
    # Service-specific settings
    bedrock_max_tokens: int = 1000
    bedrock_temperature: float = 0.1
    comprehend_max_bytes: int = 5000
    
    def __post_init__(self):
        """Validate AWS settings after initialization."""
        if not self.region:
            raise ValueError("AWS region cannot be empty")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")


@dataclass
class ExternalAPIConfig:
    """Configuration for external API integration."""
    
    endpoint_url: Optional[str] = None
    auth_header: Optional[str] = None
    timeout_seconds: int = 15
    max_retries: int = 5
    retry_delay_seconds: float = 1.0
    
    def __post_init__(self):
        """Validate external API configuration."""
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        if self.retry_delay_seconds < 0:
            raise ValueError("Retry delay must be non-negative")


@dataclass
class SystemConfig:
    """Overall system configuration combining all settings."""
    
    site_configs: Dict[str, SiteConfig] = field(default_factory=dict)
    aws_settings: AWSSettings = field(default_factory=AWSSettings)
    external_api_config: ExternalAPIConfig = field(default_factory=ExternalAPIConfig)
    
    # Processing defaults
    default_timeout_seconds: int = 30
    max_content_length: int = 1000000  # 1MB
    enable_logging: bool = True
    log_level: str = "INFO"
    
    def get_site_config(self, domain: str) -> Optional[SiteConfig]:
        """Get site configuration for a domain."""
        return self.site_configs.get(domain)
    
    def add_site_config(self, config: SiteConfig) -> None:
        """Add a site configuration."""
        self.site_configs[config.domain] = config