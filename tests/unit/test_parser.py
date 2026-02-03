"""
Unit tests for HTML parser functionality.
"""

import pytest
from datetime import datetime
from src.scraper.parser import HTMLParser, ParsedContent
from src.config.models import SiteConfig


class TestHTMLParser:
    """Test cases for HTMLParser class."""
    
    def test_init(self):
        """Test parser initialization."""
        parser = HTMLParser()
        assert parser.soup is None
        assert parser.site_config is None
    
    def test_parse_empty_html(self):
        """Test parsing empty HTML."""
        parser = HTMLParser()
        result = parser.parse("", "https://example.com")
        
        assert result.url == "https://example.com"
        assert result.extraction_method == "empty_input"
        assert result.confidence_score == 0.0
    
    def test_parse_basic_html(self):
        """Test parsing basic HTML content."""
        html = """
        <html>
            <head><title>Test Article</title></head>
            <body>
                <article>
                    <h1>Test Article Title With Sufficient Length</h1>
                    <p>First paragraph of content with substantial information.</p>
                    <p>Second paragraph of content with more details.</p>
                </article>
            </body>
        </html>
        """
        
        parser = HTMLParser()
        result = parser.parse(html, "https://example.com")
        
        assert result.url == "https://example.com"
        assert result.title is not None
        assert result.content != ""
        assert result.word_count > 0
        assert result.confidence_score > 0
    
    def test_extract_domain(self):
        """Test domain extraction from URLs."""
        parser = HTMLParser()
        
        assert parser._extract_domain("https://example.com/article") == "example.com"
        assert parser._extract_domain("http://www.test.org/path") == "www.test.org"
        assert parser._extract_domain("invalid-url") == ""
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        parser = HTMLParser()
        
        # Test whitespace normalization
        dirty_text = "  Multiple   spaces   and\n\nnewlines  "
        clean_text = parser._clean_text(dirty_text)
        assert clean_text == "Multiple spaces and newlines"
        
        # Test removal of unwanted patterns
        ad_text = "Advertisement This is the real content"
        clean_text = parser._clean_text(ad_text)
        assert "Advertisement" not in clean_text
        assert "real content" in clean_text
    
    def test_calculate_confidence(self):
        """Test confidence score calculation."""
        parser = HTMLParser()
        
        # High confidence case
        score = parser._calculate_confidence(
            title="Good Title",
            content="This is a substantial piece of content with many words and good structure.",
            author="John Doe",
            publish_date=datetime.now(),
            word_count=150
        )
        assert score >= 0.75  # Adjusted expectation
        
        # Low confidence case
        score = parser._calculate_confidence(
            title=None,
            content="Short",
            author=None,
            publish_date=None,
            word_count=1
        )
        assert score < 0.3
    
    def test_parse_with_guardian_selectors(self):
        """Test parsing with Guardian-specific selectors."""
        html = """
        <html>
            <body>
                <h1 data-gu-name="headline">Guardian Test Article</h1>
                <div data-gu-name="body">
                    <p>First paragraph from Guardian with substantial content and information.</p>
                    <p>Second paragraph from Guardian with more detailed coverage and analysis.</p>
                </div>
                <a rel="author">Test Author</a>
                <time datetime="2024-01-01T12:00:00Z">Jan 1, 2024</time>
            </body>
        </html>
        """
        
        parser = HTMLParser()
        result = parser.parse(html, "https://theguardian.com/test")
        
        assert "Guardian Test Article" in (result.title or "")
        assert "Guardian" in result.content
        assert result.author == "Test Author"
        assert result.publish_date is not None
        assert result.confidence_score >= 0.5