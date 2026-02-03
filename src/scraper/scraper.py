"""
Main news scraper that combines HTTP fetching and HTML parsing.

This module provides the primary interface for scraping news articles,
combining the HTTP fetcher and HTML parser components to provide a
complete scraping solution with comprehensive error handling.
"""

import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from .fetcher import HTTPFetcher, FetchResult
from .parser import HTMLParser, ParsedContent
from .extractor import TextExtractor, ExtractedContent
from src.config.models import SiteConfig
from src.config.sites import get_site_config_by_domain


# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ScrapedContent:
    """Complete result of news scraping operation."""
    
    url: str
    title: Optional[str] = None
    content: str = ""
    clean_content: str = ""  # Added for extracted clean content
    author: Optional[str] = None
    publish_date: Optional[datetime] = None
    word_count: int = 0
    paragraph_count: int = 0
    raw_html: str = ""
    scrape_timestamp: datetime = None
    
    # Metadata
    extraction_method: str = "unknown"
    confidence_score: float = 0.0
    fetch_time_ms: int = 0
    fetch_attempts: int = 1
    success: bool = True
    error_message: Optional[str] = None
    
    # Text extraction metadata
    removed_elements: Optional[list] = None
    extraction_confidence: float = 0.0
    
    def __post_init__(self):
        """Set scrape timestamp if not provided."""
        if self.scrape_timestamp is None:
            self.scrape_timestamp = datetime.now()
        if self.removed_elements is None:
            self.removed_elements = []


class NewsScraper:
    """
    Main news scraper combining HTTP fetching and HTML parsing.
    
    Provides a high-level interface for scraping news articles from
    supported websites with automatic fallback mechanisms.
    """
    
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: Optional[str] = None
    ):
        """
        Initialize news scraper.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            user_agent: Custom user agent string
        """
        self.fetcher = HTTPFetcher(
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent
        )
        self.parser = HTMLParser()
        self.extractor = TextExtractor()
    
    def scrape_article(self, url: str) -> ScrapedContent:
        """
        Scrape a news article from the given URL.
        
        Args:
            url: URL of the news article to scrape
            
        Returns:
            ScrapedContent with extracted article information
        """
        # Validate URL
        if not self._is_valid_url(url):
            return ScrapedContent(
                url=url,
                success=False,
                error_message="Invalid URL format"
            )
        
        # Fetch HTML content
        fetch_result = self.fetcher.fetch(url)
        
        if not fetch_result.success:
            return ScrapedContent(
                url=url,
                fetch_time_ms=fetch_result.fetch_time_ms,
                fetch_attempts=fetch_result.attempts,
                success=False,
                error_message=f"Fetch failed: {fetch_result.error_message}"
            )
        
        # Parse HTML content
        parsed_content = self.parser.parse(fetch_result.content, fetch_result.url)
        
        # Extract clean content using text extractor
        site_config = self.get_site_config(fetch_result.url)
        site_selectors = None
        if site_config:
            site_selectors = {
                'content_selector': site_config.content_selector,
                'title_selector': site_config.title_selector
            }
        
        try:
            extracted_content = self.extractor.extract_content(
                fetch_result.content, 
                site_selectors
            )
        except Exception as e:
            # If text extraction fails completely, continue with parsed content only
            extracted_content = None
            logger.warning(f"Text extraction failed: {e}")
        
        # Combine results, preferring extracted content for clean text
        clean_content = ""
        extraction_confidence = 0.0
        removed_elements = []
        
        if extracted_content:
            clean_content = extracted_content.clean_text
            extraction_confidence = extracted_content.confidence_score
            removed_elements = extracted_content.removed_elements
            
            # Check for extraction errors
            if extracted_content.error_details:
                error_type = extracted_content.error_details.get('error_type', 'UNKNOWN')
                if error_type in ['EXTRACTION_FAILED', 'UNEXPECTED_ERROR']:
                    # Log the error but continue with partial results
                    logger.error(f"Text extraction error: {extracted_content.error_details}")
        
        return ScrapedContent(
            url=fetch_result.url,  # Use final URL after redirects
            title=parsed_content.title,
            content=parsed_content.content,  # Original parsed content
            clean_content=clean_content,  # Clean extracted content
            author=parsed_content.author,
            publish_date=parsed_content.publish_date,
            word_count=extracted_content.word_count if extracted_content else parsed_content.word_count,
            paragraph_count=extracted_content.paragraph_count if extracted_content else parsed_content.paragraph_count,
            raw_html=parsed_content.raw_html,
            extraction_method=parsed_content.extraction_method,
            confidence_score=parsed_content.confidence_score,
            fetch_time_ms=fetch_result.fetch_time_ms,
            fetch_attempts=fetch_result.attempts,
            success=True,
            removed_elements=removed_elements,
            extraction_confidence=extraction_confidence
        )
    
    def get_site_config(self, url: str) -> Optional[SiteConfig]:
        """
        Get site configuration for a URL.
        
        Args:
            url: URL to get configuration for
            
        Returns:
            SiteConfig for the URL's domain, or None if invalid URL
        """
        domain = self._extract_domain(url)
        if not domain:
            return None
        
        return get_site_config_by_domain(domain)
    
    def is_supported_site(self, url: str) -> bool:
        """
        Check if a URL is from a supported news site.
        
        Args:
            url: URL to check
            
        Returns:
            True if site is explicitly supported, False otherwise
        """
        domain = self._extract_domain(url)
        if not domain:
            return False
        
        config = get_site_config_by_domain(domain)
        return config.domain != "*"  # Not using generic fallback
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        if not url or not isinstance(url, str):
            return False
        
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except Exception:
            return False
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def close(self) -> None:
        """Close the scraper and release resources."""
        if self.fetcher:
            self.fetcher.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()