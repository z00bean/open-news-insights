"""
Unit tests for HTTP fetcher functionality.
"""

import pytest
from unittest.mock import Mock, patch
import requests
from src.scraper.fetcher import HTTPFetcher, FetchResult


class TestHTTPFetcher:
    """Test cases for HTTPFetcher class."""
    
    def test_init_with_defaults(self):
        """Test fetcher initialization with default values."""
        fetcher = HTTPFetcher()
        assert fetcher.timeout == 30
        assert fetcher.max_retries == 3
        assert fetcher.backoff_factor == 1.0
        assert "Mozilla" in fetcher.user_agent
    
    def test_init_with_custom_values(self):
        """Test fetcher initialization with custom values."""
        fetcher = HTTPFetcher(
            timeout=60,
            max_retries=5,
            backoff_factor=2.0,
            user_agent="Custom Agent"
        )
        assert fetcher.timeout == 60
        assert fetcher.max_retries == 5
        assert fetcher.backoff_factor == 2.0
        assert fetcher.user_agent == "Custom Agent"
    
    def test_invalid_url_handling(self):
        """Test handling of invalid URLs."""
        fetcher = HTTPFetcher()
        
        # Test empty URL
        result = fetcher.fetch("")
        assert not result.success
        assert "Invalid URL format" in result.error_message
        
        # Test invalid URL format
        result = fetcher.fetch("not-a-url")
        assert not result.success
        assert "Invalid URL format" in result.error_message
    
    @patch('src.scraper.fetcher.requests.Session.get')
    def test_successful_fetch(self, mock_get):
        """Test successful HTTP fetch."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.url = "https://example.com"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.encoding = "utf-8"
        mock_get.return_value = mock_response
        
        fetcher = HTTPFetcher()
        result = fetcher.fetch("https://example.com")
        
        assert result.success
        assert result.status_code == 200
        assert result.content == "<html><body>Test content</body></html>"
        assert result.url == "https://example.com"
        assert result.attempts == 1
    
    @patch('src.scraper.fetcher.requests.Session.get')
    def test_http_error_handling(self, mock_get):
        """Test handling of HTTP errors."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_get.return_value = mock_response
        
        fetcher = HTTPFetcher()
        result = fetcher.fetch("https://example.com/nonexistent")
        
        assert not result.success
        assert result.status_code == 0  # Error case
        assert "404" in result.error_message
    
    @patch('src.scraper.fetcher.requests.Session.get')
    def test_timeout_handling(self, mock_get):
        """Test handling of request timeouts."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        fetcher = HTTPFetcher(max_retries=1)  # Reduce retries for faster test
        result = fetcher.fetch("https://example.com")
        
        assert not result.success
        assert "timeout" in result.error_message.lower()
        assert result.attempts > 1  # Should have retried
    
    def test_context_manager(self):
        """Test fetcher as context manager."""
        with HTTPFetcher() as fetcher:
            assert fetcher is not None
            assert hasattr(fetcher, 'session')
        # Session should be closed after context exit