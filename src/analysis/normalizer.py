"""
LLM-based text normalization using AWS Bedrock.

This module provides text normalization capabilities using AWS Bedrock's
Anthropic Claude 3 Haiku model for advanced text cleanup and processing.
"""

import json
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from ..config.models import AWSSettings
from .error_handler import (
    RetryConfig, BedrockError, BedrockTimeoutError,
    BedrockServiceError, classify_bedrock_error
)


logger = logging.getLogger(__name__)


@dataclass
class NormalizedContent:
    """Result of LLM text normalization."""
    
    normalized_text: str
    original_length: int
    normalized_length: int
    processing_time_ms: int
    model_used: str
    confidence_score: Optional[float] = None
    
    @property
    def compression_ratio(self) -> float:
        """Calculate text compression ratio."""
        if self.original_length == 0:
            return 0.0
        return self.normalized_length / self.original_length


class LLMNormalizer:
    """
    LLM-based text normalizer using AWS Bedrock.
    
    Uses Anthropic Claude 3 Haiku model for cost-efficient text cleanup,
    removing boilerplate content while preserving article meaning.
    """
    
    def __init__(self, aws_settings: AWSSettings):
        """
        Initialize the LLM normalizer.
        
        Args:
            aws_settings: AWS configuration settings
        """
        self.aws_settings = aws_settings
        self._bedrock_client = None
        self.retry_config = RetryConfig(
            max_retries=aws_settings.max_retries,
            base_delay=1.0,
            max_delay=30.0
        )
        
    @property
    def bedrock_client(self):
        """Lazy initialization of Bedrock client with timeout configuration."""
        if self._bedrock_client is None:
            # Configure client with timeout settings
            config = Config(
                region_name=self.aws_settings.region,
                retries={'max_attempts': 0},  # We handle retries manually
                read_timeout=self.aws_settings.timeout_seconds,
                connect_timeout=10
            )
            
            self._bedrock_client = boto3.client(
                'bedrock-runtime',
                config=config
            )
        return self._bedrock_client
    
    def normalize_text(self, text: str) -> NormalizedContent:
        """
        Clean and normalize text using Claude 3 Haiku with error handling.
        
        Args:
            text: Raw text content to normalize
            
        Returns:
            NormalizedContent with cleaned text and metadata
            
        Raises:
            ValueError: If text is empty or too long
            BedrockError: If Bedrock API call fails after retries
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
            
        if len(text) > 100000:  # 100KB limit for cost efficiency
            raise ValueError("Text too long for normalization")
            
        start_time = datetime.now()
        
        try:
            prompt = self.build_prompt(text)
            response = self._invoke_bedrock_with_retry(prompt)
            normalized_text = self._extract_normalized_text(response)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Text normalization completed: {len(text)} -> {len(normalized_text)} chars")
            
            return NormalizedContent(
                normalized_text=normalized_text,
                original_length=len(text),
                normalized_length=len(normalized_text),
                processing_time_ms=int(processing_time),
                model_used=self.aws_settings.bedrock_model_id
            )
            
        except BedrockError:
            # Re-raise Bedrock errors as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error during text normalization: {str(e)}")
            # Classify and wrap unexpected errors
            classified_error = classify_bedrock_error(e)
            raise classified_error
    
    def build_prompt(self, text: str) -> str:
        """
        Build normalization prompt for LLM.
        
        Args:
            text: Text content to normalize
            
        Returns:
            Formatted prompt for Claude 3 Haiku
        """
        prompt = f"""Human: Please clean and normalize the following news article text. Remove any remaining navigation elements, advertisements, duplicate content, and non-article text while preserving the core article meaning and readability.

Guidelines:
- Keep the main article content and preserve paragraph structure
- Remove navigation menus, ads, social media widgets, and boilerplate
- Fix any formatting issues or encoding problems
- Maintain the original tone and meaning
- Return only the cleaned article text without additional commentary

Article text:
{text}
Assistant: """
        return prompt.strip()
    
    def _invoke_bedrock_with_retry(self, prompt: str) -> Dict[str, Any]:
        """
        Invoke Bedrock API with retry logic and error handling.
        
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
                    logger.error(f"Max retries ({self.retry_config.max_retries}) exceeded for Bedrock call")
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
                    f"Bedrock attempt {attempt + 1}/{self.retry_config.max_retries + 1} failed: "
                    f"{classified_error}. Retrying in {delay:.2f}s"
                )
                
                time.sleep(delay)
        
        # This should never be reached
        raise last_error or BedrockServiceError("Unknown retry error")
    
    def _invoke_bedrock(self, prompt: str) -> Dict[str, Any]:
        """
        Invoke Bedrock API with the given prompt.
        
        Args:
            prompt: Formatted prompt for the model
            
        Returns:
            Raw response from Bedrock API
            
        Raises:
            ClientError: If API call fails
        """
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.aws_settings.bedrock_max_tokens,
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
            logger.debug(f"Bedrock response received: {len(str(response_body))} chars")
            
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
    
    def _extract_normalized_text(self, response: Dict[str, Any]) -> str:
        """
        Extract normalized text from Bedrock response.
        
        Args:
            response: Raw Bedrock API response
            
        Returns:
            Cleaned and normalized text
            
        Raises:
            ValueError: If response format is invalid
        """
        try:
            # Extract text from Claude 3 response format
            if 'content' in response and response['content']:
                content = response['content'][0]
                if 'text' in content:
                    normalized_text = content['text'].strip()
                    
                    if not normalized_text:
                        raise ValueError("Bedrock returned empty normalized text")
                        
                    return normalized_text
            
            raise ValueError("Invalid Bedrock response format")
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Failed to parse Bedrock response: {str(e)}")
            raise ValueError(f"Invalid Bedrock response structure: {str(e)}")