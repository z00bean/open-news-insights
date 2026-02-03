"""
News scraper module for Open News Insights.

This module provides comprehensive news scraping capabilities including
HTTP fetching with retry logic, HTML parsing with site-specific selectors,
and fallback mechanisms for content extraction.
"""

from .scraper import NewsScraper, ScrapedContent
from .fetcher import HTTPFetcher, FetchResult
from .parser import HTMLParser, ParsedContent

__all__ = [
    'NewsScraper',
    'ScrapedContent',
    'HTTPFetcher', 
    'FetchResult',
    'HTMLParser',
    'ParsedContent'
]