"""
Post-processing module for Open News Insights.

This module provides result formatting and external API integration
functionality for the news processing pipeline.
"""

from .formatter import (
    ResultFormatter,
    FormattedResponse,
    ArticleMetadata,
    ProcessingMetadata,
    FormattingError,
    ExternalAPIError
)

__all__ = [
    'ResultFormatter',
    'FormattedResponse',
    'ArticleMetadata',
    'ProcessingMetadata',
    'FormattingError',
    'ExternalAPIError'
]