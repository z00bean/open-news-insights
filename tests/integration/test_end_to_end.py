"""
End-to-end integration test for the complete Open News Insights system.

This test verifies that all components work together correctly by testing
the complete processing pipeline with minimal mocking.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.handler import lambda_handler


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def mock_lambda_context(self):
        """Create mock Lambda context."""
        context = Mock()
        context.aws_request_id = "test-request-e2e"
        context.function_name = "open-news-insights"
        context.memory_limit_in_mb = 512
        context.get_remaining_time_in_millis = Mock(return_value=30000)
        return context
    
    @patch('src.handler.get_system_config')
    @patch('boto3.client')
    @patch('requests.Session.post')
    def test_complete_pipeline_with_real_components(
        self,
        mock_requests_post,
        mock_boto3_client,
        mock_get_config,
        mock_lambda_context
    ):
        """Test complete pipeline using real component implementations with minimal mocking."""
        
        # Mock system configuration
        from src.config.models import SystemConfig, AWSSettings, ExternalAPIConfig
        
        aws_settings = AWSSettings(
            region="us-east-1",
            bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
            max_retries=2,
            comprehend_max_bytes=5000,
            comprehend_language_code="en"
        )
        
        config = SystemConfig(
            aws_settings=aws_settings,
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig(
                endpoint_url="https://api.example.com/webhook",
                max_retries=2
            )
        )
        mock_get_config.return_value = config
        
        # Mock AWS clients
        mock_bedrock_client = Mock()
        mock_comprehend_client = Mock()
        
        def boto3_client_side_effect(service_name, **kwargs):
            if service_name == 'bedrock-runtime':
                return mock_bedrock_client
            elif service_name == 'comprehend':
                return mock_comprehend_client
            return Mock()
        
        mock_boto3_client.side_effect = boto3_client_side_effect
        
        # Mock Bedrock responses for normalization and summarization
        bedrock_response = {
            'body': Mock()
        }
        bedrock_response['body'].read.return_value = json.dumps({
            'content': [
                {
                    'text': 'This is the cleaned and normalized article content.'
                }
            ]
        }).encode('utf-8')
        mock_bedrock_client.invoke_model.return_value = bedrock_response
        
        # Mock Comprehend responses
        mock_comprehend_client.detect_sentiment.return_value = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.85,
                'Negative': 0.05,
                'Neutral': 0.08,
                'Mixed': 0.02
            }
        }
        
        mock_comprehend_client.detect_pii_entities.return_value = {
            'Entities': []  # No PII detected
        }
        
        mock_comprehend_client.detect_key_phrases.return_value = {
            'KeyPhrases': [
                {
                    'Text': 'technology innovation',
                    'Score': 0.95,
                    'BeginOffset': 10,
                    'EndOffset': 30
                },
                {
                    'Text': 'artificial intelligence',
                    'Score': 0.88,
                    'BeginOffset': 50,
                    'EndOffset': 72
                }
            ]
        }
        
        # Mock external API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Success"
        mock_requests_post.return_value = mock_response
        
        # Mock HTTP fetching to return sample HTML
        sample_html = """
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Technology Innovation in 2024</h1>
                <p class="author">By Tech Reporter</p>
                <div class="content">
                    <p>This is the main article content about technology innovation.</p>
                    <p>The article discusses various aspects of artificial intelligence and machine learning.</p>
                    <p>It provides insights into the future of technology development.</p>
                </div>
            </article>
            <nav>Navigation menu</nav>
            <div class="ads">Advertisement content</div>
        </body>
        </html>
        """
        
        with patch('requests.Session.get') as mock_get:
            mock_http_response = Mock()
            mock_http_response.status_code = 200
            mock_http_response.text = sample_html
            mock_http_response.headers = {'Content-Type': 'text/html; charset=utf-8'}
            mock_http_response.url = "https://example.com/article"
            mock_http_response.raise_for_status.return_value = None
            mock_get.return_value = mock_http_response
            
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
            
            # Verify successful processing
            assert response_body["success"] == True
            
            # Verify all expected sections are present
            assert "article_metadata" in response_body
            assert "extracted_content" in response_body
            assert "normalized_content" in response_body
            assert "sentiment_analysis" in response_body
            assert "pii_detection" in response_body
            assert "topic_analysis" in response_body
            assert "summary" in response_body
            assert "processing_metadata" in response_body
            
            # Verify article metadata
            metadata = response_body["article_metadata"]
            assert metadata["url"] == "https://example.com/article"
            assert metadata["title"] == "Technology Innovation in 2024"
            assert "scrape_timestamp" in metadata
            
            # Verify content extraction worked
            assert len(response_body["extracted_content"]) > 0
            assert "technology innovation" in response_body["extracted_content"].lower()
            
            # Verify normalization worked
            assert response_body["normalized_content"] == "This is the cleaned and normalized article content."
            
            # Verify sentiment analysis
            sentiment = response_body["sentiment_analysis"]
            assert sentiment["sentiment"] == "POSITIVE"
            assert sentiment["confidence_scores"]["POSITIVE"] == 0.85
            
            # Verify PII detection (no PII expected)
            pii = response_body["pii_detection"]
            assert pii["has_pii"] == False
            assert len(pii["entities"]) == 0
            
            # Verify topic analysis
            topics = response_body["topic_analysis"]
            assert len(topics["key_phrases"]) == 2
            assert any("technology innovation" in phrase["text"] for phrase in topics["key_phrases"])
            
            # Verify summary
            assert response_body["summary"] == "This is the cleaned and normalized article content."
            
            # Verify processing metadata
            processing = response_body["processing_metadata"]
            assert processing["processing_time_ms"] > 0
            assert processing["features_enabled"]["sentiment"] == True
            assert processing["features_enabled"]["llm_normalization"] == True
            assert processing["aws_service_calls"]["comprehend"] >= 3  # sentiment, pii, topics
            assert processing["aws_service_calls"]["bedrock"] >= 2  # normalization, summary
            
            # Verify AWS service calls were made
            mock_bedrock_client.invoke_model.assert_called()
            mock_comprehend_client.detect_sentiment.assert_called_once()
            mock_comprehend_client.detect_pii_entities.assert_called_once()
            mock_comprehend_client.detect_key_phrases.assert_called_once()
            
            # Verify external API was called
            mock_requests_post.assert_called_once()
            call_args = mock_requests_post.call_args
            assert call_args[0][0] == "https://api.example.com/webhook"
            assert "json" in call_args[1]
    
    @patch('src.handler.get_system_config')
    def test_basic_scraping_only_pipeline(self, mock_get_config, mock_lambda_context):
        """Test pipeline with only basic scraping (no AWS features)."""
        
        # Mock minimal configuration
        from src.config.models import SystemConfig, AWSSettings, ExternalAPIConfig
        
        config = SystemConfig(
            aws_settings=AWSSettings(region="us-east-1"),
            default_timeout_seconds=30,
            external_api_config=ExternalAPIConfig()
        )
        mock_get_config.return_value = config
        
        # Mock HTTP fetching
        sample_html = """
        <html>
        <head><title>Simple Article</title></head>
        <body>
            <h1>Simple Article Title</h1>
            <p>This is a simple article with basic content.</p>
        </body>
        </html>
        """
        
        with patch('requests.Session.get') as mock_get:
            mock_http_response = Mock()
            mock_http_response.status_code = 200
            mock_http_response.text = sample_html
            mock_http_response.headers = {'Content-Type': 'text/html'}
            mock_http_response.url = "https://example.com/simple"
            mock_http_response.raise_for_status.return_value = None
            mock_get.return_value = mock_http_response
            
            # Create test event with no features enabled
            event = {
                "body": json.dumps({
                    "url": "https://example.com/simple",
                    "features": {}
                })
            }
            
            # Execute Lambda handler
            response = lambda_handler(event, mock_lambda_context)
            
            # Verify response
            assert response["statusCode"] == 200
            response_body = json.loads(response["body"])
            
            assert response_body["success"] == True
            assert "article_metadata" in response_body
            assert "extracted_content" in response_body
            
            # Verify no AWS features were processed
            assert response_body.get("normalized_content") is None
            assert response_body.get("sentiment_analysis") is None
            assert response_body.get("pii_detection") is None
            assert response_body.get("topic_analysis") is None
            assert response_body.get("summary") is None
            
            # Verify basic content extraction worked
            assert len(response_body["extracted_content"]) > 0
            assert "simple article" in response_body["extracted_content"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])