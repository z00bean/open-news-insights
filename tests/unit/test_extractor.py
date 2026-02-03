"""
Unit tests for text extractor functionality.
"""

import pytest
from src.scraper.extractor import TextExtractor, ExtractedContent, ExtractionError


class TestTextExtractor:
    """Test cases for TextExtractor class."""
    
    def test_init(self):
        """Test extractor initialization."""
        extractor = TextExtractor()
        assert extractor.removed_elements == []
        assert extractor.content_indicators == []
    
    def test_extract_empty_content(self):
        """Test extraction from empty content."""
        extractor = TextExtractor()
        
        # Test None input
        result = extractor.extract_content(None)
        assert result.clean_text == ""
        assert result.word_count == 0
        assert result.extraction_method == "error"
        assert not result.error_details is None
        
        # Test empty string
        result = extractor.extract_content("")
        assert result.clean_text == ""
        assert result.word_count == 0
        assert result.extraction_method == "empty_input"
    
    def test_extract_basic_html(self):
        """Test extraction from basic HTML."""
        html = """
        <html>
            <body>
                <h1>Article Title</h1>
                <p>This is the first paragraph with substantial content that provides meaningful information to readers.</p>
                <p>This is the second paragraph with more detailed content and additional context for the article.</p>
                <p>And a third paragraph to make it substantial with even more content and information.</p>
                <p>A fourth paragraph continues the narrative with important details and comprehensive coverage.</p>
                <p>The final paragraph concludes the article with summary points and key takeaways for readers.</p>
            </body>
        </html>
        """
        
        extractor = TextExtractor()
        result = extractor.extract_content(html)
        
        assert result.clean_text != ""
        assert result.word_count > 50  # Should meet quality threshold
        assert result.paragraph_count > 0
        assert result.confidence_score > 0
        assert result.extraction_method in ["readability", "generic_fallback"]
    
    def test_remove_boilerplate_elements(self):
        """Test removal of boilerplate elements."""
        html = """
        <html>
            <body>
                <nav>Navigation menu</nav>
                <header>Site header</header>
                <main>
                    <article>
                        <h1>Real Article Title</h1>
                        <p>This is the actual article content that should be preserved and contains meaningful information.</p>
                        <p>Another paragraph with substantial content that provides detailed information about the topic.</p>
                        <p>A third paragraph continues the narrative with important details and comprehensive coverage.</p>
                        <p>The fourth paragraph adds more context and depth to the article content.</p>
                        <p>Finally, the last paragraph concludes with summary points and key takeaways.</p>
                    </article>
                </main>
                <aside class="sidebar">Sidebar content</aside>
                <footer>Site footer</footer>
                <script>console.log('ads');</script>
            </body>
        </html>
        """
        
        extractor = TextExtractor()
        result = extractor.extract_content(html)
        
        # Should contain article content
        assert "actual article content" in result.clean_text
        
        # Should not contain boilerplate
        assert "Navigation menu" not in result.clean_text
        assert "Site header" not in result.clean_text
        assert "Sidebar content" not in result.clean_text
        assert "Site footer" not in result.clean_text
        
        # Check that elements were removed
        assert len(result.removed_elements) > 0
    
    def test_site_specific_extraction(self):
        """Test extraction with site-specific selectors."""
        html = """
        <html>
            <body>
                <div class="content">
                    <h1 class="title">Article Title</h1>
                    <div class="article-body">
                        <p>First paragraph of the article with substantial content and meaningful information.</p>
                        <p>Second paragraph continues the narrative with detailed explanations and context.</p>
                        <p>Third paragraph provides additional insights and comprehensive coverage of the topic.</p>
                        <p>Fourth paragraph adds more depth and analysis to the article content.</p>
                        <p>Final paragraph concludes with summary points and key takeaways for readers.</p>
                    </div>
                </div>
                <div class="sidebar">Sidebar content to ignore</div>
            </body>
        </html>
        """
        
        site_selectors = {
            'content_selector': '.article-body p',
            'title_selector': '.title'
        }
        
        extractor = TextExtractor()
        result = extractor.extract_content(html, site_selectors)
        
        assert "First paragraph" in result.clean_text
        assert "Second paragraph" in result.clean_text
        assert "Sidebar content" not in result.clean_text
        assert result.extraction_method == "site_specific"
    
    def test_encoding_handling(self):
        """Test handling of encoding issues."""
        # HTML with special characters
        html = """
        <html>
            <body>
                <p>Content with special chars: café, naïve, résumé and other international characters.</p>
                <p>Unicode content: 你好世界 and more text to make this substantial content.</p>
                <p>Additional paragraph with accented characters: François, José, München, and København.</p>
                <p>More content to ensure we meet the minimum word count requirements for quality assessment.</p>
                <p>Final paragraph with mixed content including symbols: €, £, ¥, and other currency symbols.</p>
            </body>
        </html>
        """
        
        extractor = TextExtractor()
        result = extractor.extract_content(html)
        
        assert result.clean_text != ""
        assert result.word_count > 30
        # Should handle encoding gracefully without errors
    
    def test_malformed_html_handling(self):
        """Test handling of malformed HTML."""
        malformed_html = """
        <html>
            <body>
                <p>Unclosed paragraph
                <div>Nested without closing
                <p>Another paragraph</p>
                <script>Unclosed script
            </body>
        """
        
        extractor = TextExtractor()
        result = extractor.extract_content(malformed_html)
        
        # Should not crash and should extract some content
        assert isinstance(result, ExtractedContent)
        # May have low confidence but should not error completely
        assert result.extraction_method != "error" or result.clean_text == ""
    
    def test_content_quality_assessment(self):
        """Test content quality assessment."""
        extractor = TextExtractor()
        
        # Good quality content (needs at least 50 words and 3 sentences)
        good_content = """This is a substantial piece of content with proper sentences and meaningful information. 
        It contains multiple paragraphs with good structure and coherent thoughts. The content demonstrates 
        proper writing style with varied sentence lengths and appropriate vocabulary. This type of content 
        would typically be found in a well-written news article or blog post. The sentences flow naturally 
        and provide valuable information to readers."""
        assert extractor._is_good_content(good_content)
        
        # Poor quality content
        poor_content = "Short"
        assert not extractor._is_good_content(poor_content)
        
        # Empty content
        assert not extractor._is_good_content("")
        
        # Content with too few sentences
        few_sentences = "This is just one sentence with many words to reach the minimum word count but it lacks proper sentence structure."
        assert not extractor._is_good_content(few_sentences)