"""
NLP enrichment using AWS Comprehend and Bedrock services.

This module provides comprehensive NLP analysis capabilities including
sentiment analysis, PII detection, topic extraction, and text summarization.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from ..config.models import AWSSettings
from ..config.logging import get_logger
from ..config.timeouts import get_timeout_manager
from .error_handler import (
    RetryConfig, BedrockError, BedrockServiceError,
    classify_bedrock_error
)


logger = get_logger(__name__)


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    
    sentiment: str  # POSITIVE, NEGATIVE, NEUTRAL, MIXED
    confidence_scores: Dict[str, float]
    
    @property
    def dominant_sentiment_confidence(self) -> float:
        """Get confidence score for the dominant sentiment."""
        return self.confidence_scores.get(self.sentiment, 0.0)


@dataclass
class PIIEntity:
    """Individual PII entity detected in text."""
    
    type: str
    text: str
    confidence: float
    begin_offset: int
    end_offset: int


@dataclass
class PIIResult:
    """Result of PII detection analysis."""
    
    entities: List[PIIEntity]
    redacted_text: Optional[str] = None
    
    @property
    def has_pii(self) -> bool:
        """Check if any PII entities were detected."""
        return len(self.entities) > 0
    
    @property
    def pii_types(self) -> List[str]:
        """Get unique PII types detected."""
        return list(set(entity.type for entity in self.entities))


@dataclass
class KeyPhrase:
    """Key phrase extracted from text."""
    
    text: str
    confidence: float
    begin_offset: int
    end_offset: int


@dataclass
class TopicResult:
    """Result of topic and key phrase extraction."""
    
    key_phrases: List[KeyPhrase]
    topics: List[str]  # Derived from key phrases
    
    @property
    def top_phrases(self) -> List[KeyPhrase]:
        """Get top key phrases sorted by confidence."""
        return sorted(self.key_phrases, key=lambda x: x.confidence, reverse=True)[:10]


@dataclass
class SummaryResult:
    """Result of text summarization."""
    
    summary: str
    original_length: int
    summary_length: int
    processing_time_ms: int
    model_used: str
    
    @property
    def compression_ratio(self) -> float:
        """Calculate text compression ratio."""
        if self.original_length == 0:
            return 0.0
        return self.summary_length / self.original_length


@dataclass
class EnrichmentResults:
    """Combined results from all NLP enrichment features."""
    
    sentiment: Optional[SentimentResult] = None
    pii_detection: Optional[PIIResult] = None
    topics: Optional[TopicResult] = None
    summary: Optional[SummaryResult] = None
    processing_time_ms: int = 0
    features_processed: List[str] = None
    
    def __post_init__(self):
        if self.features_processed is None:
            self.features_processed = []


class NLPEnricher:
    """
    NLP enricher using AWS Comprehend and Bedrock services.
    
    Provides sentiment analysis, PII detection, topic extraction,
    and text summarization capabilities with error handling and retry logic.
    """
    
    def __init__(self, aws_settings: AWSSettings):
        """
        Initialize the NLP enricher.
        
        Args:
            aws_settings: AWS configuration settings
        """
        self.aws_settings = aws_settings
        self.timeout_manager = get_timeout_manager()
        self._comprehend_client = None
        self._bedrock_client = None
        self.retry_config = RetryConfig(
            max_retries=aws_settings.max_retries,
            base_delay=1.0,
            max_delay=30.0
        )
    
    @property
    def comprehend_client(self):
        """Lazy initialization of Comprehend client."""
        if self._comprehend_client is None:
            # Get timeout configuration for Comprehend service
            timeout_config = self.timeout_manager.get_aws_timeout("comprehend")
            
            config = Config(
                region_name=self.aws_settings.region,
                retries={'max_attempts': 0},  # We handle retries manually
                read_timeout=timeout_config['read_timeout'],
                connect_timeout=timeout_config['connect_timeout']
            )
            
            self._comprehend_client = boto3.client(
                'comprehend',
                config=config
            )
        return self._comprehend_client
    
    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client."""
        if self._bedrock_client is None:
            # Get timeout configuration for Bedrock service
            timeout_config = self.timeout_manager.get_aws_timeout("bedrock")
            
            config = Config(
                region_name=self.aws_settings.region,
                retries={'max_attempts': 0},  # We handle retries manually
                read_timeout=timeout_config['read_timeout'],
                connect_timeout=timeout_config['connect_timeout']
            )
            
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                config=config
            )
        return self._bedrock_client
    
    def analyze_sentiment(self, text: str) -> SentimentResult:
        """
        Analyze text sentiment using AWS Comprehend.
        
        Args:
            text: Text content to analyze
            
        Returns:
            SentimentResult with sentiment and confidence scores
            
        Raises:
            ValueError: If text is empty or too long
            BedrockServiceError: If Comprehend API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        logger.set_context(component="nlp_enricher", processing_step="sentiment_analysis")
        
        # Truncate text if it exceeds Comprehend limits
        original_length = len(text)
        text = self._truncate_text_for_comprehend(text)
        
        if len(text) != original_length:
            logger.info(
                "Text truncated for Comprehend",
                original_length=original_length,
                truncated_length=len(text),
                max_bytes=self.aws_settings.comprehend_max_bytes
            )
        
        try:
            start_time = time.time()
            
            response = self._call_comprehend_with_retry(
                'detect_sentiment',
                Text=text,
                LanguageCode=self.aws_settings.comprehend_language_code
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            sentiment = response['Sentiment']
            confidence_scores = response['SentimentScore']
            
            # Convert confidence scores to more readable format
            scores = {
                'POSITIVE': confidence_scores['Positive'],
                'NEGATIVE': confidence_scores['Negative'],
                'NEUTRAL': confidence_scores['Neutral'],
                'MIXED': confidence_scores['Mixed']
            }
            
            logger.log_aws_service_call(
                service="comprehend",
                operation="detect_sentiment",
                duration_ms=duration_ms,
                success=True,
                text_length=len(text),
                result_sentiment=sentiment,
                confidence=scores[sentiment]
            )
            
            logger.info(
                "Sentiment analysis completed successfully",
                sentiment=sentiment,
                confidence=scores[sentiment],
                text_length=len(text),
                processing_time_ms=duration_ms
            )
            
            return SentimentResult(
                sentiment=sentiment,
                confidence_scores=scores
            )
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
            
            logger.log_aws_service_call(
                service="comprehend",
                operation="detect_sentiment",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
                text_length=len(text)
            )
            
            logger.error("Sentiment analysis failed", error=e, text_length=len(text))
            classified_error = classify_bedrock_error(e)
            raise classified_error
    
    def detect_pii(self, text: str) -> PIIResult:
        """
        Detect PII entities in text using AWS Comprehend.
        
        Args:
            text: Text content to analyze
            
        Returns:
            PIIResult with detected PII entities
            
        Raises:
            ValueError: If text is empty or too long
            BedrockServiceError: If Comprehend API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Truncate text if it exceeds Comprehend limits
        text = self._truncate_text_for_comprehend(text)
        
        try:
            response = self._call_comprehend_with_retry(
                'detect_pii_entities',
                Text=text,
                LanguageCode=self.aws_settings.comprehend_language_code
            )
            
            entities = []
            for entity_data in response['Entities']:
                entity = PIIEntity(
                    type=entity_data['Type'],
                    text=text[entity_data['BeginOffset']:entity_data['EndOffset']],
                    confidence=entity_data['Score'],
                    begin_offset=entity_data['BeginOffset'],
                    end_offset=entity_data['EndOffset']
                )
                entities.append(entity)
            
            logger.info(f"PII detection completed: {len(entities)} entities found")
            
            return PIIResult(entities=entities)
            
        except Exception as e:
            logger.error(f"PII detection failed: {str(e)}")
            classified_error = classify_bedrock_error(e)
            raise classified_error
    
    def extract_topics(self, text: str) -> TopicResult:
        """
        Extract key phrases and topics from text using AWS Comprehend.
        
        Args:
            text: Text content to analyze
            
        Returns:
            TopicResult with key phrases and derived topics
            
        Raises:
            ValueError: If text is empty or too long
            BedrockServiceError: If Comprehend API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        # Truncate text if it exceeds Comprehend limits
        text = self._truncate_text_for_comprehend(text)
        
        try:
            response = self._call_comprehend_with_retry(
                'detect_key_phrases',
                Text=text,
                LanguageCode=self.aws_settings.comprehend_language_code
            )
            
            key_phrases = []
            for phrase_data in response['KeyPhrases']:
                phrase = KeyPhrase(
                    text=phrase_data['Text'],
                    confidence=phrase_data['Score'],
                    begin_offset=phrase_data['BeginOffset'],
                    end_offset=phrase_data['EndOffset']
                )
                key_phrases.append(phrase)
            
            # Derive topics from high-confidence key phrases
            topics = self._derive_topics_from_phrases(key_phrases)
            
            logger.info(f"Topic extraction completed: {len(key_phrases)} phrases, {len(topics)} topics")
            
            return TopicResult(
                key_phrases=key_phrases,
                topics=topics
            )
            
        except Exception as e:
            logger.error(f"Topic extraction failed: {str(e)}")
            classified_error = classify_bedrock_error(e)
            raise classified_error
    
    def summarize_content(self, text: str) -> SummaryResult:
        """
        Generate article summary using AWS Bedrock.
        
        Args:
            text: Text content to summarize
            
        Returns:
            SummaryResult with generated summary
            
        Raises:
            ValueError: If text is empty or too long
            BedrockError: If Bedrock API call fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        if len(text) > 100000:  # 100KB limit for cost efficiency
            raise ValueError("Text too long for summarization")
        
        start_time = datetime.now()
        
        try:
            prompt = self._build_summarization_prompt(text)
            response = self._invoke_bedrock_with_retry(prompt)
            summary = self._extract_summary_from_response(response)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Text summarization completed: {len(text)} -> {len(summary)} chars")
            
            return SummaryResult(
                summary=summary,
                original_length=len(text),
                summary_length=len(summary),
                processing_time_ms=int(processing_time),
                model_used=self.aws_settings.bedrock_model_id
            )
            
        except BedrockError:
            # Re-raise Bedrock errors as-is
            raise
        except Exception as e:
            logger.error(f"Text summarization failed: {str(e)}")
            classified_error = classify_bedrock_error(e)
            raise classified_error
    
    def enrich_content(self, text: str, features: Dict[str, bool]) -> EnrichmentResults:
        """
        Perform comprehensive NLP enrichment based on enabled features.
        
        Implements batch processing for multiple enrichment features,
        combining results from AWS Comprehend and Bedrock services efficiently.
        
        Args:
            text: Text content to enrich
            features: Dictionary of feature flags (sentiment, pii, topics, summary)
            
        Returns:
            EnrichmentResults with all requested analysis results
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        start_time = datetime.now()
        results = EnrichmentResults()
        
        # Optimize processing order: Comprehend operations first (faster), then Bedrock
        comprehend_features = ['sentiment', 'pii', 'topics']
        bedrock_features = ['summary']
        
        # Process Comprehend features in batch
        for feature in comprehend_features:
            if features.get(feature, False):
                try:
                    if feature == 'sentiment':
                        results.sentiment = self.analyze_sentiment(text)
                    elif feature == 'pii':
                        results.pii_detection = self.detect_pii(text)
                    elif feature == 'topics':
                        results.topics = self.extract_topics(text)
                    
                    results.features_processed.append(feature)
                    logger.debug(f"{feature.title()} analysis completed successfully")
                    
                except Exception as e:
                    logger.warning(f"{feature.title()} analysis failed: {str(e)}")
                    # Continue processing other features on failure
        
        # Process Bedrock features
        for feature in bedrock_features:
            if features.get(feature, False):
                try:
                    if feature == 'summary':
                        results.summary = self.summarize_content(text)
                    
                    results.features_processed.append(feature)
                    logger.debug(f"{feature.title()} analysis completed successfully")
                    
                except Exception as e:
                    logger.warning(f"{feature.title()} analysis failed: {str(e)}")
                    # Continue processing other features on failure
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        results.processing_time_ms = int(processing_time)
        
        logger.info(
            f"NLP enrichment completed: {len(results.features_processed)}/{sum(features.values())} "
            f"features processed successfully in {processing_time:.0f}ms"
        )
        
        return results
    
    def enrich_multiple_contents(self, texts: List[str], features: Dict[str, bool]) -> List[EnrichmentResults]:
        """
        Perform NLP enrichment on multiple texts efficiently.
        
        Optimizes batch processing by grouping similar operations together
        and handling partial failures gracefully.
        
        Args:
            texts: List of text contents to enrich
            features: Dictionary of feature flags (sentiment, pii, topics, summary)
            
        Returns:
            List of EnrichmentResults for each input text
        """
        if not texts:
            return []
        
        results = []
        start_time = datetime.now()
        
        logger.info(f"Starting batch enrichment for {len(texts)} texts with features: {list(features.keys())}")
        
        for i, text in enumerate(texts):
            try:
                result = self.enrich_content(text, features)
                results.append(result)
                logger.debug(f"Batch item {i+1}/{len(texts)} processed successfully")
                
            except Exception as e:
                logger.warning(f"Batch item {i+1}/{len(texts)} failed: {str(e)}")
                # Add empty result for failed processing
                results.append(EnrichmentResults())
        
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        successful_count = sum(1 for r in results if r.features_processed)
        
        logger.info(
            f"Batch enrichment completed: {successful_count}/{len(texts)} texts processed "
            f"successfully in {total_time:.0f}ms"
        )
        
        return results
    
    def _truncate_text_for_comprehend(self, text: str) -> str:
        """
        Truncate text to fit within Comprehend byte limits.
        
        Args:
            text: Original text
            
        Returns:
            Truncated text that fits within limits
        """
        # Comprehend has a 5000 byte limit for most operations
        text_bytes = text.encode('utf-8')
        if len(text_bytes) <= self.aws_settings.comprehend_max_bytes:
            return text
        
        # Truncate to fit within byte limit, ensuring we don't break UTF-8
        truncated_bytes = text_bytes[:self.aws_settings.comprehend_max_bytes]
        try:
            return truncated_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # If we broke a UTF-8 sequence, try truncating a bit more
            for i in range(1, 5):  # UTF-8 sequences are max 4 bytes
                try:
                    return truncated_bytes[:-i].decode('utf-8')
                except UnicodeDecodeError:
                    continue
            
            # Fallback: truncate by characters instead
            return text[:len(text) // 2]
    
    def _call_comprehend_with_retry(self, method_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call Comprehend API method with retry logic.
        
        Args:
            method_name: Name of the Comprehend method to call
            **kwargs: Arguments to pass to the method
            
        Returns:
            Response from Comprehend API
            
        Raises:
            BedrockServiceError: If API call fails after retries
        """
        last_error = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                method = getattr(self.comprehend_client, method_name)
                return method(**kwargs)
                
            except Exception as e:
                classified_error = classify_bedrock_error(e)
                last_error = classified_error
                
                if attempt == self.retry_config.max_retries:
                    logger.error(f"Max retries ({self.retry_config.max_retries}) exceeded for {method_name}")
                    raise classified_error
                
                if not classified_error.retryable:
                    logger.error(f"Non-retryable error in {method_name}: {classified_error}")
                    raise classified_error
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
                    self.retry_config.max_delay
                )
                
                logger.warning(
                    f"Comprehend {method_name} attempt {attempt + 1}/{self.retry_config.max_retries + 1} failed: "
                    f"{classified_error}. Retrying in {delay:.2f}s"
                )
                
                time.sleep(delay)
        
        raise last_error or BedrockServiceError("Unknown retry error")
    
    def _derive_topics_from_phrases(self, key_phrases: List[KeyPhrase]) -> List[str]:
        """
        Derive topic labels from key phrases.
        
        Args:
            key_phrases: List of extracted key phrases
            
        Returns:
            List of derived topic strings
        """
        # Filter high-confidence phrases (>0.8) and extract meaningful topics
        high_confidence_phrases = [
            phrase for phrase in key_phrases 
            if phrase.confidence > 0.8 and len(phrase.text.split()) <= 3
        ]
        
        # Sort by confidence and take top phrases as topics
        topics = [
            phrase.text.title() 
            for phrase in sorted(high_confidence_phrases, key=lambda x: x.confidence, reverse=True)[:5]
        ]
        
        return topics
    
    def _build_summarization_prompt(self, text: str) -> str:
        """
        Build summarization prompt for Bedrock.
        
        Args:
            text: Text content to summarize
            
        Returns:
            Formatted prompt for Claude 3 Haiku
        """
        prompt = f"""Human: Please provide a concise summary of the following news article. Focus on the key facts, main points, and important details while keeping the summary to 2-3 sentences.

Article:
{text}
Assistant: """
        return prompt.strip()
    
    def _invoke_bedrock_with_retry(self, prompt: str) -> Dict[str, Any]:
        """
        Invoke Bedrock API with retry logic for summarization.
        
        Args:
            prompt: Formatted prompt for the model
            
        Returns:
            Raw response from Bedrock API
            
        Raises:
            BedrockError: If API call fails after retries
        """
        last_error = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                return self._invoke_bedrock(prompt)
                
            except Exception as e:
                classified_error = classify_bedrock_error(e)
                last_error = classified_error
                
                if attempt == self.retry_config.max_retries:
                    logger.error(f"Max retries ({self.retry_config.max_retries}) exceeded for Bedrock summarization")
                    raise classified_error
                
                if not classified_error.retryable:
                    logger.error(f"Non-retryable Bedrock error: {classified_error}")
                    raise classified_error
                
                # Calculate delay with exponential backoff
                delay = min(
                    self.retry_config.base_delay * (self.retry_config.exponential_base ** attempt),
                    self.retry_config.max_delay
                )
                
                logger.warning(
                    f"Bedrock summarization attempt {attempt + 1}/{self.retry_config.max_retries + 1} failed: "
                    f"{classified_error}. Retrying in {delay:.2f}s"
                )
                
                time.sleep(delay)
        
        raise last_error or BedrockServiceError("Unknown retry error")
    
    def _invoke_bedrock(self, prompt: str) -> Dict[str, Any]:
        """
        Invoke Bedrock API for summarization.
        
        Args:
            prompt: Formatted prompt for the model
            
        Returns:
            Raw response from Bedrock API
            
        Raises:
            ClientError: If API call fails
        """
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": min(self.aws_settings.bedrock_max_tokens, 500),  # Limit for summaries
            "temperature": self.aws_settings.bedrock_temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.aws_settings.bedrock_model_id,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            logger.debug(f"Bedrock summarization response received: {len(str(response_body))} chars")
            
            return response_body
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Bedrock API error [{error_code}]: {error_message}")
            raise
        except BotoCoreError as e:
            logger.error(f"Bedrock client error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Bedrock: {str(e)}")
            raise
    
    def _extract_summary_from_response(self, response: Dict[str, Any]) -> str:
        """
        Extract summary text from Bedrock response.
        
        Args:
            response: Raw Bedrock API response
            
        Returns:
            Generated summary text
            
        Raises:
            ValueError: If response format is invalid
        """
        try:
            # Extract text from Claude 3 response format
            if 'content' in response and response['content']:
                content = response['content'][0]
                if 'text' in content:
                    summary = content['text'].strip()
                    
                    if not summary:
                        raise ValueError("Bedrock returned empty summary")
                        
                    return summary
            
            raise ValueError("Invalid Bedrock response format")
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Failed to parse Bedrock response: {str(e)}")
            raise ValueError(f"Invalid Bedrock response structure: {str(e)}")