"""
AWS Lambda handler for Open News Insights API.

This module provides the main entry point for the Lambda function,
handling API Gateway events and orchestrating the news processing pipeline.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from .config.manager import get_system_config
from .config.logging import get_logger, LogContext
from .scraper.scraper import NewsScraper
from .analysis.normalizer import LLMNormalizer
from .analysis.enricher import NLPEnricher
from .postprocess.formatter import ResultFormatter


# Configure structured logging
logger = get_logger(__name__)


class HandlerError(Exception):
    """Custom exception for handler-level errors."""
    
    def __init__(self, message: str, error_type: str = "HANDLER_ERROR", status_code: int = 500):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for API Gateway proxy integration.
    
    Processes news article URLs through a configurable pipeline including
    scraping, text extraction, optional LLM normalization, NLP enrichment,
    and external API forwarding based on feature flags.
    
    Implements comprehensive error handling with graceful degradation:
    - Returns partial results when non-critical features fail
    - Provides detailed error information for troubleshooting
    - Continues processing when possible rather than failing completely
    
    Args:
        event: API Gateway event containing request data
        context: Lambda runtime context
        
    Returns:
        API Gateway response format with status code and body
    """
    start_time = datetime.now()
    request_url = "unknown"
    request_id = getattr(context, 'aws_request_id', f"req_{int(time.time())}")
    
    # Initialize logging context
    log_context = LogContext(request_id=request_id)
    logger.set_context(request_id=request_id)
    
    with logger.timed_operation("lambda_handler"):
        try:
            # Parse API Gateway event
            with logger.timed_operation("parse_request"):
                request_data = parse_api_gateway_event(event)
                request_url = request_data["url"]
                feature_flags = request_data["feature_flags"]
                
                # Update logging context
                logger.set_context(url=request_url, feature_flags=feature_flags)
                
                logger.info(
                    "Processing request",
                    url=request_url,
                    features_enabled=list(feature_flags.keys()),
                    lambda_context={
                        "function_name": getattr(context, 'function_name', 'unknown'),
                        "memory_limit": getattr(context, 'memory_limit_in_mb', 'unknown'),
                        "remaining_time": getattr(context, 'get_remaining_time_in_millis', lambda: 'unknown')()
                    }
                )
            
            # Load system configuration with error handling
            try:
                with logger.timed_operation("load_configuration"):
                    config = get_system_config()
                    logger.info("System configuration loaded successfully")
            except Exception as e:
                logger.error("Failed to load system configuration", error=e)
                raise HandlerError(
                    f"Configuration error: {str(e)}",
                    "CONFIGURATION_ERROR",
                    500
                )
            
            # Initialize components with error handling
            try:
                with logger.timed_operation("initialize_components"):
                    scraper = NewsScraper(
                        timeout=config.default_timeout_seconds,
                        max_retries=config.aws_settings.max_retries
                    )
                    
                    formatter = ResultFormatter(config.external_api_config)
                    
                    # Initialize optional components based on feature flags
                    normalizer = None
                    enricher = None
                    
                    if any(feature_flags.get(f, False) for f in ["llm_normalization", "sentiment", "pii", "topics", "summary"]):
                        if feature_flags.get("llm_normalization", False):
                            normalizer = LLMNormalizer(config.aws_settings)
                        
                        if any(feature_flags.get(f, False) for f in ["sentiment", "pii", "topics", "summary"]):
                            enricher = NLPEnricher(config.aws_settings)
                    
                    logger.info(
                        "Components initialized successfully",
                        components={
                            "scraper": True,
                            "formatter": True,
                            "normalizer": normalizer is not None,
                            "enricher": enricher is not None
                        }
                    )
                            
            except Exception as e:
                logger.error("Failed to initialize components", error=e)
                raise HandlerError(
                    f"Component initialization error: {str(e)}",
                    "INITIALIZATION_ERROR",
                    500
                )
            
            # Execute processing pipeline
            with logger.timed_operation("processing_pipeline"):
                processing_results = execute_processing_pipeline(
                    url=request_url,
                    feature_flags=feature_flags,
                    scraper=scraper,
                    normalizer=normalizer,
                    enricher=enricher,
                    formatter=formatter
                )
            
            # Calculate total processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.log_metrics({
                "total_processing_time_ms": int(processing_time),
                "request_size_bytes": len(json.dumps(event)),
                "memory_used_mb": getattr(context, 'memory_limit_in_mb', 0),
                "remaining_time_ms": getattr(context, 'get_remaining_time_in_millis', lambda: 0)()
            }, "lambda_execution")
            
            # Handle successful processing (including partial failures)
            if processing_results["success"]:
                response_body = processing_results["response"]
                
                # Update processing time in metadata
                if hasattr(response_body, 'processing_metadata') and response_body.processing_metadata:
                    response_body.processing_metadata.processing_time_ms = int(processing_time)
                elif isinstance(response_body, dict):
                    # For minimal responses, add processing time
                    response_body["processing_time_ms"] = int(processing_time)
                
                # Handle external API posting with error handling
                external_api_error = None
                if feature_flags.get("external_api", False):
                    try:
                        with logger.timed_operation("external_api_post"):
                            formatter.post_to_external_api(response_body)
                            logger.info("Successfully posted results to external API")
                    except Exception as e:
                        external_api_error = str(e)
                        logger.warning("Failed to post to external API", error=e)
                        # Don't fail the entire request for external API errors
                        
                        # Add external API error to response
                        if isinstance(response_body, dict):
                            if "processing_errors" not in response_body:
                                response_body["processing_errors"] = []
                            response_body["processing_errors"].append(f"External API posting failed: {external_api_error}")
                        elif hasattr(response_body, 'processing_metadata') and response_body.processing_metadata:
                            response_body.processing_metadata.errors_encountered.append(f"External API posting failed: {external_api_error}")
                
                # Determine response status code
                status_code = 200
                if processing_results.get("partial_failures", False):
                    status_code = 206  # Partial Content - indicates some features failed
                
                logger.info(
                    "Request completed successfully",
                    status_code=status_code,
                    partial_failures=processing_results.get("partial_failures", False),
                    processing_errors=processing_results.get("processing_errors", [])
                )
                
                return create_api_response(status_code, response_body)
            else:
                # Return error response
                error_response = processing_results["error_response"]
                status_code = processing_results.get("status_code", 500)
                
                # Add processing time to error response
                error_response["processing_time_ms"] = int(processing_time)
                
                logger.error(
                    "Request failed",
                    status_code=status_code,
                    error_type=error_response.get("error", {}).get("type"),
                    error_message=error_response.get("error", {}).get("message")
                )
                
                return create_api_response(status_code, error_response)
        
        except HandlerError as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error("Handler error occurred", error=e, processing_time_ms=int(processing_time))
            
            error_response = create_error_response(
                url=request_url,
                error_message=str(e),
                error_type=e.error_type,
                processing_step="request_handling"
            )
            error_response["processing_time_ms"] = int(processing_time)
            
            return create_api_response(e.status_code, error_response)
        
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error("Unexpected error in Lambda handler", error=e, processing_time_ms=int(processing_time))
            
            error_response = create_error_response(
                url=request_url,
                error_message=f"Internal server error: {str(e)}",
                error_type="INTERNAL_ERROR",
                processing_step="handler"
            )
            error_response["processing_time_ms"] = int(processing_time)
            
            return create_api_response(500, error_response)


def parse_api_gateway_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate API Gateway event data.
    
    Args:
        event: Raw API Gateway event
        
    Returns:
        Dictionary with parsed URL and feature flags
        
    Raises:
        HandlerError: If event format is invalid or required fields are missing
    """
    try:
        logger.info("Parsing API Gateway event", event_keys=list(event.keys()))
        
        # Handle both direct invocation and API Gateway proxy format
        if "body" in event:
            # API Gateway proxy integration
            body = event["body"]
            if isinstance(body, str):
                body = json.loads(body)
                logger.debug("Parsed JSON body from string")
        else:
            # Direct invocation
            body = event
            logger.debug("Using event as direct body")
        
        logger.debug("Request body parsed", body_keys=list(body.keys()) if isinstance(body, dict) else "non-dict")
        
        # Extract and validate URL
        url = body.get("url")
        if url is None:
            logger.error("Missing required field: url", body=body)
            raise HandlerError("Missing required field: url", "VALIDATION_ERROR", 400)
        
        if not isinstance(url, str) or not url.strip():
            logger.error("Invalid URL format", url=url, url_type=type(url).__name__)
            raise HandlerError("URL must be a non-empty string", "VALIDATION_ERROR", 400)
        
        # Parse and validate feature flags
        features_raw = body.get("features", {})
        logger.debug("Raw features from request", features=features_raw)
        
        feature_flags = parse_feature_flags(features_raw)
        
        logger.info(
            "API Gateway event parsed successfully",
            url=url.strip(),
            feature_flags=feature_flags,
            features_count=len([f for f, enabled in feature_flags.items() if enabled])
        )
        
        return {
            "url": url.strip(),
            "feature_flags": feature_flags
        }
    
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in request body", json_error=str(e))
        raise HandlerError(f"Invalid JSON in request body: {str(e)}", "VALIDATION_ERROR", 400)
    except HandlerError:
        raise
    except Exception as e:
        logger.error("Failed to parse request", error=e)
        raise HandlerError(f"Failed to parse request: {str(e)}", "VALIDATION_ERROR", 400)


def parse_feature_flags(features: Dict[str, Any]) -> Dict[str, bool]:
    """
    Parse and validate feature flags from request.
    
    Args:
        features: Raw features dictionary from request
        
    Returns:
        Dictionary of validated boolean feature flags
        
    Raises:
        HandlerError: If feature flag combination is invalid
    """
    # Default feature flags
    default_flags = {
        "llm_normalization": False,
        "sentiment": False,
        "pii": False,
        "topics": False,
        "summary": False,
        "external_api": False
    }
    
    # Parse provided flags
    parsed_flags = {}
    for key, default_value in default_flags.items():
        value = features.get(key, default_value)
        
        # Convert to boolean
        if isinstance(value, bool):
            parsed_flags[key] = value
        elif isinstance(value, str):
            parsed_flags[key] = value.lower() in ("true", "1", "yes", "on")
        elif isinstance(value, (int, float)):
            parsed_flags[key] = bool(value)
        else:
            parsed_flags[key] = default_value
    
    logger.debug(
        "Feature flags parsed",
        raw_features=features,
        parsed_flags=parsed_flags,
        enabled_features=[f for f, enabled in parsed_flags.items() if enabled]
    )
    
    # Validate feature flag combinations
    validate_feature_flags(parsed_flags)
    
    return parsed_flags


def validate_feature_flags(feature_flags: Dict[str, bool]) -> None:
    """
    Validate feature flag combinations.
    
    Args:
        feature_flags: Dictionary of feature flags to validate
        
    Raises:
        HandlerError: If feature flag combination is invalid
    """
    # Check for valid combinations
    aws_features = ["llm_normalization", "sentiment", "pii", "topics", "summary"]
    aws_enabled = any(feature_flags.get(f, False) for f in aws_features)
    
    # If no features are enabled, that's valid (basic scraping only)
    if not any(feature_flags.values()):
        logger.info("No processing features enabled - basic scraping only")
        return
    
    # Validate individual features
    for feature, enabled in feature_flags.items():
        if not isinstance(enabled, bool):
            logger.error(f"Invalid feature flag type", feature=feature, value=enabled, value_type=type(enabled).__name__)
            raise HandlerError(f"Feature flag '{feature}' must be boolean", "VALIDATION_ERROR", 400)
    
    # Log enabled features
    enabled_features = [f for f, enabled in feature_flags.items() if enabled]
    logger.info(
        "Feature flags validated successfully",
        enabled_features=enabled_features,
        aws_features_enabled=aws_enabled,
        total_features=len(enabled_features)
    )


def execute_processing_pipeline(
    url: str,
    feature_flags: Dict[str, bool],
    scraper: NewsScraper,
    normalizer: Optional[LLMNormalizer],
    enricher: Optional[NLPEnricher],
    formatter: ResultFormatter
) -> Dict[str, Any]:
    """
    Execute the complete processing pipeline based on feature flags.
    
    Implements graceful degradation - continues processing when non-critical
    features fail, returning partial results rather than complete failure.
    
    Args:
        url: News article URL to process
        feature_flags: Dictionary of enabled features
        scraper: News scraper instance
        normalizer: Optional LLM normalizer instance
        enricher: Optional NLP enricher instance
        formatter: Result formatter instance
        
    Returns:
        Dictionary with processing results or error information
    """
    processing_errors = []
    partial_results = {}
    
    # Set processing step context
    logger.set_context(processing_step="pipeline")
    
    try:
        # Step 1: Scrape article (critical step - failure stops processing)
        logger.set_context(processing_step="scraping")
        logger.info("Starting article scraping")
        
        with logger.timed_operation("scrape_article"):
            scraped_content = scraper.scrape_article(url)
        
        if not scraped_content.success:
            logger.error(
                "Article scraping failed",
                error_message=scraped_content.error_message,
                url=url
            )
            return {
                "success": False,
                "error_response": create_error_response(
                    url=url,
                    error_message=scraped_content.error_message or "Scraping failed",
                    error_type="SCRAPING_ERROR",
                    processing_step="scraping"
                ),
                "status_code": 400
            }
        
        logger.info(
            "Scraping completed successfully",
            content_length=len(scraped_content.clean_content),
            title=scraped_content.title,
            word_count=scraped_content.word_count,
            extraction_method=scraped_content.extraction_method
        )
        
        partial_results["scraping"] = {
            "success": True,
            "content_length": len(scraped_content.clean_content),
            "title": scraped_content.title,
            "word_count": scraped_content.word_count,
            "extraction_method": scraped_content.extraction_method
        }
        
        # Step 2: Optional LLM normalization (non-critical - continue on failure)
        normalized_content = None
        if feature_flags.get("llm_normalization", False) and normalizer:
            logger.set_context(processing_step="llm_normalization")
            try:
                logger.info("Starting LLM normalization")
                
                with logger.timed_operation("llm_normalization") as timing:
                    normalization_result = normalizer.normalize_text(scraped_content.clean_content)
                    normalized_content = normalization_result.normalized_text
                
                logger.info(
                    "LLM normalization completed successfully",
                    original_length=len(scraped_content.clean_content),
                    normalized_length=len(normalized_content),
                    compression_ratio=normalization_result.compression_ratio,
                    model_used=normalization_result.model_used
                )
                
                partial_results["llm_normalization"] = {
                    "success": True,
                    "compression_ratio": normalization_result.compression_ratio,
                    "processing_time_ms": normalization_result.processing_time_ms,
                    "model_used": normalization_result.model_used
                }
                
            except Exception as e:
                error_msg = f"LLM normalization failed: {str(e)}"
                logger.warning("LLM normalization failed", error=e)
                processing_errors.append(error_msg)
                partial_results["llm_normalization"] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                # Continue with original content
        
        # Step 3: Optional NLP enrichment (non-critical - continue on failure)
        enrichment_results = None
        if enricher and any(feature_flags.get(f, False) for f in ["sentiment", "pii", "topics", "summary"]):
            logger.set_context(processing_step="nlp_enrichment")
            try:
                logger.info("Starting NLP enrichment")
                enrichment_features = {
                    "sentiment": feature_flags.get("sentiment", False),
                    "pii": feature_flags.get("pii", False),
                    "topics": feature_flags.get("topics", False),
                    "summary": feature_flags.get("summary", False)
                }
                
                logger.info(
                    "NLP enrichment features enabled",
                    features=enrichment_features
                )
                
                # Use normalized content if available, otherwise use clean content
                content_to_enrich = normalized_content or scraped_content.clean_content
                
                with logger.timed_operation("nlp_enrichment"):
                    enrichment_results = enricher.enrich_content(content_to_enrich, enrichment_features)
                
                logger.info(
                    "NLP enrichment completed successfully",
                    features_processed=enrichment_results.features_processed,
                    processing_time_ms=enrichment_results.processing_time_ms,
                    content_length=len(content_to_enrich)
                )
                
                partial_results["nlp_enrichment"] = {
                    "success": True,
                    "features_processed": enrichment_results.features_processed,
                    "processing_time_ms": enrichment_results.processing_time_ms
                }
                
                # Track individual feature failures
                requested_features = [f for f, enabled in enrichment_features.items() if enabled]
                failed_features = set(requested_features) - set(enrichment_results.features_processed)
                if failed_features:
                    error_msg = f"Some NLP features failed: {list(failed_features)}"
                    logger.warning(
                        "Some NLP features failed",
                        failed_features=list(failed_features),
                        successful_features=enrichment_results.features_processed
                    )
                    processing_errors.append(error_msg)
                    partial_results["nlp_enrichment"]["failed_features"] = list(failed_features)
                
            except Exception as e:
                error_msg = f"NLP enrichment failed: {str(e)}"
                logger.warning("NLP enrichment failed", error=e)
                processing_errors.append(error_msg)
                partial_results["nlp_enrichment"] = {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                # Continue without enrichment
        
        # Step 4: Format response (critical step - but handle gracefully)
        logger.set_context(processing_step="formatting")
        logger.info("Formatting response")
        
        try:
            # Create extracted content object for formatter
            from .scraper.extractor import ExtractedContent
            extracted_content = ExtractedContent(
                clean_text=scraped_content.clean_content,
                word_count=scraped_content.word_count,
                paragraph_count=scraped_content.paragraph_count,
                extraction_method=scraped_content.extraction_method,
                confidence_score=scraped_content.confidence_score,
                removed_elements=scraped_content.removed_elements or [],
                error_details=None
            )
            
            with logger.timed_operation("format_response"):
                formatted_response = formatter.format_response(
                    url=url,
                    extracted_content=extracted_content,
                    enrichment_results=enrichment_results,
                    normalized_content=normalized_content,
                    features_enabled=feature_flags,
                    processing_time_ms=0,  # Will be updated by caller
                    title=scraped_content.title,
                    author=scraped_content.author,
                    publish_date=scraped_content.publish_date.isoformat() if scraped_content.publish_date else None
                )
            
            # Add processing errors to metadata if any occurred
            if processing_errors and hasattr(formatted_response, 'processing_metadata'):
                if formatted_response.processing_metadata:
                    formatted_response.processing_metadata.errors_encountered.extend(processing_errors)
            
            logger.info(
                "Processing pipeline completed successfully",
                partial_failures=len(processing_errors) > 0,
                processing_errors_count=len(processing_errors)
            )
            
            return {
                "success": True,
                "response": formatted_response,
                "partial_failures": len(processing_errors) > 0,
                "processing_errors": processing_errors
            }
            
        except Exception as e:
            # If formatting fails, return a minimal response
            logger.error("Response formatting failed", error=e)
            processing_errors.append(f"Response formatting failed: {str(e)}")
            
            # Create minimal response manually
            minimal_response = {
                "success": True,
                "article_metadata": {
                    "url": url,
                    "title": scraped_content.title,
                    "scrape_timestamp": datetime.utcnow().isoformat() + "Z"
                },
                "extracted_content": scraped_content.clean_content,
                "normalized_content": normalized_content,
                "processing_errors": processing_errors,
                "partial_results": partial_results,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            logger.info(
                "Minimal response created due to formatting failure",
                response_type="minimal",
                processing_errors_count=len(processing_errors)
            )
            
            return {
                "success": True,
                "response": minimal_response,
                "partial_failures": True,
                "processing_errors": processing_errors
            }
    
    except Exception as e:
        logger.error("Processing pipeline failed", error=e, partial_results=partial_results)
        
        # Include any partial results in error response
        error_response = create_error_response(
            url=url,
            error_message=str(e),
            error_type="PROCESSING_ERROR",
            processing_step="pipeline",
            partial_results=partial_results
        )
        
        # Add processing errors to error response
        if processing_errors:
            error_response["processing_errors"] = processing_errors
        
        return {
            "success": False,
            "error_response": error_response,
            "status_code": 500
        }


def create_error_response(
    url: str,
    error_message: str,
    error_type: str = "PROCESSING_ERROR",
    processing_step: Optional[str] = None,
    partial_results: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create structured error response with comprehensive error information.
    
    Args:
        url: Original article URL
        error_message: Error description
        error_type: Type of error
        processing_step: Step where error occurred
        partial_results: Any partial results available
        
    Returns:
        Structured error response dictionary
    """
    error_response = {
        "success": False,
        "error": {
            "type": error_type,
            "message": error_message,
            "step": processing_step,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "recoverable": _is_recoverable_error(error_type),
            "retry_recommended": _should_retry_error(error_type)
        },
        "article_metadata": {
            "url": url,
            "scrape_timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "partial_results": partial_results or {},
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Add troubleshooting hints based on error type
    troubleshooting_hints = _get_troubleshooting_hints(error_type, processing_step)
    if troubleshooting_hints:
        error_response["error"]["troubleshooting_hints"] = troubleshooting_hints
    
    return error_response


def _is_recoverable_error(error_type: str) -> bool:
    """Determine if an error type is potentially recoverable."""
    recoverable_errors = {
        "TIMEOUT_ERROR",
        "CONNECTION_ERROR", 
        "HTTP_ERROR",
        "AWS_SERVICE_ERROR",
        "EXTERNAL_API_ERROR"
    }
    return error_type in recoverable_errors


def _should_retry_error(error_type: str) -> bool:
    """Determine if an error type should be retried."""
    retryable_errors = {
        "TIMEOUT_ERROR",
        "CONNECTION_ERROR",
        "AWS_SERVICE_ERROR"
    }
    return error_type in retryable_errors


def _get_troubleshooting_hints(error_type: str, processing_step: Optional[str]) -> List[str]:
    """Get troubleshooting hints based on error type and processing step."""
    hints = []
    
    if error_type == "VALIDATION_ERROR":
        hints.extend([
            "Check that the URL is valid and accessible",
            "Ensure feature flags are boolean values",
            "Verify request body contains required fields"
        ])
    elif error_type == "SCRAPING_ERROR":
        hints.extend([
            "Verify the URL is accessible and returns HTML content",
            "Check if the website blocks automated requests",
            "Try again later if the site is temporarily unavailable"
        ])
    elif error_type == "AWS_SERVICE_ERROR":
        hints.extend([
            "Check AWS credentials and permissions",
            "Verify AWS service availability in your region",
            "Check if you've exceeded service quotas or rate limits"
        ])
    elif error_type == "TIMEOUT_ERROR":
        hints.extend([
            "The request took longer than expected to complete",
            "Try again with a shorter article or fewer features enabled",
            "Check network connectivity to external services"
        ])
    elif error_type == "CONFIGURATION_ERROR":
        hints.extend([
            "Check environment variables are properly set",
            "Verify configuration files are valid and accessible",
            "Ensure AWS region and service endpoints are correct"
        ])
    elif error_type == "EXTERNAL_API_ERROR":
        hints.extend([
            "Check external API endpoint configuration",
            "Verify authentication credentials",
            "Check if external API is available and accepting requests"
        ])
    
    # Add step-specific hints
    if processing_step == "scraping":
        hints.append("Consider checking if the website has changed its structure")
    elif processing_step == "llm_normalization":
        hints.append("Try processing without LLM normalization enabled")
    elif processing_step == "nlp_enrichment":
        hints.append("Try processing with fewer NLP features enabled")
    
    return hints


def create_api_response(status_code: int, body: Any) -> Dict[str, Any]:
    """
    Create API Gateway response format.
    
    Args:
        status_code: HTTP status code
        body: Response body (will be JSON serialized)
        
    Returns:
        API Gateway response format
    """
    # Convert dataclass to dict if needed
    if hasattr(body, '__dataclass_fields__'):
        from dataclasses import asdict
        body = asdict(body)
    
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "POST,OPTIONS"
        },
        "body": json.dumps(body, default=str, ensure_ascii=False)
    }