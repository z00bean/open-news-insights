"""
HTML parser with site-specific selector support and fallback mechanisms.

This module provides HTML parsing capabilities using BeautifulSoup with
support for site-specific CSS selectors and generic fallback mechanisms
for content extraction from news websites.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
import re

from bs4 import BeautifulSoup, Tag, NavigableString
from bs4.element import Comment

from src.config.models import SiteConfig
from src.config.sites import get_site_config_by_domain


@dataclass
class ParsedContent:
    """Result of HTML parsing operation."""
    
    title: Optional[str] = None
    content: str = ""
    author: Optional[str] = None
    publish_date: Optional[datetime] = None
    word_count: int = 0
    paragraph_count: int = 0
    extraction_method: str = "unknown"
    confidence_score: float = 0.0
    raw_html: str = ""
    url: str = ""


class HTMLParser:
    """
    HTML parser with site-specific selector support.
    
    Provides content extraction using site-specific CSS selectors with
    automatic fallback to generic selectors when site-specific ones fail.
    """
    
    def __init__(self):
        """Initialize HTML parser."""
        self.soup: Optional[BeautifulSoup] = None
        self.site_config: Optional[SiteConfig] = None
    
    def parse(self, html: str, url: str) -> ParsedContent:
        """
        Parse HTML content and extract article information.
        
        Args:
            html: Raw HTML content
            url: Source URL for site-specific configuration
            
        Returns:
            ParsedContent with extracted information
        """
        if not html or not html.strip():
            return ParsedContent(
                url=url,
                raw_html=html,
                extraction_method="empty_input",
                confidence_score=0.0
            )
        
        # Parse HTML with BeautifulSoup
        self.soup = BeautifulSoup(html, 'html.parser')
        
        # Get site-specific configuration
        domain = self._extract_domain(url)
        self.site_config = get_site_config_by_domain(domain)
        
        # Extract content using site-specific selectors first
        result = self._extract_with_site_config(url, html)
        
        # If site-specific extraction failed, try fallback
        if result.confidence_score < 0.5:
            fallback_result = self._extract_with_fallback(url, html)
            if fallback_result.confidence_score > result.confidence_score:
                result = fallback_result
        
        return result
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def _extract_with_site_config(self, url: str, raw_html: str) -> ParsedContent:
        """
        Extract content using site-specific configuration.
        
        Args:
            url: Source URL
            raw_html: Raw HTML content
            
        Returns:
            ParsedContent with extracted information
        """
        if not self.soup or not self.site_config:
            return ParsedContent(
                url=url,
                raw_html=raw_html,
                extraction_method="no_config",
                confidence_score=0.0
            )
        
        # Extract title
        title = self._extract_title(self.site_config.title_selector)
        
        # Extract content
        content_paragraphs = self._extract_content(self.site_config.content_selector)
        content = "\n\n".join(content_paragraphs)
        
        # Extract author
        author = self._extract_author(self.site_config.author_selector)
        
        # Extract publish date
        publish_date = self._extract_date(self.site_config.date_selector)
        
        # Calculate metrics
        word_count = len(content.split()) if content else 0
        paragraph_count = len(content_paragraphs)
        
        # Calculate confidence score based on extraction success
        confidence_score = self._calculate_confidence(
            title, content, author, publish_date, word_count
        )
        
        return ParsedContent(
            title=title,
            content=content,
            author=author,
            publish_date=publish_date,
            word_count=word_count,
            paragraph_count=paragraph_count,
            extraction_method=f"site_specific_{self.site_config.domain}",
            confidence_score=confidence_score,
            raw_html=raw_html,
            url=url
        )
    
    def _extract_with_fallback(self, url: str, raw_html: str) -> ParsedContent:
        """
        Extract content using fallback selectors.
        
        Args:
            url: Source URL
            raw_html: Raw HTML content
            
        Returns:
            ParsedContent with extracted information
        """
        if not self.soup or not self.site_config:
            return ParsedContent(
                url=url,
                raw_html=raw_html,
                extraction_method="no_fallback",
                confidence_score=0.0
            )
        
        # Try fallback selectors for content
        content_paragraphs = []
        fallback_method = "generic_fallback"
        
        for selector in self.site_config.fallback_selectors:
            content_paragraphs = self._extract_content(selector)
            if content_paragraphs and len(content_paragraphs) > 2:
                fallback_method = f"fallback_{selector.replace(' ', '_')}"
                break
        
        # If fallback selectors failed, try generic extraction
        if not content_paragraphs:
            content_paragraphs = self._extract_generic_content()
            fallback_method = "generic_extraction"
        
        content = "\n\n".join(content_paragraphs)
        
        # Try generic title extraction
        title = self._extract_generic_title()
        
        # Try generic author extraction
        author = self._extract_generic_author()
        
        # Try generic date extraction
        publish_date = self._extract_generic_date()
        
        # Calculate metrics
        word_count = len(content.split()) if content else 0
        paragraph_count = len(content_paragraphs)
        
        # Calculate confidence score (lower for fallback)
        confidence_score = self._calculate_confidence(
            title, content, author, publish_date, word_count
        ) * 0.7  # Reduce confidence for fallback extraction
        
        return ParsedContent(
            title=title,
            content=content,
            author=author,
            publish_date=publish_date,
            word_count=word_count,
            paragraph_count=paragraph_count,
            extraction_method=fallback_method,
            confidence_score=confidence_score,
            raw_html=raw_html,
            url=url
        )
    
    def _extract_title(self, selector: str) -> Optional[str]:
        """Extract title using CSS selector."""
        if not self.soup or not selector:
            return None
        
        try:
            elements = self.soup.select(selector)
            for element in elements:
                text = self._clean_text(element.get_text())
                if text and len(text) > 10:  # Reasonable title length
                    return text
        except Exception:
            pass
        
        return None
    
    def _extract_content(self, selector: str) -> List[str]:
        """Extract content paragraphs using CSS selector."""
        if not self.soup or not selector:
            return []
        
        try:
            elements = self.soup.select(selector)
            paragraphs = []
            
            for element in elements:
                text = self._clean_text(element.get_text())
                if text and len(text.split()) > 5:  # Minimum words per paragraph
                    paragraphs.append(text)
            
            return paragraphs
        except Exception:
            return []
    
    def _extract_author(self, selector: Optional[str]) -> Optional[str]:
        """Extract author using CSS selector."""
        if not self.soup or not selector:
            return None
        
        try:
            elements = self.soup.select(selector)
            for element in elements:
                text = self._clean_text(element.get_text())
                if text and len(text) < 100:  # Reasonable author name length
                    return text
        except Exception:
            pass
        
        return None
    
    def _extract_date(self, selector: Optional[str]) -> Optional[datetime]:
        """Extract publish date using CSS selector."""
        if not self.soup or not selector:
            return None
        
        try:
            elements = self.soup.select(selector)
            for element in elements:
                # Try datetime attribute first
                datetime_attr = element.get('datetime')
                if datetime_attr:
                    return self._parse_datetime(datetime_attr)
                
                # Try text content
                text = self._clean_text(element.get_text())
                if text:
                    return self._parse_datetime(text)
        except Exception:
            pass
        
        return None
    
    def _extract_generic_title(self) -> Optional[str]:
        """Extract title using generic selectors."""
        generic_selectors = [
            "h1",
            ".title",
            ".headline",
            "[class*='title']",
            "[class*='headline']"
        ]
        
        for selector in generic_selectors:
            title = self._extract_title(selector)
            if title:
                return title
        
        return None
    
    def _extract_generic_content(self) -> List[str]:
        """Extract content using generic selectors."""
        generic_selectors = [
            "article p",
            ".content p",
            ".article-body p",
            ".story p",
            "main p",
            "p"
        ]
        
        for selector in generic_selectors:
            paragraphs = self._extract_content(selector)
            if paragraphs and len(paragraphs) > 2:
                return paragraphs
        
        return []
    
    def _extract_generic_author(self) -> Optional[str]:
        """Extract author using generic selectors."""
        generic_selectors = [
            ".author",
            ".byline",
            ".writer",
            "[class*='author']",
            "[class*='byline']"
        ]
        
        for selector in generic_selectors:
            author = self._extract_author(selector)
            if author:
                return author
        
        return None
    
    def _extract_generic_date(self) -> Optional[datetime]:
        """Extract date using generic selectors."""
        generic_selectors = [
            "time",
            ".date",
            ".published",
            "[class*='date']",
            "[class*='time']"
        ]
        
        for selector in generic_selectors:
            date = self._extract_date(selector)
            if date:
                return date
        
        return None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common unwanted patterns
        text = re.sub(r'^(Advertisement|Sponsored|Related:|Share:|Follow:)', '', text, flags=re.IGNORECASE)
        
        return text
    
    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse datetime string into datetime object."""
        if not date_str:
            return None
        
        # Common datetime formats
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%B %d, %Y",
            "%d %B %Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    def _calculate_confidence(
        self,
        title: Optional[str],
        content: str,
        author: Optional[str],
        publish_date: Optional[datetime],
        word_count: int
    ) -> float:
        """
        Calculate confidence score for extraction quality.
        
        Args:
            title: Extracted title
            content: Extracted content
            author: Extracted author
            publish_date: Extracted publish date
            word_count: Word count of content
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        
        # Title contributes 25%
        if title and len(title) > 10:
            score += 0.25
        
        # Content contributes 50%
        if content:
            if word_count > 100:
                score += 0.5
            elif word_count > 50:
                score += 0.3
            elif word_count > 20:
                score += 0.1
        
        # Author contributes 15%
        if author:
            score += 0.15
        
        # Date contributes 10%
        if publish_date:
            score += 0.1
        
        return min(score, 1.0)