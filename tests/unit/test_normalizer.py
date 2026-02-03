"""
Unit tests for LLM normalizer functionality.

Tests the AWS Bedrock integration for text normalization with error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from botocore.exceptions import ClientError

from src.config.models import AWSSettings
from src.analysis.normalizer import LLMNormalizer, NormalizedContent
from src.analysis.error_handler import BedrockServiceError, BedrockTimeoutError, BedrockError


class TestLLMNormalizer:
    """Test cases for LLM normalizer."""
    
    @pytest.fixture
    def aws_settings(self):
        """Create test AWS settings."""
        return AWSSettings(
            region="us-east-1",
            bedrock_model_id="anthropic.claude-3-haiku-20240307-v1:0",
            max_retries=2,
            timeout_seconds=30
        )
    
    @pytest.fixture
    def normalizer(self, aws_settings):
        """Create normalizer instance."""
        return LLMNormalizer(aws_settings)
    
    def test_normalize_text_success(self, normalizer):
        """Test successful text normalization."""
        # Mock Bedrock response
        mock_response = {
            'content': [
                {
                    'text': 'This is the cleaned article text.'
                }
            ]
        }
        
        with patch.object(normalizer, '_invoke_bedrock_with_retry', return_value=mock_response):
            result = normalizer.normalize_text("Original article with ads and navigation")
            
            assert isinstance(result, NormalizedContent)
            assert result.normalized_text == 'This is the cleaned article text.'
            assert result.original_length > 0
            assert result.normalized_length > 0
            assert result.processing_time_ms >= 0  # Allow 0 for fast tests
            assert result.model_used == "anthropic.claude-3-haiku-20240307-v1:0"
    
    def test_normalize_empty_text_raises_error(self, normalizer):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            normalizer.normalize_text("")
    
    def test_normalize_too_long_text_raises_error(self, normalizer):
        """Test that overly long text raises ValueError."""
        long_text = "x" * 100001  # Exceeds 100KB limit
        
        with pytest.raises(ValueError, match="Text too long for normalization"):
            normalizer.normalize_text(long_text)
    
    def test_build_prompt(self, normalizer):
        """Test prompt building."""
        text = "Sample article text"
        prompt = normalizer.build_prompt(text)
        
        assert "Sample article text" in prompt
        assert "clean and normalize" in prompt
        assert "Human:" in prompt
        assert "Assistant:" in prompt
    
    def test_bedrock_client_initialization(self, normalizer):
        """Test lazy Bedrock client initialization."""
        # Client should be None initially
        assert normalizer._bedrock_client is None
        
        # Accessing property should initialize client
        with patch('boto3.client') as mock_boto3:
            mock_client = Mock()
            mock_boto3.return_value = mock_client
            
            client = normalizer.bedrock_client
            
            assert client == mock_client
            assert normalizer._bedrock_client == mock_client
            mock_boto3.assert_called_once()
    
    @patch('src.analysis.normalizer.time.sleep')
    def test_retry_logic_on_retryable_error(self, mock_sleep, normalizer):
        """Test retry logic with retryable errors."""
        # Mock a retryable error followed by success
        mock_response = {'content': [{'text': 'Success'}]}
        
        with patch.object(normalizer, '_invoke_bedrock') as mock_invoke:
            # First call fails with throttling, second succeeds
            mock_invoke.side_effect = [
                ClientError(
                    {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate limit'}},
                    'InvokeModel'
                ),
                mock_response
            ]
            
            result = normalizer._invoke_bedrock_with_retry("test prompt")
            
            assert result == mock_response
            assert mock_invoke.call_count == 2
            mock_sleep.assert_called_once()  # Should sleep between retries
    
    def test_non_retryable_error_fails_immediately(self, normalizer):
        """Test that non-retryable errors fail immediately."""
        with patch.object(normalizer, '_invoke_bedrock') as mock_invoke:
            mock_invoke.side_effect = ClientError(
                {'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'}},
                'InvokeModel'
            )
            
            with pytest.raises(BedrockServiceError) as exc_info:
                normalizer._invoke_bedrock_with_retry("test prompt")
            
            assert not exc_info.value.retryable
            assert mock_invoke.call_count == 1  # Should not retry
    
    def test_max_retries_exceeded(self, normalizer):
        """Test behavior when max retries are exceeded."""
        with patch.object(normalizer, '_invoke_bedrock') as mock_invoke:
            # Always fail with retryable error
            mock_invoke.side_effect = ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate limit'}},
                'InvokeModel'
            )
            
            with patch('src.analysis.normalizer.time.sleep'):
                with pytest.raises(BedrockError):  # Accept any BedrockError subclass
                    normalizer._invoke_bedrock_with_retry("test prompt")
            
            # Should try max_retries + 1 times (initial + retries)
            assert mock_invoke.call_count == normalizer.retry_config.max_retries + 1