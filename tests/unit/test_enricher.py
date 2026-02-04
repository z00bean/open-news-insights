"""
Unit tests for NLP enricher functionality.

Tests sentiment analysis, PII detection, topic extraction, and text summarization
using AWS Comprehend and Bedrock services.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.analysis.enricher import (
    NLPEnricher, SentimentResult, PIIResult, PIIEntity, 
    TopicResult, KeyPhrase, SummaryResult, EnrichmentResults
)
from src.config.models import AWSSettings
from src.analysis.error_handler import BedrockServiceError


@pytest.fixture
def aws_settings():
    """Create test AWS settings."""
    return AWSSettings(
        region="us-east-1",
        comprehend_language_code="en",
        max_retries=2,
        timeout_seconds=30,
        comprehend_max_bytes=5000
    )


@pytest.fixture
def enricher(aws_settings):
    """Create NLP enricher instance."""
    return NLPEnricher(aws_settings)


@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return "This is a great news article about technology. John Smith from New York wrote this piece."


class TestNLPEnricher:
    """Test cases for NLP enricher functionality."""
    
    def test_initialization(self, aws_settings):
        """Test enricher initialization."""
        enricher = NLPEnricher(aws_settings)
        assert enricher.aws_settings == aws_settings
        assert enricher._comprehend_client is None
        assert enricher._bedrock_client is None
    
    @patch('boto3.client')
    def test_comprehend_client_lazy_initialization(self, mock_boto3_client, enricher):
        """Test lazy initialization of Comprehend client."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        # First access should create client
        client = enricher.comprehend_client
        assert client == mock_client
        mock_boto3_client.assert_called_once()
        
        # Second access should reuse client
        client2 = enricher.comprehend_client
        assert client2 == mock_client
        assert mock_boto3_client.call_count == 1
    
    @patch('boto3.client')
    def test_bedrock_client_lazy_initialization(self, mock_boto3_client, enricher):
        """Test lazy initialization of Bedrock client."""
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        # First access should create client
        client = enricher.bedrock_client
        assert client == mock_client
        mock_boto3_client.assert_called_once()
        
        # Second access should reuse client
        client2 = enricher.bedrock_client
        assert client2 == mock_client
        assert mock_boto3_client.call_count == 1
    
    def test_analyze_sentiment_empty_text(self, enricher):
        """Test sentiment analysis with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            enricher.analyze_sentiment("")
        
        with pytest.raises(ValueError, match="Text cannot be empty"):
            enricher.analyze_sentiment("   ")
    
    @patch.object(NLPEnricher, '_call_comprehend_with_retry')
    def test_analyze_sentiment_success(self, mock_call, enricher, sample_text):
        """Test successful sentiment analysis."""
        mock_response = {
            'Sentiment': 'POSITIVE',
            'SentimentScore': {
                'Positive': 0.85,
                'Negative': 0.05,
                'Neutral': 0.08,
                'Mixed': 0.02
            }
        }
        mock_call.return_value = mock_response
        
        result = enricher.analyze_sentiment(sample_text)
        
        assert isinstance(result, SentimentResult)
        assert result.sentiment == 'POSITIVE'
        assert result.confidence_scores['POSITIVE'] == 0.85
        assert result.dominant_sentiment_confidence == 0.85
        
        mock_call.assert_called_once_with(
            'detect_sentiment',
            Text=sample_text,
            LanguageCode='en'
        )
    
    def test_detect_pii_empty_text(self, enricher):
        """Test PII detection with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            enricher.detect_pii("")
    
    @patch.object(NLPEnricher, '_call_comprehend_with_retry')
    def test_detect_pii_success(self, mock_call, enricher, sample_text):
        """Test successful PII detection."""
        mock_response = {
            'Entities': [
                {
                    'Type': 'NAME',
                    'Score': 0.95,
                    'BeginOffset': 45,
                    'EndOffset': 55
                }
            ]
        }
        mock_call.return_value = mock_response
        
        result = enricher.detect_pii(sample_text)
        
        assert isinstance(result, PIIResult)
        assert result.has_pii
        assert len(result.entities) == 1
        assert result.pii_types == ['NAME']
        
        entity = result.entities[0]
        assert entity.type == 'NAME'
        assert entity.confidence == 0.95
        assert entity.text == sample_text[45:55]
    
    @patch.object(NLPEnricher, '_call_comprehend_with_retry')
    def test_detect_pii_no_entities(self, mock_call, enricher, sample_text):
        """Test PII detection with no entities found."""
        mock_response = {'Entities': []}
        mock_call.return_value = mock_response
        
        result = enricher.detect_pii(sample_text)
        
        assert isinstance(result, PIIResult)
        assert not result.has_pii
        assert len(result.entities) == 0
        assert result.pii_types == []
    
    def test_extract_topics_empty_text(self, enricher):
        """Test topic extraction with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            enricher.extract_topics("")
    
    @patch.object(NLPEnricher, '_call_comprehend_with_retry')
    def test_extract_topics_success(self, mock_call, enricher, sample_text):
        """Test successful topic extraction."""
        mock_response = {
            'KeyPhrases': [
                {
                    'Text': 'technology',
                    'Score': 0.95,
                    'BeginOffset': 35,
                    'EndOffset': 45
                },
                {
                    'Text': 'news article',
                    'Score': 0.85,
                    'BeginOffset': 20,
                    'EndOffset': 32
                }
            ]
        }
        mock_call.return_value = mock_response
        
        result = enricher.extract_topics(sample_text)
        
        assert isinstance(result, TopicResult)
        assert len(result.key_phrases) == 2
        assert len(result.topics) == 2  # Both phrases have high confidence (>0.8)
        
        top_phrases = result.top_phrases
        assert top_phrases[0].text == 'technology'
        assert top_phrases[0].confidence == 0.95
    
    def test_summarize_content_empty_text(self, enricher):
        """Test summarization with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            enricher.summarize_content("")
    
    def test_summarize_content_too_long(self, enricher):
        """Test summarization with text that's too long."""
        long_text = "x" * 100001  # Exceeds 100KB limit
        with pytest.raises(ValueError, match="Text too long for summarization"):
            enricher.summarize_content(long_text)
    
    @patch.object(NLPEnricher, '_invoke_bedrock_with_retry')
    @patch.object(NLPEnricher, '_build_summarization_prompt')
    @patch.object(NLPEnricher, '_extract_summary_from_response')
    def test_summarize_content_success(self, mock_extract, mock_prompt, mock_invoke, enricher, sample_text):
        """Test successful text summarization."""
        mock_prompt.return_value = "test prompt"
        mock_response = {"content": [{"text": "Test summary"}]}
        mock_invoke.return_value = mock_response
        mock_extract.return_value = "Test summary"
        
        result = enricher.summarize_content(sample_text)
        
        assert isinstance(result, SummaryResult)
        assert result.summary == "Test summary"
        assert result.original_length == len(sample_text)
        assert result.summary_length == len("Test summary")
        assert result.compression_ratio < 1.0
        
        mock_prompt.assert_called_once_with(sample_text)
        mock_invoke.assert_called_once_with("test prompt")
        mock_extract.assert_called_once_with(mock_response)
    
    def test_enrich_content_empty_text(self, enricher):
        """Test content enrichment with empty text."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            enricher.enrich_content("", {'sentiment': True})
    
    @patch.object(NLPEnricher, 'analyze_sentiment')
    @patch.object(NLPEnricher, 'detect_pii')
    @patch.object(NLPEnricher, 'extract_topics')
    @patch.object(NLPEnricher, 'summarize_content')
    def test_enrich_content_all_features(self, mock_summary, mock_topics, mock_pii, mock_sentiment, enricher, sample_text):
        """Test content enrichment with all features enabled."""
        # Mock all feature results
        mock_sentiment.return_value = SentimentResult('POSITIVE', {'POSITIVE': 0.9})
        mock_pii.return_value = PIIResult([])
        mock_topics.return_value = TopicResult([], [])
        mock_summary.return_value = SummaryResult("Summary", 100, 20, 500, "claude")
        
        features = {'sentiment': True, 'pii': True, 'topics': True, 'summary': True}
        result = enricher.enrich_content(sample_text, features)
        
        assert isinstance(result, EnrichmentResults)
        assert result.sentiment is not None
        assert result.pii_detection is not None
        assert result.topics is not None
        assert result.summary is not None
        assert len(result.features_processed) == 4
        assert result.processing_time_ms >= 0  # Processing time can be 0 in mocked tests
        
        # Verify all methods were called
        mock_sentiment.assert_called_once_with(sample_text)
        mock_pii.assert_called_once_with(sample_text)
        mock_topics.assert_called_once_with(sample_text)
        mock_summary.assert_called_once_with(sample_text)
    
    @patch.object(NLPEnricher, 'analyze_sentiment')
    def test_enrich_content_partial_failure(self, mock_sentiment, enricher, sample_text):
        """Test content enrichment with partial feature failure."""
        # Mock sentiment to fail
        mock_sentiment.side_effect = BedrockServiceError("Test error", "TEST_ERROR")
        
        features = {'sentiment': True, 'pii': False}
        result = enricher.enrich_content(sample_text, features)
        
        assert isinstance(result, EnrichmentResults)
        assert result.sentiment is None  # Failed feature
        assert len(result.features_processed) == 0  # No successful features
    
    def test_enrich_multiple_contents_empty_list(self, enricher):
        """Test batch enrichment with empty list."""
        result = enricher.enrich_multiple_contents([], {'sentiment': True})
        assert result == []
    
    @patch.object(NLPEnricher, 'enrich_content')
    def test_enrich_multiple_contents_success(self, mock_enrich, enricher):
        """Test successful batch enrichment."""
        texts = ["Text 1", "Text 2"]
        features = {'sentiment': True}
        
        # Mock successful enrichment
        mock_result = EnrichmentResults()
        mock_result.features_processed = ['sentiment']
        mock_enrich.return_value = mock_result
        
        results = enricher.enrich_multiple_contents(texts, features)
        
        assert len(results) == 2
        assert all(isinstance(r, EnrichmentResults) for r in results)
        assert mock_enrich.call_count == 2
    
    @patch.object(NLPEnricher, 'enrich_content')
    def test_enrich_multiple_contents_partial_failure(self, mock_enrich, enricher):
        """Test batch enrichment with partial failures."""
        texts = ["Text 1", "Text 2"]
        features = {'sentiment': True}
        
        # Mock first success, second failure
        success_result = EnrichmentResults()
        success_result.features_processed = ['sentiment']
        
        mock_enrich.side_effect = [success_result, Exception("Test error")]
        
        results = enricher.enrich_multiple_contents(texts, features)
        
        assert len(results) == 2
        assert results[0].features_processed == ['sentiment']  # Success
        assert results[1].features_processed == []  # Failure
    
    def test_truncate_text_for_comprehend_short_text(self, enricher):
        """Test text truncation with short text."""
        short_text = "Short text"
        result = enricher._truncate_text_for_comprehend(short_text)
        assert result == short_text
    
    def test_truncate_text_for_comprehend_long_text(self, enricher):
        """Test text truncation with long text."""
        # Create text that exceeds byte limit
        long_text = "x" * 6000  # Exceeds 5000 byte limit
        result = enricher._truncate_text_for_comprehend(long_text)
        
        # Result should be shorter and valid UTF-8
        assert len(result.encode('utf-8')) <= enricher.aws_settings.comprehend_max_bytes
        assert isinstance(result, str)  # Valid UTF-8
    
    def test_derive_topics_from_phrases(self, enricher):
        """Test topic derivation from key phrases."""
        phrases = [
            KeyPhrase("technology", 0.95, 0, 10),
            KeyPhrase("artificial intelligence", 0.90, 15, 35),
            KeyPhrase("machine learning", 0.85, 40, 56),
            KeyPhrase("the", 0.60, 60, 63),  # Low confidence, should be filtered
            KeyPhrase("very long phrase that should be filtered", 0.95, 70, 110)  # Too long
        ]
        
        topics = enricher._derive_topics_from_phrases(phrases)
        
        # Should include high-confidence, short phrases only
        assert len(topics) <= 5
        assert "Technology" in topics
        assert "the" not in topics  # Low confidence filtered out
    
    def test_build_summarization_prompt(self, enricher, sample_text):
        """Test summarization prompt building."""
        prompt = enricher._build_summarization_prompt(sample_text)
        
        assert "Human:" in prompt
        assert "concise summary" in prompt
        assert sample_text in prompt
        assert "Assistant:" in prompt
    
    def test_extract_summary_from_response_valid(self, enricher):
        """Test summary extraction from valid response."""
        response = {
            "content": [
                {"text": "This is a test summary."}
            ]
        }
        
        summary = enricher._extract_summary_from_response(response)
        assert summary == "This is a test summary."
    
    def test_extract_summary_from_response_invalid(self, enricher):
        """Test summary extraction from invalid response."""
        invalid_response = {"invalid": "format"}
        
        with pytest.raises(ValueError, match="Invalid Bedrock response format"):
            enricher._extract_summary_from_response(invalid_response)
    
    def test_extract_summary_from_response_empty(self, enricher):
        """Test summary extraction from empty response."""
        empty_response = {
            "content": [
                {"text": ""}
            ]
        }
        
        with pytest.raises(ValueError, match="Bedrock returned empty summary"):
            enricher._extract_summary_from_response(empty_response)


class TestDataModels:
    """Test cases for data model classes."""
    
    def test_sentiment_result(self):
        """Test SentimentResult data model."""
        scores = {'POSITIVE': 0.8, 'NEGATIVE': 0.1, 'NEUTRAL': 0.1, 'MIXED': 0.0}
        result = SentimentResult('POSITIVE', scores)
        
        assert result.sentiment == 'POSITIVE'
        assert result.confidence_scores == scores
        assert result.dominant_sentiment_confidence == 0.8
    
    def test_pii_result(self):
        """Test PIIResult data model."""
        entities = [
            PIIEntity('NAME', 'John Smith', 0.95, 0, 10),
            PIIEntity('EMAIL', 'john@example.com', 0.90, 15, 31)
        ]
        result = PIIResult(entities)
        
        assert result.has_pii
        assert len(result.entities) == 2
        assert set(result.pii_types) == {'NAME', 'EMAIL'}
    
    def test_pii_result_no_entities(self):
        """Test PIIResult with no entities."""
        result = PIIResult([])
        
        assert not result.has_pii
        assert len(result.entities) == 0
        assert result.pii_types == []
    
    def test_topic_result(self):
        """Test TopicResult data model."""
        phrases = [
            KeyPhrase("technology", 0.95, 0, 10),
            KeyPhrase("innovation", 0.85, 15, 25)
        ]
        topics = ["Technology", "Innovation"]
        result = TopicResult(phrases, topics)
        
        assert len(result.key_phrases) == 2
        assert result.topics == topics
        
        top_phrases = result.top_phrases
        assert top_phrases[0].text == "technology"  # Highest confidence first
    
    def test_summary_result(self):
        """Test SummaryResult data model."""
        result = SummaryResult("Summary text", 1000, 100, 500, "claude-3-haiku")
        
        assert result.summary == "Summary text"
        assert result.original_length == 1000
        assert result.summary_length == 100
        assert result.compression_ratio == 0.1
        assert result.processing_time_ms == 500
        assert result.model_used == "claude-3-haiku"
    
    def test_enrichment_results(self):
        """Test EnrichmentResults data model."""
        result = EnrichmentResults()
        
        assert result.sentiment is None
        assert result.pii_detection is None
        assert result.topics is None
        assert result.summary is None
        assert result.processing_time_ms == 0
        assert result.features_processed == []