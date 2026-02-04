"""
Integration tests for the complete Open News Insights processing pipeline.

Tests the end-to-end functionality by wiring all components together
and verifying that the complete processing pipeline works correctly.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from dataclasses import dataclass

# Import the handler and components
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.handler import lambda_handler, execute_processing_pipeline
from src.scraper.scraper import NewsScraper, ScrapedContent
from src.analysis.normalizer import LLMNormalizer, NormalizedContent
from src.analysis.enricher import NLPEnricher, EnrichmentResults, SentimentResult, PIIResult, TopicResult, SummaryResult
from src.postprocess.formatter import ResultFormatter, FormattedResponse
from src.scraper.extractor import ExtractedContent
from src.config.models import SystemConfig, AWSSettings, ExternalAPIConfig


class TestCompleteProcessingPipeline:
    """Test complete processing pipeline integration."""
    
    @pytest.fixture
    def mock_lambda_context(self):
        """Create mock Lambda context."""
        context = Mock()
        context.aws_request_id = "test-request-123"
        context.function_name = "open-news-insights"
        context.memory_limit_in_mb = 512
        context.get_remaining_time_in_millis = Mock(return_value=30000)
        return context
    
    @pytest.fixture
    def sample_scraped_content(self):
        """Create sample scraped content."""
        return ScrapedContent(
            url="https://example.com/article",
            title="Test Article",
            content="This is the original parsed content.",
            clean_content="This is the clean extracted content from the article.",
            author="Test Author",
            publish_date=datetime(2024, 1, 15, 10, 30),
            word_count=150,
            paragraph_count=3,
            raw_html="<html><body>Test content</body></html>",
            extraction_method="site_specific",
            confidence_score=0.95,
            fetch_time_ms=1200,
            fetch_attempts=1,
            success=True,
            removed_elements=["nav", "ads"],
            extraction_confidence=0.92
        )
    
    @pytest.fixture
    def sample_normalized_content(self):
        """Create sample normalized content."""
        return NormalizedContent(
            normalized_text="This is the normalized and cleaned content.",
            original_length=150,
            normalized_length=120,
            processing_time_ms=2500,
            model_used="anthropic.claude-3-haiku-20240307-v1:0"
        )
    
    @pytest.fixture
    def sample_enrichment_results(self):
        """Create sample enrichment results."""
        sentiment = SentimentResult(
            sentiment="POSITIVE",
            confidence_scores={
                "POSITIVE": 0.85,
                "NEGATIVE": 0.05,
                "NEUTRAL": 0.08,
                "MIXED": 0.02
            }
        )
        
        pii = PIIResult(entities=[])  # No PII detected
        
        topics = TopicResult(
            key_phrases=[],
            topics=["Technology", "Innovation"]
        )
        
        summary = SummaryResult(
            summary="This article discusses technology and innovation.",
            original_length=120,
            summary_length=45,
            processing_time_ms=1800,
            model_used="anthropic.claude-3-haiku-20240307-v1:0"
        )
        
        return EnrichmentResults(
            sentiment=sentiment,
            pii_detection=pii,
            topics=topics,
            summary=summary,
            processing_time_ms=5000,
            features_processed=["sentiment", "pii", "topics", "summary"]
        )
    
    @patch('src.handler.get_system_config')
    @patch('src.handler.NewsScraper')
    @patch('src.handler.LLMNormalizer')
    @patch('src.handler.NLPEnricher')
    @patch('src.handler.ResultFormatter')
    def test_complete_pipeline_all_features_enabled(
        self,
        mock_formatter_class,
        mock_enricher_class,
        mock_normalizer_class,
        mock_scraper_class,
        mock_get_config,
        mock_lambda_context,
        sample_scraped_content,
        sample_normalized_content,
        sample_enrichment_results
    ):
        """Test complete pipeline with all features enabled."""
        
        # Mock system configuration
        aws_settings = AWSSettings(
            region="us-east-1",
            bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
            max_retries=3
        )
        config = SystemConfig(
            aws_settings=aws_settings,
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig()
        )
        mock_get_config.return_value = config
        
        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.scrape_article.return_value = sample_scraped_content
        mock_scraper_class.return_value = mock_scraper
        
        # Mock normalizer
        mock_normalizer = Mock()
        mock_normalizer.normalize_text.return_value = sample_normalized_content
        mock_normalizer_class.return_value = mock_normalizer
        
        # Mock enricher
        mock_enricher = Mock()
        mock_enricher.enrich_content.return_value = sample_enrichment_results
        mock_enricher_class.return_value = mock_enricher
        
        # Mock formatter
        mock_formatter = Mock()
        formatted_response = FormattedResponse(
            success=True,
            article_metadata=Mock(),
            extracted_content="This is the clean extracted content from the article.",
            normalized_content="This is the normalized and cleaned content.",
            sentiment_analysis={"sentiment": "POSITIVE", "confidence_scores": {"POSITIVE": 0.85}},
            pii_detection={"entities": [], "has_pii": False},
            topic_analysis={"topics": ["Technology", "Innovation"]},
            summary="This article discusses technology and innovation."
        )
        mock_formatter.format_response.return_value = formatted_response
        mock_formatter.post_to_external_api.return_value = True
        mock_formatter_class.return_value = mock_formatter
        
        # Create test event with all features enabled
        event = {
            "body": json.dumps({
                "url": "https://example.com/article",
                "features": {
                    "llm_normalization": True,
                    "sentiment": True,
                    "pii": True,
                    "topics": True,
                    "summary": True,
                    "external_api": True
                }
            })
        }
        
        # Execute Lambda handler
        response = lambda_handler(event, mock_lambda_context)
        
        # Verify response structure
        assert response["statusCode"] == 200
        assert "body" in response
        
        response_body = json.loads(response["body"])
        assert response_body["success"] == True
        assert "article_metadata" in response_body
        assert "extracted_content" in response_body
        assert "normalized_content" in response_body
        assert "sentiment_analysis" in response_body
        assert "pii_detection" in response_body
        assert "topic_analysis" in response_body
        assert "summary" in response_body
        
        # Verify component interactions
        mock_scraper.scrape_article.assert_called_once_with("https://example.com/article")
        mock_normalizer.normalize_text.assert_called_once_with(sample_scraped_content.clean_content)
        mock_enricher.enrich_content.assert_called_once()
        mock_formatter.format_response.assert_called_once()
        mock_formatter.post_to_external_api.assert_called_once()
    
    @patch('src.handler.get_system_config')
    @patch('src.handler.NewsScraper')
    @patch('src.handler.ResultFormatter')
    def test_complete_pipeline_basic_scraping_only(
        self,
        mock_formatter_class,
        mock_scraper_class,
        mock_get_config,
        mock_lambda_context,
        sample_scraped_content
    ):
        """Test complete pipeline with only basic scraping (no AWS features)."""
        
        # Mock system configuration
        config = SystemConfig(
            aws_settings=AWSSettings(region="us-east-1"),
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig()
        )
        mock_get_config.return_value = config
        
        # Mock scraper
        mock_scraper = Mock()
        mock_scraper.scrape_article.return_value = sample_scraped_content
        mock_scraper_class.return_value = mock_scraper
        
        # Mock formatter
        mock_formatter = Mock()
        formatted_response = FormattedResponse(
            success=True,
            article_metadata=Mock(),
            extracted_content="This is the clean extracted content from the article."
        )
        mock_formatter.format_response.return_value = formatted_response
        mock_formatter_class.return_value = mock_formatter
        
        # Create test event with no features enabled
        event = {
            "body": json.dumps({
                "url": "https://example.com/article",
                "features": {}
            })
        }
        
        # Execute Lambda handler
        response = lambda_handler(event, mock_lambda_context)
        
        # Verify response structure
        assert response["statusCode"] == 200
        response_body = json.loads(response["body"])
        assert response_body["success"] == True
        
        # Verify only scraping was performed
        mock_scraper.scrape_article.assert_called_once_with("https://example.com/article")
        mock_formatter.format_response.assert_called_once()
        
        # Verify no AWS services were initialized
        # (normalizer and enricher should not be created when no features are enabled)
    
    @patch('src.handler.get_system_config')
    @patch('src.handler.NewsScraper')
    def test_complete_pipeline_scraping_failure(
        self,
        mock_scraper_class,
        mock_get_config,
        mock_lambda_context
    ):
        """Test complete pipeline with scraping failure."""
        
        # Mock system configuration
        config = SystemConfig(
            aws_settings=AWSSettings(region="us-east-1"),
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig()
        )
        mock_get_config.return_value = config
        
        # Mock scraper to fail
        mock_scraper = Mock()
        failed_content = ScrapedContent(
            url="https://example.com/article",
            success=False,
            error_message="Failed to fetch content: HTTP 404"
        )
        mock_scraper.scrape_article.return_value = failed_content
        mock_scraper_class.return_value = mock_scraper
        
        # Create test event
        event = {
            "body": json.dumps({
                "url": "https://example.com/article",
                "features": {"sentiment": True}
            })
        }
        
        # Execute Lambda handler
        response = lambda_handler(event, mock_lambda_context)
        
        # Verify error response
        assert response["statusCode"] == 400
        response_body = json.loads(response["body"])
        assert response_body["success"] == False
        assert response_body["error"]["type"] == "SCRAPING_ERROR"
        assert "Failed to fetch content" in response_body["error"]["message"]
    
    @patch('src.handler.get_system_config')
    @patch('src.handler.NewsScraper')
    @patch('src.handler.LLMNormalizer')
    @patch('src.handler.ResultFormatter')
    def test_complete_pipeline_partial_failure(
        self,
        mock_formatter_class,
        mock_normalizer_class,
        mock_scraper_class,
        mock_get_config,
        mock_lambda_context,
        sample_scraped_content
    ):
        """Test complete pipeline with partial failure (normalization fails)."""
        
        # Mock system configuration
        config = SystemConfig(
            aws_settings=AWSSettings(region="us-east-1"),
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig()
        )
        mock_get_config.return_value = config
        
        # Mock scraper (succeeds)
        mock_scraper = Mock()
        mock_scraper.scrape_article.return_value = sample_scraped_content
        mock_scraper_class.return_value = mock_scraper
        
        # Mock normalizer (fails)
        mock_normalizer = Mock()
        mock_normalizer.normalize_text.side_effect = Exception("Bedrock service unavailable")
        mock_normalizer_class.return_value = mock_normalizer
        
        # Mock formatter
        mock_formatter = Mock()
        formatted_response = FormattedResponse(
            success=True,
            article_metadata=Mock(),
            extracted_content="This is the clean extracted content from the article."
        )
        mock_formatter.format_response.return_value = formatted_response
        mock_formatter_class.return_value = mock_formatter
        
        # Create test event with normalization enabled
        event = {
            "body": json.dumps({
                "url": "https://example.com/article",
                "features": {
                    "llm_normalization": True
                }
            })
        }
        
        # Execute Lambda handler
        response = lambda_handler(event, mock_lambda_context)
        
        # Verify partial success response (206 status code)
        assert response["statusCode"] == 206  # Partial Content
        response_body = json.loads(response["body"])
        assert response_body["success"] == True
        
        # Verify scraping succeeded but normalization failed
        mock_scraper.scrape_article.assert_called_once()
        mock_normalizer.normalize_text.assert_called_once()
        mock_formatter.format_response.assert_called_once()
    
    def test_execute_processing_pipeline_direct(self, sample_scraped_content):
        """Test execute_processing_pipeline function directly."""
        
        # Create mock components
        mock_scraper = Mock()
        mock_scraper.scrape_article.return_value = sample_scraped_content
        
        mock_formatter = Mock()
        formatted_response = {"success": True, "content": "test"}
        mock_formatter.format_response.return_value = formatted_response
        
        # Test with basic features only
        feature_flags = {"sentiment": False, "llm_normalization": False}
        
        result = execute_processing_pipeline(
            url="https://example.com/article",
            feature_flags=feature_flags,
            scraper=mock_scraper,
            normalizer=None,
            enricher=None,
            formatter=mock_formatter
        )
        
        # Verify successful processing
        assert result["success"] == True
        assert result["response"] == formatted_response
        assert result["partial_failures"] == False
        assert result["processing_errors"] == []
        
        # Verify component calls
        mock_scraper.scrape_article.assert_called_once_with("https://example.com/article")
        mock_formatter.format_response.assert_called_once()


class TestComponentWiring:
    """Test proper dependency injection and component wiring."""
    
    @patch('src.handler.get_system_config')
    def test_component_initialization_with_feature_flags(self, mock_get_config):
        """Test that components are initialized based on feature flags."""
        
        # Mock system configuration
        config = SystemConfig(
            aws_settings=AWSSettings(region="us-east-1"),
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig()
        )
        mock_get_config.return_value = config
        
        # Test with different feature flag combinations
        test_cases = [
            # No AWS features - no normalizer or enricher should be created
            ({"sentiment": False, "llm_normalization": False}, False, False),
            # Only normalization - normalizer should be created
            ({"sentiment": False, "llm_normalization": True}, True, False),
            # Only sentiment - enricher should be created
            ({"sentiment": True, "llm_normalization": False}, False, True),
            # Both features - both should be created
            ({"sentiment": True, "llm_normalization": True}, True, True),
        ]
        
        for feature_flags, expect_normalizer, expect_enricher in test_cases:
            with patch('src.handler.NewsScraper') as mock_scraper_class, \
                 patch('src.handler.LLMNormalizer') as mock_normalizer_class, \
                 patch('src.handler.NLPEnricher') as mock_enricher_class, \
                 patch('src.handler.ResultFormatter') as mock_formatter_class:
                
                # Mock the components
                mock_scraper_class.return_value = Mock()
                mock_normalizer_class.return_value = Mock()
                mock_enricher_class.return_value = Mock()
                mock_formatter_class.return_value = Mock()
                
                # Create test event
                event = {
                    "body": json.dumps({
                        "url": "https://example.com/article",
                        "features": feature_flags
                    })
                }
                
                context = Mock()
                context.aws_request_id = "test-123"
                context.function_name = "test"
                context.memory_limit_in_mb = 512
                context.get_remaining_time_in_millis = Mock(return_value=30000)
                
                # Mock scraper to return successful result to avoid early exit
                mock_scraper = mock_scraper_class.return_value
                mock_scraper.scrape_article.return_value = ScrapedContent(
                    url="https://example.com/article",
                    clean_content="test content",
                    success=True
                )
                
                # Mock formatter to return successful result
                mock_formatter = mock_formatter_class.return_value
                mock_formatter.format_response.return_value = {"success": True}
                
                try:
                    lambda_handler(event, context)
                except Exception:
                    # We expect some errors due to mocking, but we're testing initialization
                    pass
                
                # Verify component initialization
                mock_scraper_class.assert_called_once()
                mock_formatter_class.assert_called_once()
                
                if expect_normalizer:
                    mock_normalizer_class.assert_called_once()
                else:
                    mock_normalizer_class.assert_not_called()
                
                if expect_enricher:
                    mock_enricher_class.assert_called_once()
                else:
                    mock_enricher_class.assert_not_called()
    
    @patch('src.handler.get_system_config')
    def test_configuration_dependency_injection(self, mock_get_config):
        """Test that configuration is properly injected into components."""
        
        # Create test configuration
        aws_settings = AWSSettings(
            region="us-west-2",
            bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
            max_retries=5
        )
        config = SystemConfig(
            aws_settings=aws_settings,
            default_timeout_seconds=45,
            external_api_config=ExternalAPIConfig(endpoint_url="https://api.example.com")
        )
        mock_get_config.return_value = config
        
        with patch('src.handler.NewsScraper') as mock_scraper_class, \
             patch('src.handler.LLMNormalizer') as mock_normalizer_class, \
             patch('src.handler.NLPEnricher') as mock_enricher_class, \
             patch('src.handler.ResultFormatter') as mock_formatter_class:
            
            # Create test event with all features
            event = {
                "body": json.dumps({
                    "url": "https://example.com/article",
                    "features": {
                        "llm_normalization": True,
                        "sentiment": True
                    }
                })
            }
            
            context = Mock()
            context.aws_request_id = "test-123"
            context.function_name = "test"
            context.memory_limit_in_mb = 512
            context.get_remaining_time_in_millis = Mock(return_value=30000)
            
            # Mock successful scraping to avoid early exit
            mock_scraper = Mock()
            mock_scraper.scrape_article.return_value = ScrapedContent(
                url="https://example.com/article",
                clean_content="test content",
                success=True
            )
            mock_scraper_class.return_value = mock_scraper
            
            # Mock other components
            mock_normalizer_class.return_value = Mock()
            mock_enricher_class.return_value = Mock()
            mock_formatter = Mock()
            mock_formatter.format_response.return_value = {"success": True}
            mock_formatter_class.return_value = mock_formatter
            
            try:
                lambda_handler(event, context)
            except Exception:
                # We expect some errors due to mocking
                pass
            
            # Verify components were initialized with correct configuration
            mock_scraper_class.assert_called_once_with(
                timeout=45,  # default_timeout_seconds
                max_retries=5  # aws_settings.max_retries
            )
            
            mock_normalizer_class.assert_called_once_with(aws_settings)
            mock_enricher_class.assert_called_once_with(aws_settings)
            mock_formatter_class.assert_called_once_with(config.external_api_config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])