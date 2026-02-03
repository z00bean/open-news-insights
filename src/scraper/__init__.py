"""
News scraper module for Open News Insights.

This module provides comprehensive news scraping capabilities including
HTTP fetching with retry logic, HTML parsing with site-specific selectors,
text extraction with boilerplate removal, and fallback mechanisms for content extraction.
"""

# Lazy imports to avoid dependency issues during testing
__all__ = [
    'NewsScraper',
    'ScrapedContent',
    'HTTPFetcher', 
    'FetchResult',
    'HTMLParser',
    'ParsedContent',
    'TextExtractor',
    'ExtractedContent'
]

def __getattr__(name):
    if name == 'NewsScraper':
        from .scraper import NewsScraper
        return NewsScraper
    elif name == 'ScrapedContent':
        from .scraper import ScrapedContent
        return ScrapedContent
    elif name == 'HTTPFetcher':
        from .fetcher import HTTPFetcher
        return HTTPFetcher
    elif name == 'FetchResult':
        from .fetcher import FetchResult
        return FetchResult
    elif name == 'HTMLParser':
        from .parser import HTMLParser
        return HTMLParser
    elif name == 'ParsedContent':
        from .parser import ParsedContent
        return ParsedContent
    elif name == 'TextExtractor':
        from .extractor import TextExtractor
        return TextExtractor
    elif name == 'ExtractedContent':
        from .extractor import ExtractedContent
        return ExtractedContent
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")