"""
Unit tests for result formatter functionality.

Tests the core formatting and external API integration capabilities
of the ResultFormatter class.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.postprocess.formatter import (
    ResultFormatter,
    FormattedResponse,
    ArticleMetadata,
    ProcessingMetadata,
    FormattingError,
    ExternalAPIError
)
from src.config.models import ExternalAPIConfig
from src.scraper.extractor import ExtractedContent
from src.analysis.enricher import EnrichmentResults, SentimentResult


class TestResultFormatter:
    """Test cases for ResultFormatter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.api_config = ExternalAPIConfig(
            endpoint_url="https://api.example.com/webhook",
            auth_header="Bearer test-token",
            timeout_seconds=10,
            max_retries=2,
            retry_delay_seconds=0.1
        )
        self.formatter = ResultFormatter(self.api_config)
    
    def test_format_response_basic(self):
        """Test basic response formatting."""
        # Create test data
        extracted_content = ExtractedContent(
            clean_text="This is a test article content.",
            word_count=6,
            paragraph_count=1,
            extraction_method="test",
            confidence_score=0.8
        )
        
        # Format response
        response = self.formatter.format_response(
            url="https://example.com/article",
            extracted_content=extracted_content,
            title="Test Article",
            author="Test Author",
            processing_time_ms=1000
        )
        
        # Verify response structure
        assert isinstance(response, FormattedResponse)
        assert response.success is True
        assert response.article_metadata.url == "https://example.com/article"
        assert response.article_metadata.title == "Test Article"
        assert response.article_metadata.author == "Test Author"
        assert response.extracted_content == "This is a test article content."
        assert response.processing_metadata.processing_time_ms == 1000
        assert response.processing_metadata.extraction_method == "test"
        assert response.processing_metadata.extraction_confidence == 0.8
    
    def test_format_response_with_enrichment(self):
        """Test response formatting with enrichment results."""
        # Create test data
        extracted_content = ExtractedContent(
            clean_text="This is a positive article.",
            word_count=5,
            paragraph_count=1,
            extraction_method="test",
            confidence_score=0.9
        )
        
        # Create enrichment results
        sentiment_result = SentimentResult(
            sentiment="POSITIVE",
            confidence_scores={"POSITIVE": 0.9, "NEGATIVE": 0.1, "NEUTRAL": 0.0, "MIXED": 0.0}
        )
        
        enrichment_results = EnrichmentResults(
            sentiment=sentiment_result,
            processing_time_ms=500,
            features_processed=["sentiment"]
        )
        
        # Format response
        response = self.formatter.format_response(
            url="https://example.com/article",
            extracted_content=extracted_content,
            enrichment_results=enrichment_results,
            features_enabled={"sentiment": True, "pii": False}
        )
        
        # Verify enrichment data is included
        assert response.sentiment_analysis is not None
        assert response.sentiment_analysis["sentiment"] == "POSITIVE"
        assert response.sentiment_analysis["dominant_confidence"] == 0.9
        assert response.processing_metadata.aws_service_calls["comprehend"] == 1
        assert response.processing_metadata.features_enabled["sentiment"] is True
    
    def test_format_error_response(self):
        """Test error response formatting."""
        error_response = self.formatter.format_error_response(
            url="https://example.com/article",
            error_message="Test error occurred",
            error_type="TEST_ERROR",
            processing_step="extraction",
            partial_results={"extracted_text": "partial content"}
        )
        
        # Verify error response structure
        assert error_response["success"] is False
        assert error_response["error"]["type"] == "TEST_ERROR"
        assert error_response["error"]["message"] == "Test error occurred"
        assert error_response["error"]["step"] == "extraction"
        assert error_response["article_metadata"]["url"] == "https://example.com/article"
        assert error_response["partial_results"]["extracted_text"] == "partial content"
    
    @patch('requests.Session.post')
    def test_post_to_external_api_success(self, mock_post):
        """Test successful external API posting."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Success"
        mock_post.return_value = mock_response
        
        # Create test data
        test_data = {"test": "data", "success": True}
        
        # Post to API
        result = self.formatter.post_to_external_api(test_data)
        
        # Verify success
        assert result is True
        mock_post.assert_called_once()
        
        # Verify request details
        call_args = mock_post.call_args
        assert call_args[1]['json'] == test_data
        assert call_args[1]['headers']['Authorization'] == "Bearer test-token"
        # Timeout is now a tuple (connect_timeout, read_timeout)
        assert call_args[1]['timeout'] == (5, 15)  # External API timeout from timeout manager
    
    @patch('requests.Session.post')
    def test_post_to_external_api_retry_on_failure(self, mock_post):
        """Test retry logic on API failure."""
        # Mock failed responses followed by success
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Internal Server Error"
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.text = "Success"
        
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        # Create test data
        test_data = {"test": "data"}
        
        # Post to API
        result = self.formatter.post_to_external_api(test_data)
        
        # Verify success after retry
        assert result is True
        assert mock_post.call_count == 2
    
    @patch('requests.Session.post')
    def test_post_to_external_api_max_retries_exceeded(self, mock_post):
        """Test behavior when max retries are exceeded."""
        # Mock all requests to fail
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        # Create test data
        test_data = {"test": "data"}
        
        # Post to API should raise exception after retries
        with pytest.raises(ExternalAPIError) as exc_info:
            self.formatter.post_to_external_api(test_data)
        
        # Verify retry attempts (max_retries + 1 = 3 total attempts)
        assert mock_post.call_count == 3
        assert "status 500" in str(exc_info.value)
    
    def test_post_to_external_api_no_endpoint(self):
        """Test behavior when no external API endpoint is configured."""
        # Create formatter without endpoint
        formatter = ResultFormatter(ExternalAPIConfig())
        
        # Post should succeed without making any requests
        result = formatter.post_to_external_api({"test": "data"})
        assert result is True
    
    def test_format_response_handles_none_content(self):
        """Test formatting with None extracted content."""
        response = self.formatter.format_response(
            url="https://example.com/article",
            extracted_content=None,
            processing_time_ms=100
        )
        
        # Should handle gracefully
        assert response.success is True
        assert response.extracted_content == ""
        assert response.processing_metadata.extraction_method == "unknown"
        assert response.processing_metadata.extraction_confidence == 0.0
    
    def test_article_metadata_domain_extraction(self):
        """Test automatic domain extraction from URL."""
        metadata = ArticleMetadata(url="https://www.example.com/path/to/article")
        assert metadata.domain == "www.example.com"
        
        # Test with invalid URL
        metadata_invalid = ArticleMetadata(url="not-a-url")
        assert metadata_invalid.domain is None
    
    def test_retry_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        # Test delay calculation
        delay_0 = self.formatter._calculate_retry_delay(0)
        delay_1 = self.formatter._calculate_retry_delay(1)
        delay_2 = self.formatter._calculate_retry_delay(2)
        
        # Should increase exponentially
        assert delay_0 == 0.1  # base delay
        assert delay_1 == 0.2  # base * 2^1
        assert delay_2 == 0.4  # base * 2^2
        
        # Test cap at 30 seconds
        delay_large = self.formatter._calculate_retry_delay(10)
        assert delay_large == 30.0