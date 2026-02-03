"""
Site-specific configurations for news scraping.

This module contains predefined configurations for supported news websites,
including CSS selectors and fallback mechanisms for content extraction.
"""

from .models import SiteConfig


# Guardian US/UK configuration
GUARDIAN_CONFIG = SiteConfig(
    domain="theguardian.com",
    title_selector="h1[data-gu-name='headline'], h1.content__headline",
    content_selector="div[data-gu-name='body'] p, div.content__article-body p",
    author_selector="a[rel='author'], .byline a, address a",
    date_selector="time[datetime], .content__dateline time",
    fallback_selectors=[
        "article p",
        ".article-body p",
        ".content p",
        "main p"
    ]
)

# Times of India configuration
TIMES_OF_INDIA_CONFIG = SiteConfig(
    domain="timesofindia.indiatimes.com",
    title_selector="h1.HNMDR, h1._2yWcd, h1",
    content_selector="div._s30J p, div.ga-headlines p, .Normal p",
    author_selector=".byline, .author-name, .writer-name",
    date_selector=".publish-date, .date-line, time",
    fallback_selectors=[
        "article p",
        ".story-content p",
        ".article-content p",
        "main p"
    ]
)

# Generic fallback configuration for unknown sites
GENERIC_CONFIG = SiteConfig(
    domain="*",
    title_selector="h1, .title, .headline",
    content_selector="article p, .content p, .article-body p, .story p",
    author_selector=".author, .byline, .writer",
    date_selector="time, .date, .published",
    fallback_selectors=[
        "p",
        "div p",
        "main p",
        "section p"
    ]
)

# Registry of all supported site configurations
SITE_CONFIGS = {
    "theguardian.com": GUARDIAN_CONFIG,
    "www.theguardian.com": GUARDIAN_CONFIG,
    "timesofindia.indiatimes.com": TIMES_OF_INDIA_CONFIG,
    "www.timesofindia.indiatimes.com": TIMES_OF_INDIA_CONFIG,
    "*": GENERIC_CONFIG  # Fallback for unknown domains
}


def get_site_config_by_domain(domain: str) -> SiteConfig:
    """
    Get site configuration for a specific domain.
    
    Args:
        domain: The domain name to get configuration for
        
    Returns:
        SiteConfig object for the domain, or generic config if not found
    """
    # Normalize domain (remove www. prefix if present)
    normalized_domain = domain.lower()
    if normalized_domain.startswith("www."):
        normalized_domain = normalized_domain[4:]
    
    # Try exact match first
    if normalized_domain in SITE_CONFIGS:
        return SITE_CONFIGS[normalized_domain]
    
    # Try with www. prefix
    www_domain = f"www.{normalized_domain}"
    if www_domain in SITE_CONFIGS:
        return SITE_CONFIGS[www_domain]
    
    # Return generic fallback
    return SITE_CONFIGS["*"]


def get_all_supported_domains() -> list[str]:
    """Get list of all explicitly supported domains."""
    return [domain for domain in SITE_CONFIGS.keys() if domain != "*"]