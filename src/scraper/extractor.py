"""
Text extractor with boilerplate removal for news articles.

This module provides advanced text extraction capabilities that remove
navigation elements, advertisements, and non-article content while
preserving paragraph structure and basic formatting. Includes comprehensive
error handling for various HTML structures and encoding formats.
"""

import re
import logging
from typing import List, Optional, Set, Dict, Any, Union
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
from bs4.element import PageElement
from urllib.parse import urlparse


# Set up logging
logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Custom exception for text extraction errors."""
    
    def __init__(self, message: str, error_type: str = "EXTRACTION_ERROR", details: Optional[Dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


@dataclass
class ExtractedContent:
    """Result of text extraction operation."""
    
    clean_text: str
    word_count: int
    paragraph_count: int
    extraction_method: str
    confidence_score: float
    removed_elements: List[str] = None
    preserved_formatting: Dict[str, Any] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.removed_elements is None:
            self.removed_elements = []
        if self.preserved_formatting is None:
            self.preserved_formatting = {}
        if self.error_details is None:
            self.error_details = {}


class TextExtractor:
    """
    Advanced text extractor with boilerplate removal.
    
    Implements readability-style algorithms to remove navigation elements,
    advertisements, and non-content elements while preserving the main
    article content and paragraph structure.
    """
    
    # Elements that are typically boilerplate/non-content
    BOILERPLATE_TAGS = {
        'nav', 'header', 'footer', 'aside', 'menu', 'menuitem',
        'script', 'style', 'noscript', 'iframe', 'embed', 'object',
        'form', 'input', 'button', 'select', 'textarea', 'label'
    }
    
    # Class/ID patterns that indicate boilerplate content
    BOILERPLATE_PATTERNS = [
        r'nav', r'navigation', r'menu', r'sidebar', r'aside',
        r'header', r'footer', r'banner', r'toolbar',
        r'ad', r'advertisement', r'promo', r'sponsored',
        r'social', r'share', r'sharing', r'follow',
        r'comment', r'discussion', r'feedback',
        r'related', r'recommend', r'suggestion',
        r'widget', r'plugin', r'embed',
        r'breadcrumb', r'pagination', r'pager',
        r'search', r'filter', r'sort',
        r'cookie', r'gdpr', r'privacy',
        r'newsletter', r'subscribe', r'signup'
    ]
    
    # Patterns for content that should be preserved
    CONTENT_PATTERNS = [
        r'article', r'content', r'main', r'story', r'post',
        r'body', r'text', r'paragraph', r'section'
    ]
    
    def __init__(self):
        """Initialize text extractor."""
        self.removed_elements = []
        self.content_indicators = []
    
    def extract_content(self, html: str, site_selectors: Optional[Dict[str, str]] = None) -> ExtractedContent:
        """
        Extract clean article content from HTML with comprehensive error handling.
        
        Args:
            html: Raw HTML content
            site_selectors: Optional site-specific selectors for content extraction
            
        Returns:
            ExtractedContent with cleaned text and metadata
            
        Raises:
            ExtractionError: For critical extraction failures
        """
        # Input validation
        if html is None:
            return self._create_error_result(
                "HTML input is None",
                "NULL_INPUT",
                {"input_type": type(html).__name__}
            )
        
        if not isinstance(html, str):
            return self._create_error_result(
                f"HTML input must be string, got {type(html).__name__}",
                "INVALID_INPUT_TYPE",
                {"input_type": type(html).__name__, "input_value": str(html)[:100]}
            )
        
        if not html.strip():
            return ExtractedContent(
                clean_text="",
                word_count=0,
                paragraph_count=0,
                extraction_method="empty_input",
                confidence_score=0.0,
                error_details={"warning": "Empty HTML input"}
            )
        
        try:
            # Detect and handle encoding issues
            html = self._handle_encoding_issues(html)
            
            # Parse HTML with error handling
            soup = self._safe_parse_html(html)
            if soup is None:
                return self._create_error_result(
                    "Failed to parse HTML content",
                    "HTML_PARSE_ERROR",
                    {"html_length": len(html), "html_preview": html[:200]}
                )
            
            # Remove comments and unwanted elements
            try:
                self._remove_comments_and_scripts(soup)
            except Exception as e:
                logger.warning(f"Error removing comments/scripts: {e}")
                # Continue processing even if this fails
            
            # Remove boilerplate elements
            try:
                self._remove_boilerplate_elements(soup)
            except Exception as e:
                logger.warning(f"Error removing boilerplate: {e}")
                # Continue processing even if this fails
            
            # Try site-specific extraction first
            if site_selectors:
                try:
                    content = self._extract_with_selectors(soup, site_selectors)
                    if content and self._is_good_content(content):
                        return self._create_result(content, "site_specific")
                except Exception as e:
                    logger.warning(f"Site-specific extraction failed: {e}")
                    # Fall through to other methods
            
            # Try readability-style extraction
            try:
                content = self._extract_with_readability(soup)
                if content and self._is_good_content(content):
                    return self._create_result(content, "readability")
            except Exception as e:
                logger.warning(f"Readability extraction failed: {e}")
                # Fall through to generic method
            
            # Fallback to generic extraction
            try:
                content = self._extract_generic_content(soup)
                result = self._create_result(content, "generic_fallback")
                
                # Add warning if content quality is poor
                if result.confidence_score < 0.3:
                    result.error_details["warning"] = "Low confidence extraction - content quality may be poor"
                
                return result
            except Exception as e:
                return self._create_error_result(
                    f"All extraction methods failed: {str(e)}",
                    "EXTRACTION_FAILED",
                    {"last_error": str(e), "html_length": len(html)}
                )
            
        except ExtractionError:
            # Re-raise custom extraction errors
            raise
        except UnicodeDecodeError as e:
            return self._create_error_result(
                f"Unicode decoding error: {str(e)}",
                "ENCODING_ERROR",
                {"encoding_error": str(e), "position": getattr(e, 'start', None)}
            )
        except MemoryError:
            return self._create_error_result(
                "Insufficient memory to process HTML content",
                "MEMORY_ERROR",
                {"html_size": len(html)}
            )
        except Exception as e:
            return self._create_error_result(
                f"Unexpected error during extraction: {str(e)}",
                "UNEXPECTED_ERROR",
                {"error_type": type(e).__name__, "error_message": str(e)}
            )
    
    def _handle_encoding_issues(self, html: str) -> str:
        """
        Handle various encoding issues in HTML content.
        
        Args:
            html: Raw HTML string
            
        Returns:
            HTML string with encoding issues resolved
        """
        try:
            # Try to detect and fix common encoding issues
            if isinstance(html, bytes):
                # Try common encodings
                for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        html = html.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # If all fail, use utf-8 with error handling
                    html = html.decode('utf-8', errors='replace')
            
            # Replace problematic characters
            html = html.replace('\x00', '')  # Remove null bytes
            html = re.sub(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', '', html)  # Remove control characters
            
            return html
            
        except Exception as e:
            logger.warning(f"Error handling encoding: {e}")
            # Return original if encoding handling fails
            return str(html) if html is not None else ""
    
    def _safe_parse_html(self, html: str) -> Optional[BeautifulSoup]:
        """
        Safely parse HTML with multiple parser fallbacks.
        
        Args:
            html: HTML string to parse
            
        Returns:
            BeautifulSoup object or None if parsing fails
        """
        # Try different parsers in order of preference
        parsers = ['html.parser', 'lxml', 'html5lib']
        
        for parser in parsers:
            try:
                soup = BeautifulSoup(html, parser)
                # Validate that parsing was successful
                if soup and (soup.find() or soup.get_text(strip=True)):
                    return soup
            except Exception as e:
                logger.debug(f"Parser {parser} failed: {e}")
                continue
        
        # If all parsers fail, try with error recovery
        try:
            # Use html.parser with more lenient settings
            soup = BeautifulSoup(html, 'html.parser', from_encoding='utf-8')
            return soup
        except Exception as e:
            logger.error(f"All HTML parsers failed: {e}")
            return None
    
    def _create_error_result(self, message: str, error_type: str, details: Dict[str, Any]) -> ExtractedContent:
        """
        Create an ExtractedContent result for error cases.
        
        Args:
            message: Error message
            error_type: Type of error
            details: Additional error details
            
        Returns:
            ExtractedContent with error information
        """
        return ExtractedContent(
            clean_text="",
            word_count=0,
            paragraph_count=0,
            extraction_method="error",
            confidence_score=0.0,
            removed_elements=[f"Error: {message}"],
            error_details={
                "error_type": error_type,
                "error_message": message,
                "details": details
            }
        )
    
    def _remove_comments_and_scripts(self, soup: BeautifulSoup) -> None:
        """Remove HTML comments, scripts, and style elements with error handling."""
        try:
            # Remove comments
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                try:
                    comment.extract()
                    self.removed_elements.append("comment")
                except Exception as e:
                    logger.debug(f"Error removing comment: {e}")
        except Exception as e:
            logger.warning(f"Error finding comments: {e}")
        
        try:
            # Remove script and style tags
            for tag_name in ['script', 'style', 'noscript']:
                tags = soup.find_all(tag_name)
                for tag in tags:
                    try:
                        tag.extract()
                        self.removed_elements.append(f"script_style:{tag_name}")
                    except Exception as e:
                        logger.debug(f"Error removing {tag_name} tag: {e}")
        except Exception as e:
            logger.warning(f"Error removing script/style tags: {e}")
    
    def _remove_boilerplate_elements(self, soup: BeautifulSoup) -> None:
        """Remove elements that are likely boilerplate with error handling."""
        try:
            # Remove by tag name
            for tag_name in self.BOILERPLATE_TAGS:
                try:
                    tags = soup.find_all(tag_name)
                    for tag in tags:
                        try:
                            tag.extract()
                            self.removed_elements.append(f"tag:{tag_name}")
                        except Exception as e:
                            logger.debug(f"Error removing {tag_name} tag: {e}")
                except Exception as e:
                    logger.debug(f"Error finding {tag_name} tags: {e}")
        except Exception as e:
            logger.warning(f"Error removing boilerplate tags: {e}")
        
        try:
            # Remove by class/id patterns
            elements = soup.find_all()
            for element in elements:
                try:
                    if self._is_boilerplate_element(element):
                        element.extract()
                        self.removed_elements.append(f"pattern:{element.name}")
                except Exception as e:
                    logger.debug(f"Error checking/removing element: {e}")
        except Exception as e:
            logger.warning(f"Error removing boilerplate patterns: {e}")
        
        # Remove by class/id patterns
        for element in soup.find_all():
            if self._is_boilerplate_element(element):
                element.extract()
                self.removed_elements.append(f"pattern:{element.name}")
    
    def _is_boilerplate_element(self, element: Tag) -> bool:
        """Check if an element is likely boilerplate based on attributes with error handling."""
        if not isinstance(element, Tag):
            return False
        
        try:
            # Check class and id attributes
            classes = element.get('class', [])
            element_id = element.get('id', '')
            
            # Combine all text to check
            text_to_check = ' '.join(classes) + ' ' + element_id
            text_to_check = text_to_check.lower()
            
            # Check against boilerplate patterns
            for pattern in self.BOILERPLATE_PATTERNS:
                try:
                    if re.search(pattern, text_to_check):
                        return True
                except re.error as e:
                    logger.debug(f"Regex error with pattern {pattern}: {e}")
                    continue
            
            # Check for specific attributes that indicate ads/widgets
            if element.get('data-ad') or element.get('data-widget'):
                return True
            
            # Check for hidden elements
            style = element.get('style', '')
            if style:
                style_clean = style.replace(' ', '').lower()
                if 'display:none' in style_clean or 'visibility:hidden' in style_clean:
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking boilerplate element: {e}")
            return False  # Default to keeping element if check fails
    
    def _extract_with_selectors(self, soup: BeautifulSoup, selectors: Dict[str, str]) -> str:
        """Extract content using site-specific selectors with error handling."""
        content_parts = []
        
        try:
            # Try content selector
            content_selector = selectors.get('content_selector')
            if content_selector:
                try:
                    elements = soup.select(content_selector)
                    for element in elements:
                        try:
                            text = self._extract_text_from_element(element)
                            if text:
                                content_parts.append(text)
                        except Exception as e:
                            logger.debug(f"Error extracting text from element: {e}")
                except Exception as e:
                    logger.warning(f"Error with content selector '{content_selector}': {e}")
            
            return '\n\n'.join(content_parts)
            
        except Exception as e:
            logger.error(f"Error in selector-based extraction: {e}")
            return ""
    
    def _extract_with_readability(self, soup: BeautifulSoup) -> str:
        """Extract content using readability-style algorithm with error handling."""
        try:
            # Find the best content container
            best_element = self._find_best_content_element(soup)
            
            if best_element:
                return self._extract_text_from_element(best_element)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error in readability extraction: {e}")
            return ""
    
    def _find_best_content_element(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the element most likely to contain the main content."""
        candidates = []
        
        # Look for semantic content elements
        for tag_name in ['article', 'main', 'section', 'div']:
            elements = soup.find_all(tag_name)
            for element in elements:
                score = self._score_content_element(element)
                if score > 0:
                    candidates.append((element, score))
        
        # Sort by score and return the best
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        
        return None
    
    def _score_content_element(self, element: Tag) -> float:
        """Score an element based on likelihood of containing main content."""
        if not isinstance(element, Tag):
            return 0.0
        
        score = 0.0
        
        # Check class and id for content indicators
        classes = element.get('class', [])
        element_id = element.get('id', '')
        text_to_check = ' '.join(classes) + ' ' + element_id
        text_to_check = text_to_check.lower()
        
        # Positive indicators
        for pattern in self.CONTENT_PATTERNS:
            if re.search(pattern, text_to_check):
                score += 10.0
        
        # Negative indicators
        for pattern in self.BOILERPLATE_PATTERNS:
            if re.search(pattern, text_to_check):
                score -= 5.0
        
        # Text content analysis
        text_content = element.get_text(strip=True)
        if text_content:
            word_count = len(text_content.split())
            
            # Prefer elements with substantial text
            if word_count > 100:
                score += 20.0
            elif word_count > 50:
                score += 10.0
            elif word_count > 20:
                score += 5.0
            
            # Check for paragraph structure
            paragraphs = element.find_all('p')
            if len(paragraphs) > 3:
                score += 15.0
            elif len(paragraphs) > 1:
                score += 5.0
        
        # Penalize elements with too many links (likely navigation)
        links = element.find_all('a')
        if len(links) > 10:
            score -= 10.0
        
        return max(score, 0.0)
    
    def _extract_generic_content(self, soup: BeautifulSoup) -> str:
        """Extract content using generic fallback method with error handling."""
        content_parts = []
        
        try:
            # Try to find paragraphs with substantial content
            try:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    try:
                        text = self._extract_text_from_element(p)
                        if text and len(text.split()) > 10:  # Minimum word threshold
                            content_parts.append(text)
                    except Exception as e:
                        logger.debug(f"Error extracting paragraph text: {e}")
            except Exception as e:
                logger.warning(f"Error finding paragraphs: {e}")
            
            # If no good paragraphs, try other text containers
            if not content_parts:
                for tag_name in ['div', 'section', 'article']:
                    try:
                        elements = soup.find_all(tag_name)
                        for element in elements:
                            try:
                                text = self._extract_text_from_element(element)
                                if text and len(text.split()) > 20:
                                    content_parts.append(text)
                                    break  # Take first good one
                            except Exception as e:
                                logger.debug(f"Error extracting {tag_name} text: {e}")
                        if content_parts:
                            break
                    except Exception as e:
                        logger.debug(f"Error finding {tag_name} elements: {e}")
            
            return '\n\n'.join(content_parts)
            
        except Exception as e:
            logger.error(f"Error in generic content extraction: {e}")
            return ""
    
    def _extract_text_from_element(self, element: Tag) -> str:
        """Extract and clean text from a BeautifulSoup element with error handling."""
        if not element:
            return ""
        
        try:
            # Get text while preserving some structure
            text_parts = []
            
            try:
                for child in element.descendants:
                    try:
                        if isinstance(child, NavigableString) and not isinstance(child, Comment):
                            text = str(child).strip()
                            if text:
                                text_parts.append(text)
                        elif isinstance(child, Tag) and child.name in ['br', 'p', 'div']:
                            # Add line breaks for block elements
                            if text_parts and not text_parts[-1].endswith('\n'):
                                text_parts.append('\n')
                    except Exception as e:
                        logger.debug(f"Error processing child element: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Error iterating element descendants: {e}")
                # Fallback to simple text extraction
                try:
                    return self._clean_text(element.get_text())
                except Exception as e2:
                    logger.error(f"Fallback text extraction failed: {e2}")
                    return ""
            
            # Join and clean the text
            raw_text = ' '.join(text_parts)
            return self._clean_text(raw_text)
            
        except Exception as e:
            logger.error(f"Error extracting text from element: {e}")
            return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text with error handling."""
        if not text:
            return ""
        
        try:
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Remove common unwanted patterns
            patterns_to_remove = [
                r'^(Advertisement|Sponsored|Related:|Share:|Follow:|Subscribe:)',
                r'(Click here|Read more|Continue reading).*$',
                r'^\s*(By|Author:|Written by)\s+',
                r'\s*(Share on|Follow us|Subscribe to).*$'
            ]
            
            for pattern in patterns_to_remove:
                try:
                    text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
                except re.error as e:
                    logger.debug(f"Regex error with pattern {pattern}: {e}")
                    continue
            
            # Clean up paragraph breaks
            try:
                text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
            except re.error as e:
                logger.debug(f"Error cleaning paragraph breaks: {e}")
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning text: {e}")
            # Return original text if cleaning fails
            return str(text) if text else ""
    
    def _is_good_content(self, content: str) -> bool:
        """Check if extracted content meets quality thresholds."""
        if not content:
            return False
        
        words = content.split()
        
        # Minimum word count
        if len(words) < 50:
            return False
        
        # Check for reasonable sentence structure
        sentences = re.split(r'[.!?]+', content)
        if len(sentences) < 3:
            return False
        
        # Check average word length (avoid gibberish)
        avg_word_length = sum(len(word) for word in words) / len(words)
        if avg_word_length < 3 or avg_word_length > 15:
            return False
        
        return True
    
    def _create_result(self, content: str, method: str) -> ExtractedContent:
        """Create ExtractedContent result from cleaned text."""
        if not content:
            return ExtractedContent(
                clean_text="",
                word_count=0,
                paragraph_count=0,
                extraction_method=method,
                confidence_score=0.0,
                removed_elements=self.removed_elements.copy()
            )
        
        # Calculate metrics
        words = content.split()
        word_count = len(words)
        
        # Count paragraphs (double newlines indicate paragraph breaks)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        paragraph_count = len(paragraphs)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(content, method)
        
        # Preserve formatting information
        formatting_info = {
            'has_paragraphs': paragraph_count > 1,
            'avg_paragraph_length': word_count / max(paragraph_count, 1),
            'has_proper_sentences': '.' in content or '!' in content or '?' in content
        }
        
        return ExtractedContent(
            clean_text=content,
            word_count=word_count,
            paragraph_count=paragraph_count,
            extraction_method=method,
            confidence_score=confidence_score,
            removed_elements=self.removed_elements.copy(),
            preserved_formatting=formatting_info
        )
    
    def _calculate_confidence_score(self, content: str, method: str) -> float:
        """Calculate confidence score for extracted content."""
        if not content:
            return 0.0
        
        score = 0.0
        words = content.split()
        word_count = len(words)
        
        # Base score based on extraction method
        method_scores = {
            'site_specific': 0.8,
            'readability': 0.6,
            'generic_fallback': 0.4,
            'error': 0.0
        }
        score = method_scores.get(method, 0.3)
        
        # Adjust based on content quality
        if word_count > 200:
            score += 0.2
        elif word_count > 100:
            score += 0.1
        elif word_count < 50:
            score -= 0.2
        
        # Check for proper sentence structure
        sentences = re.split(r'[.!?]+', content)
        if len(sentences) > 5:
            score += 0.1
        
        # Check for paragraph structure
        paragraphs = content.split('\n\n')
        if len(paragraphs) > 2:
            score += 0.1
        
        return min(max(score, 0.0), 1.0)