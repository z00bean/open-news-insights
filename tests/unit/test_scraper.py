"""
Unit tests for main news scraper functionality.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from src.scraper.scraper import NewsScraper, ScrapedContent
from src.scraper.fetcher import FetchResult
from src.scraper.parser import ParsedContent
from src.scraper.extractor import ExtractedContent


class TestNewsScraper:
    """Test cases for NewsScraper class."""
    
    def test_init(self):
        """Test scraper initialization."""
        scraper = NewsScraper()
        assert scraper.fetcher is not None
        assert scraper.parser is not None
        assert scraper.extractor is not None
    
    def test_init_with_custom_params(self):
        """Test scraper initialization with custom parameters."""
        scraper = NewsScraper(
            timeout=60,
            max_retries=5,
            user_agent="Custom Agent"
        )
        assert scraper.fetcher.timeout == 60
        assert scraper.fetcher.max_retries == 5
        assert scraper.fetcher.user_agent == "Custom Agent"
    
    def test_invalid_url_handling(self):
        """Test handling of invalid URLs."""
        scraper = NewsScraper()
        
        # Test empty URL
        result = scraper.scrape_article("")
        assert not result.success
        assert "Invalid URL format" in result.error_message
        
        # Test invalid URL
        result = scraper.scrape_article("not-a-url")
        assert not result.success
        assert "Invalid URL format" in result.error_message
    
    def test_url_validation(self):
        """Test URL validation logic."""
        scraper = NewsScraper()
        
        assert scraper._is_valid_url("https://example.com")
        assert scraper._is_valid_url("http://test.org/path")
        assert not scraper._is_valid_url("")
        assert not scraper._is_valid_url("not-a-url")
        assert not scraper._is_valid_url(None)
        assert not scraper._is_valid_url("ftp://example.com")
    
    def test_domain_extraction(self):
        """Test domain extraction from URLs."""
        scraper = NewsScraper()
        
        assert scraper._extract_domain("https://example.com/article") == "example.com"
        assert scraper._extract_domain("http://www.test.org/path") == "www.test.org"
        assert scraper._extract_domain("invalid-url") == ""
    
    @patch('src.scraper.scraper.HTTPFetcher.fetch')
    def test_fetch_failure_handling(self, mock_fetch):
        """Test handling of fetch failures."""
        # Mock failed fetch
        mock_fetch.return_value = FetchResult(
            url="https://example.com",
            content="",
            status_code=0,
            headers={},
            fetch_time_ms=1000,
            attempts=3,
            success=False,
            error_message="Connection failed"
        )
        
        scraper = NewsScraper()
        result = scraper.scrape_article("https://example.com")
        
        assert not result.success
        assert "Fetch failed" in result.error_message
        assert result.fetch_time_ms == 1000
        assert result.fetch_attempts == 3
    
    @patch('src.scraper.scraper.TextExtractor.extract_content')
    @patch('src.scraper.scraper.HTMLParser.parse')
    @patch('src.scraper.scraper.HTTPFetcher.fetch')
    def test_successful_scraping(self, mock_fetch, mock_parse, mock_extract):
        """Test successful article scraping."""
        # Mock successful fetch
        mock_fetch.return_value = FetchResult(
            url="https://example.com/article",
            content="<html><body><h1>Test</h1><p>Content</p></body></html>",
            status_code=200,
            headers={"Content-Type": "text/html"},
            fetch_time_ms=500,
            attempts=1,
            success=True
        )
        
        # Mock successful parsing
        mock_parse.return_value = ParsedContent(
            title="Test Article",
            content="Test content paragraph",
            author="Test Author",
            publish_date=datetime(2024, 1, 1),
            word_count=3,
            paragraph_count=1,
            extraction_method="site_specific",
            confidence_score=0.8,
            raw_html="<html>...</html>",
            url="https://example.com/article"
        )
        
        # Mock successful extraction
        mock_extract.return_value = ExtractedContent(
            clean_text="Clean test content paragraph",
            word_count=4,
            paragraph_count=1,
            extraction_method="site_specific",
            confidence_score=0.9,
            removed_elements=["nav", "footer"]
        )
        
        scraper = NewsScraper()
        result = scraper.scrape_article("https://example.com/article")
        
        assert result.success
        assert result.title == "Test Article"
        assert result.content == "Test content paragraph"
        assert result.clean_content == "Clean test content paragraph"
        assert result.author == "Test Author"
        assert result.publish_date == datetime(2024, 1, 1)
        assert result.word_count == 4  # From extractor
        assert result.confidence_score == 0.8  # From parser
        assert result.extraction_confidence == 0.9  # From extractor
        assert result.fetch_time_ms == 500
        assert result.fetch_attempts == 1
        assert len(result.removed_elements) == 2
    
    def test_site_config_retrieval(self):
        """Test site configuration retrieval."""
        scraper = NewsScraper()
        
        # Test Guardian config
        config = scraper.get_site_config("https://theguardian.com/article")
        assert config is not None
        assert config.domain == "theguardian.com"
        
        # Test unknown site (should get generic config)
        config = scraper.get_site_config("https://unknown-site.com/article")
        assert config is not None
        assert config.domain == "*"  # Generic fallback
        
        # Test invalid URL
        config = scraper.get_site_config("invalid-url")
        assert config is None
    
    def test_supported_site_check(self):
        """Test supported site checking."""
        scraper = NewsScraper()
        
        # Test supported sites
        assert scraper.is_supported_site("https://theguardian.com/article")
        assert scraper.is_supported_site("https://timesofindia.indiatimes.com/article")
        
        # Test unsupported site
        assert not scraper.is_supported_site("https://unknown-site.com/article")
        
        # Test invalid URL
        assert not scraper.is_supported_site("invalid-url")
    
    def test_context_manager(self):
        """Test scraper as context manager."""
        with NewsScraper() as scraper:
            assert scraper is not None
            assert scraper.fetcher is not None
        # Resources should be cleaned up after context exit
    
    @patch('src.scraper.scraper.TextExtractor.extract_content')
    @patch('src.scraper.scraper.HTMLParser.parse')
    @patch('src.scraper.scraper.HTTPFetcher.fetch')
    def test_extraction_error_handling(self, mock_fetch, mock_parse, mock_extract):
        """Test handling of text extraction errors."""
        # Mock successful fetch and parse
        mock_fetch.return_value = FetchResult(
            url="https://example.com/article",
            content="<html><body><p>Content</p></body></html>",
            status_code=200,
            headers={},
            success=True
        )
        
        mock_parse.return_value = ParsedContent(
            title="Test",
            content="Content",
            word_count=1,
            paragraph_count=1,
            extraction_method="generic",
            confidence_score=0.5
        )
        
        # Mock extraction failure
        mock_extract.side_effect = Exception("Extraction failed")
        
        scraper = NewsScraper()
        result = scraper.scrape_article("https://example.com/article")
        
        # Should still succeed with parsed content only
        assert result.success
        assert result.title == "Test"
        assert result.content == "Content"
        assert result.clean_content == ""  # No extracted content
        assert result.extraction_confidence == 0.0