"""
Unit tests for the Lambda handler module.

Tests the main entry point and orchestration logic for the Open News Insights
Lambda function, including API Gateway event parsing, feature flag validation,
and error handling.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the handler module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock the relative imports before importing handler
from unittest.mock import MagicMock
sys.modules['src.config.manager'] = MagicMock()
sys.modules['src.scraper.scraper'] = MagicMock()
sys.modules['src.analysis.normalizer'] = MagicMock()
sys.modules['src.analysis.enricher'] = MagicMock()
sys.modules['src.postprocess.formatter'] = MagicMock()
sys.modules['src.scraper.extractor'] = MagicMock()

from src.handler import (
    parse_api_gateway_event,
    parse_feature_flags,
    validate_feature_flags,
    create_error_response,
    create_api_response,
    HandlerError,
    _is_recoverable_error,
    _should_retry_error,
    _get_troubleshooting_hints
)


class TestAPIGatewayEventParsing:
    """Test API Gateway event parsing functionality."""
    
    def test_parse_direct_invocation_event(self):
        """Test parsing direct Lambda invocation event."""
        event = {
            "url": "https://example.com/article",
            "features": {
                "sentiment": True,
                "pii": False
            }
        }
        
        result = parse_api_gateway_event(event)
        
        assert result["url"] == "https://example.com/article"
        assert result["feature_flags"]["sentiment"] == True
        assert result["feature_flags"]["pii"] == False
    
    def test_parse_api_gateway_proxy_event(self):
        """Test parsing API Gateway proxy integration event."""
        event = {
            "body": json.dumps({
                "url": "https://example.com/article",
                "features": {
                    "topics": True
                }
            })
        }
        
        result = parse_api_gateway_event(event)
        
        assert result["url"] == "https://example.com/article"
        assert result["feature_flags"]["topics"] == True
    
    def test_parse_event_missing_url(self):
        """Test parsing event with missing URL."""
        event = {
            "features": {"sentiment": True}
        }
        
        with pytest.raises(HandlerError) as exc_info:
            parse_api_gateway_event(event)
        
        assert exc_info.value.error_type == "VALIDATION_ERROR"
        assert exc_info.value.status_code == 400
        assert "Missing required field: url" in str(exc_info.value)
    
    def test_parse_event_empty_url(self):
        """Test parsing event with empty URL."""
        event = {
            "url": "",
            "features": {}
        }
        
        with pytest.raises(HandlerError) as exc_info:
            parse_api_gateway_event(event)
        
        assert exc_info.value.error_type == "VALIDATION_ERROR"
        assert "URL must be a non-empty string" in str(exc_info.value)
    
    def test_parse_event_invalid_json(self):
        """Test parsing event with invalid JSON body."""
        event = {
            "body": "invalid json"
        }
        
        with pytest.raises(HandlerError) as exc_info:
            parse_api_gateway_event(event)
        
        assert exc_info.value.error_type == "VALIDATION_ERROR"
        assert "Invalid JSON" in str(exc_info.value)


class TestFeatureFlagParsing:
    """Test feature flag parsing and validation."""
    
    def test_parse_feature_flags_boolean_values(self):
        """Test parsing boolean feature flag values."""
        features = {
            "sentiment": True,
            "pii": False,
            "topics": True
        }
        
        result = parse_feature_flags(features)
        
        assert result["sentiment"] == True
        assert result["pii"] == False
        assert result["topics"] == True
        assert result["llm_normalization"] == False  # Default
        assert result["summary"] == False  # Default
        assert result["external_api"] == False  # Default
    
    def test_parse_feature_flags_string_values(self):
        """Test parsing string feature flag values."""
        features = {
            "sentiment": "true",
            "pii": "false",
            "topics": "yes",
            "summary": "no",
            "llm_normalization": "1",
            "external_api": "0"
        }
        
        result = parse_feature_flags(features)
        
        assert result["sentiment"] == True
        assert result["pii"] == False
        assert result["topics"] == True
        assert result["summary"] == False
        assert result["llm_normalization"] == True
        assert result["external_api"] == False
    
    def test_parse_feature_flags_numeric_values(self):
        """Test parsing numeric feature flag values."""
        features = {
            "sentiment": 1,
            "pii": 0,
            "topics": 2.5,
            "summary": 0.0
        }
        
        result = parse_feature_flags(features)
        
        assert result["sentiment"] == True
        assert result["pii"] == False
        assert result["topics"] == True
        assert result["summary"] == False
    
    def test_validate_feature_flags_all_disabled(self):
        """Test validation with all features disabled."""
        flags = {
            "sentiment": False,
            "pii": False,
            "topics": False,
            "summary": False,
            "llm_normalization": False,
            "external_api": False
        }
        
        # Should not raise any exception
        validate_feature_flags(flags)
    
    def test_validate_feature_flags_some_enabled(self):
        """Test validation with some features enabled."""
        flags = {
            "sentiment": True,
            "pii": False,
            "topics": True,
            "summary": False,
            "llm_normalization": False,
            "external_api": True
        }
        
        # Should not raise any exception
        validate_feature_flags(flags)


class TestErrorHandling:
    """Test error handling and response creation."""
    
    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        response = create_error_response(
            url="https://example.com/article",
            error_message="Test error",
            error_type="TEST_ERROR",
            processing_step="testing"
        )
        
        assert response["success"] == False
        assert response["error"]["type"] == "TEST_ERROR"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["step"] == "testing"
        assert response["error"]["recoverable"] == False
        assert response["error"]["retry_recommended"] == False
        assert response["article_metadata"]["url"] == "https://example.com/article"
        assert "timestamp" in response["error"]
        assert "timestamp" in response
    
    def test_create_error_response_with_partial_results(self):
        """Test error response creation with partial results."""
        partial_results = {
            "scraping": {"success": True, "content_length": 1000}
        }
        
        response = create_error_response(
            url="https://example.com/article",
            error_message="Processing failed",
            error_type="PROCESSING_ERROR",
            processing_step="enrichment",
            partial_results=partial_results
        )
        
        assert response["partial_results"] == partial_results
    
    def test_is_recoverable_error(self):
        """Test recoverable error detection."""
        assert _is_recoverable_error("TIMEOUT_ERROR") == True
        assert _is_recoverable_error("CONNECTION_ERROR") == True
        assert _is_recoverable_error("AWS_SERVICE_ERROR") == True
        assert _is_recoverable_error("VALIDATION_ERROR") == False
        assert _is_recoverable_error("UNKNOWN_ERROR") == False
    
    def test_should_retry_error(self):
        """Test retry recommendation logic."""
        assert _should_retry_error("TIMEOUT_ERROR") == True
        assert _should_retry_error("CONNECTION_ERROR") == True
        assert _should_retry_error("AWS_SERVICE_ERROR") == True
        assert _should_retry_error("VALIDATION_ERROR") == False
        assert _should_retry_error("PROCESSING_ERROR") == False
    
    def test_get_troubleshooting_hints(self):
        """Test troubleshooting hints generation."""
        hints = _get_troubleshooting_hints("VALIDATION_ERROR", "request_parsing")
        assert len(hints) > 0
        assert any("URL" in hint for hint in hints)
        
        hints = _get_troubleshooting_hints("AWS_SERVICE_ERROR", "enrichment")
        assert len(hints) > 0
        assert any("AWS" in hint for hint in hints)
        
        hints = _get_troubleshooting_hints("SCRAPING_ERROR", "scraping")
        assert len(hints) > 0
        assert any("website" in hint.lower() for hint in hints)


class TestAPIResponseCreation:
    """Test API Gateway response creation."""
    
    def test_create_api_response_success(self):
        """Test successful API response creation."""
        body = {"success": True, "data": "test"}
        
        response = create_api_response(200, body)
        
        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"
        assert response["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Headers" in response["headers"]
        assert "Access-Control-Allow-Methods" in response["headers"]
        
        parsed_body = json.loads(response["body"])
        assert parsed_body == body
    
    def test_create_api_response_error(self):
        """Test error API response creation."""
        body = {"success": False, "error": {"type": "TEST_ERROR"}}
        
        response = create_api_response(400, body)
        
        assert response["statusCode"] == 400
        parsed_body = json.loads(response["body"])
        assert parsed_body == body
    
    def test_create_api_response_with_dataclass(self):
        """Test API response creation with dataclass body."""
        from dataclasses import dataclass
        
        @dataclass
        class TestData:
            success: bool
            message: str
        
        body = TestData(success=True, message="test")
        
        response = create_api_response(200, body)
        
        assert response["statusCode"] == 200
        parsed_body = json.loads(response["body"])
        assert parsed_body["success"] == True
        assert parsed_body["message"] == "test"


class TestHandlerError:
    """Test custom HandlerError exception."""
    
    def test_handler_error_creation(self):
        """Test HandlerError creation with default values."""
        error = HandlerError("Test error")
        
        assert str(error) == "Test error"
        assert error.error_type == "HANDLER_ERROR"
        assert error.status_code == 500
    
    def test_handler_error_creation_with_custom_values(self):
        """Test HandlerError creation with custom values."""
        error = HandlerError("Validation failed", "VALIDATION_ERROR", 400)
        
        assert str(error) == "Validation failed"
        assert error.error_type == "VALIDATION_ERROR"
        assert error.status_code == 400