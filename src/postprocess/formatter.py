"""
Result formatter and external API integration for Open News Insights.

This module provides structured response formatting and external API posting
functionality with comprehensive error handling and retry logic.
"""

import json
import logging
import time
import requests
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
from urllib.parse import urlparse

from ..config.models import ExternalAPIConfig
from ..config.timeouts import get_timeout_manager
from ..scraper.extractor import ExtractedContent
from ..analysis.enricher import EnrichmentResults


logger = logging.getLogger(__name__)


class FormattingError(Exception):
    """Custom exception for result formatting errors."""
    
    def __init__(self, message: str, error_type: str = "FORMATTING_ERROR", details: Optional[Dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class ExternalAPIError(Exception):
    """Custom exception for external API errors."""
    
    def __init__(self, message: str, error_type: str = "API_ERROR", details: Optional[Dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


@dataclass
class ArticleMetadata:
    """Metadata about the original article."""
    
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[str] = None
    scrape_timestamp: str = None
    domain: Optional[str] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.scrape_timestamp is None:
            self.scrape_timestamp = datetime.utcnow().isoformat() + "Z"
        
        if self.domain is None and self.url:
            try:
                parsed = urlparse(self.url)
                self.domain = parsed.netloc if parsed.netloc else None
            except Exception:
                self.domain = None


@dataclass
class ProcessingMetadata:
    """Metadata about the processing pipeline."""
    
    processing_time_ms: int
    features_enabled: Dict[str, bool]
    aws_service_calls: Dict[str, int]
    errors_encountered: List[str]
    extraction_method: str
    extraction_confidence: float
    
    def __post_init__(self):
        """Initialize default values."""
        if self.aws_service_calls is None:
            self.aws_service_calls = {}
        if self.errors_encountered is None:
            self.errors_encountered = []


@dataclass
class FormattedResponse:
    """Complete formatted response structure."""
    
    success: bool
    article_metadata: ArticleMetadata
    extracted_content: str
    normalized_content: Optional[str] = None
    sentiment_analysis: Optional[Dict[str, Any]] = None
    pii_detection: Optional[Dict[str, Any]] = None
    topic_analysis: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    processing_metadata: Optional[ProcessingMetadata] = None
    timestamp: str = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + "Z"


class ResultFormatter:
    """
    Result formatter with external API integration.
    
    Formats processing results into structured responses and handles
    posting to external APIs with retry logic and error handling.
    """
    
    def __init__(self, external_api_config: Optional[ExternalAPIConfig] = None):
        """
        Initialize result formatter.
        
        Args:
            external_api_config: Configuration for external API integration
        """
        self.external_api_config = external_api_config or ExternalAPIConfig()
        self.timeout_manager = get_timeout_manager()
        self.session = requests.Session()
        
        # Configure session defaults
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'OpenNewsInsights/1.0'
        })
        
        # Set timeout using timeout manager
        timeout_tuple = self.timeout_manager.get_http_timeout("api_call")
        self.session.timeout = timeout_tuple
    
    def format_response(
        self,
        url: str,
        extracted_content: ExtractedContent,
        enrichment_results: Optional[EnrichmentResults] = None,
        normalized_content: Optional[str] = None,
        features_enabled: Optional[Dict[str, bool]] = None,
        processing_time_ms: int = 0,
        title: Optional[str] = None,
        author: Optional[str] = None,
        publish_date: Optional[str] = None
    ) -> FormattedResponse:
        """
        Format processing results into structured response.
        
        Args:
            url: Original article URL
            extracted_content: Extracted and cleaned content
            enrichment_results: Optional NLP enrichment results
            normalized_content: Optional LLM-normalized content
            features_enabled: Dictionary of enabled features
            processing_time_ms: Total processing time
            title: Article title
            author: Article author
            publish_date: Article publish date
            
        Returns:
            FormattedResponse with all processing results
            
        Raises:
            FormattingError: If formatting fails
        """
        try:
            # Create article metadata
            article_metadata = ArticleMetadata(
                url=url,
                title=title,
                author=author,
                publish_date=publish_date
            )
            
            # Create processing metadata
            processing_metadata = ProcessingMetadata(
                processing_time_ms=processing_time_ms,
                features_enabled=features_enabled or {},
                aws_service_calls=self._count_aws_service_calls(enrichment_results),
                errors_encountered=self._extract_errors(extracted_content, enrichment_results),
                extraction_method=extracted_content.extraction_method if extracted_content else "unknown",
                extraction_confidence=extracted_content.confidence_score if extracted_content else 0.0
            )
            
            # Format enrichment results
            sentiment_data = None
            pii_data = None
            topic_data = None
            summary_text = None
            
            if enrichment_results:
                sentiment_data = self._format_sentiment_result(enrichment_results.sentiment)
                pii_data = self._format_pii_result(enrichment_results.pii_detection)
                topic_data = self._format_topic_result(enrichment_results.topics)
                
                if enrichment_results.summary:
                    summary_text = enrichment_results.summary.summary
            
            # Create formatted response
            response = FormattedResponse(
                success=True,
                article_metadata=article_metadata,
                extracted_content=extracted_content.clean_text if extracted_content else "",
                normalized_content=normalized_content,
                sentiment_analysis=sentiment_data,
                pii_detection=pii_data,
                topic_analysis=topic_data,
                summary=summary_text,
                processing_metadata=processing_metadata
            )
            
            logger.info(f"Response formatted successfully for URL: {url}")
            return response
            
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            raise FormattingError(
                f"Failed to format response: {str(e)}",
                "RESPONSE_FORMATTING_ERROR",
                {"url": url, "error": str(e)}
            )
    
    def format_error_response(
        self,
        url: str,
        error_message: str,
        error_type: str = "PROCESSING_ERROR",
        processing_step: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format error response with consistent structure.
        
        Args:
            url: Original article URL
            error_message: Error description
            error_type: Type of error
            processing_step: Step where error occurred
            partial_results: Any partial results available
            
        Returns:
            Structured error response dictionary
        """
        try:
            error_response = {
                "success": False,
                "error": {
                    "type": error_type,
                    "message": error_message,
                    "step": processing_step,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                },
                "article_metadata": {
                    "url": url,
                    "scrape_timestamp": datetime.utcnow().isoformat() + "Z"
                },
                "partial_results": partial_results or {},
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            logger.info(f"Error response formatted for URL: {url}")
            return error_response
            
        except Exception as e:
            logger.error(f"Error formatting error response: {str(e)}")
            # Return minimal error response if formatting fails
            return {
                "success": False,
                "error": {
                    "type": "FORMATTING_ERROR",
                    "message": f"Failed to format error response: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                },
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    def post_to_external_api(self, data: Union[FormattedResponse, Dict[str, Any]]) -> bool:
        """
        POST results to configured external API with retry logic.
        
        Args:
            data: Formatted response data to post
            
        Returns:
            True if posting succeeded, False otherwise
            
        Raises:
            ExternalAPIError: If posting fails after all retries
        """
        if not self.external_api_config.endpoint_url:
            logger.info("No external API endpoint configured, skipping post")
            return True
        
        # Convert dataclass to dict if needed
        if isinstance(data, FormattedResponse):
            payload = self._convert_to_json_serializable(asdict(data))
        else:
            payload = data
        
        # Add authentication header if configured
        headers = {}
        if self.external_api_config.auth_header:
            headers['Authorization'] = self.external_api_config.auth_header
        
        last_error = None
        
        for attempt in range(self.external_api_config.max_retries + 1):
            try:
                logger.info(f"Posting to external API (attempt {attempt + 1}/{self.external_api_config.max_retries + 1})")
                
                # Get timeout configuration for external API calls
                timeout_tuple = self.timeout_manager.get_http_timeout("api_call")
                
                response = self.session.post(
                    self.external_api_config.endpoint_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout_tuple
                )
                
                # Check if request was successful
                if response.status_code in [200, 201, 202]:
                    logger.info(f"Successfully posted to external API: {response.status_code}")
                    return True
                else:
                    error_msg = f"External API returned status {response.status_code}: {response.text[:200]}"
                    logger.warning(error_msg)
                    last_error = ExternalAPIError(
                        error_msg,
                        "HTTP_ERROR",
                        {
                            "status_code": response.status_code,
                            "response_text": response.text[:500],
                            "attempt": attempt + 1
                        }
                    )
                
            except requests.exceptions.Timeout as e:
                timeout_config = self.timeout_manager.get_http_timeout("api_call")
                error_msg = f"External API request timed out after {timeout_config[0]}s connect, {timeout_config[1]}s read"
                logger.warning(f"{error_msg} (attempt {attempt + 1})")
                last_error = ExternalAPIError(
                    error_msg,
                    "TIMEOUT_ERROR",
                    {
                        "connect_timeout": timeout_config[0],
                        "read_timeout": timeout_config[1],
                        "attempt": attempt + 1
                    }
                )
                
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Failed to connect to external API: {str(e)}"
                logger.warning(f"{error_msg} (attempt {attempt + 1})")
                last_error = ExternalAPIError(
                    error_msg,
                    "CONNECTION_ERROR",
                    {"connection_error": str(e), "attempt": attempt + 1}
                )
                
            except requests.exceptions.RequestException as e:
                error_msg = f"External API request failed: {str(e)}"
                logger.warning(f"{error_msg} (attempt {attempt + 1})")
                last_error = ExternalAPIError(
                    error_msg,
                    "REQUEST_ERROR",
                    {"request_error": str(e), "attempt": attempt + 1}
                )
                
            except Exception as e:
                error_msg = f"Unexpected error posting to external API: {str(e)}"
                logger.error(f"{error_msg} (attempt {attempt + 1})")
                last_error = ExternalAPIError(
                    error_msg,
                    "UNEXPECTED_ERROR",
                    {"error": str(e), "attempt": attempt + 1}
                )
            
            # Wait before retry (except on last attempt)
            if attempt < self.external_api_config.max_retries:
                delay = self._calculate_retry_delay(attempt)
                logger.info(f"Waiting {delay:.2f}s before retry...")
                time.sleep(delay)
        
        # All retries exhausted
        logger.error(f"Failed to post to external API after {self.external_api_config.max_retries + 1} attempts")
        if last_error:
            raise last_error
        else:
            raise ExternalAPIError("Unknown error posting to external API")
    
    def _count_aws_service_calls(self, enrichment_results: Optional[EnrichmentResults]) -> Dict[str, int]:
        """Count AWS service calls made during processing."""
        calls = {"comprehend": 0, "bedrock": 0}
        
        if enrichment_results:
            # Count Comprehend calls
            if enrichment_results.sentiment:
                calls["comprehend"] += 1
            if enrichment_results.pii_detection:
                calls["comprehend"] += 1
            if enrichment_results.topics:
                calls["comprehend"] += 1
            
            # Count Bedrock calls
            if enrichment_results.summary:
                calls["bedrock"] += 1
        
        return calls
    
    def _extract_errors(
        self,
        extracted_content: Optional[ExtractedContent],
        enrichment_results: Optional[EnrichmentResults]
    ) -> List[str]:
        """Extract error messages from processing results."""
        errors = []
        
        # Check extraction errors
        if extracted_content and extracted_content.error_details:
            error_msg = extracted_content.error_details.get("error_message")
            if error_msg:
                errors.append(f"Extraction: {error_msg}")
        
        # Note: EnrichmentResults doesn't currently track individual errors
        # This could be enhanced in the future
        
        return errors
    
    def _format_sentiment_result(self, sentiment_result) -> Optional[Dict[str, Any]]:
        """Format sentiment analysis result for JSON serialization."""
        if not sentiment_result:
            return None
        
        return {
            "sentiment": sentiment_result.sentiment,
            "confidence_scores": sentiment_result.confidence_scores,
            "dominant_confidence": sentiment_result.dominant_sentiment_confidence
        }
    
    def _format_pii_result(self, pii_result) -> Optional[Dict[str, Any]]:
        """Format PII detection result for JSON serialization."""
        if not pii_result:
            return None
        
        entities = []
        for entity in pii_result.entities:
            entities.append({
                "type": entity.type,
                "text": entity.text,
                "confidence": entity.confidence,
                "begin_offset": entity.begin_offset,
                "end_offset": entity.end_offset
            })
        
        return {
            "entities": entities,
            "has_pii": pii_result.has_pii,
            "pii_types": pii_result.pii_types,
            "redacted_text": pii_result.redacted_text
        }
    
    def _format_topic_result(self, topic_result) -> Optional[Dict[str, Any]]:
        """Format topic analysis result for JSON serialization."""
        if not topic_result:
            return None
        
        key_phrases = []
        for phrase in topic_result.key_phrases:
            key_phrases.append({
                "text": phrase.text,
                "confidence": phrase.confidence,
                "begin_offset": phrase.begin_offset,
                "end_offset": phrase.end_offset
            })
        
        return {
            "key_phrases": key_phrases,
            "topics": topic_result.topics,
            "top_phrases": [
                {
                    "text": phrase.text,
                    "confidence": phrase.confidence,
                    "begin_offset": phrase.begin_offset,
                    "end_offset": phrase.end_offset
                }
                for phrase in topic_result.top_phrases
            ]
        }
    
    def _convert_to_json_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if isinstance(obj, dict):
            return {key: self._convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return self._convert_to_json_serializable(asdict(obj) if hasattr(obj, '__dataclass_fields__') else obj.__dict__)
        else:
            return obj
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff."""
        base_delay = self.external_api_config.retry_delay_seconds
        # Exponential backoff: base_delay * 2^attempt
        delay = base_delay * (2 ** attempt)
        # Cap at 30 seconds
        return min(delay, 30.0)