# Open News Insights

A serverless Python application built on AWS Lambda that processes news articles through a configurable pipeline. The system accepts HTTP requests via API Gateway, fetches and processes news articles from public websites, optionally enriches content using AWS AI services, and forwards results to external APIs.

## Architecture

The system follows a modular design with clear separation of concerns:

- **News Scraper**: Fetches and parses HTML content from news websites
- **Text Extractor**: Removes boilerplate and extracts clean article content
- **LLM Normalizer**: Uses AWS Bedrock for advanced text cleanup (optional)
- **NLP Enricher**: Performs sentiment analysis, PII detection, and topic extraction using AWS Comprehend (optional)
- **Result Formatter**: Formats and forwards results to external APIs

## Project Structure

```
├── src/                    # Source code
│   ├── handler.py         # Lambda handler (main entry point)
│   ├── scraper/           # News scraping components
│   ├── analysis/          # LLM and NLP processing
│   ├── postprocess/       # Result formatting
│   └── config/            # Configuration management
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   └── property/          # Property-based tests
├── infra/                 # Infrastructure configuration
├── template.yaml          # SAM template
└── requirements.txt       # Python dependencies
```

## Getting Started

### Prerequisites

- Python 3.11+
- AWS CLI configured
- AWS SAM CLI

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Deployment

1. Build the application:
   ```bash
   sam build
   ```

2. Deploy to AWS:
   ```bash
   sam deploy --guided
   ```

## Usage

Send a POST request to the API Gateway endpoint with a news article URL:

```json
{
  "url": "https://example-news-site.com/article",
  "features": {
    "llm_normalization": true,
    "sentiment_analysis": true,
    "pii_detection": false,
    "topic_extraction": true,
    "summarization": true,
    "external_api_forwarding": false
  }
}
```

## Text Extraction Example

The system's text extractor removes boilerplate content and extracts clean article text. Here's an example:

### Input HTML
```html
<html>
<head><title>Breaking News</title></head>
<body>
  <nav class="navigation">
    <a href="/home">Home</a>
    <a href="/politics">Politics</a>
  </nav>
  
  <header class="site-header">
    <div class="logo">News Site</div>
    <div class="ad-banner">Advertisement</div>
  </header>
  
  <article class="main-content">
    <h1>Major Climate Summit Reaches Historic Agreement</h1>
    <div class="byline">By Jane Reporter | Published: 2024-01-15</div>
    
    <p>World leaders gathered in Geneva today to finalize a groundbreaking 
    climate agreement that could reshape global environmental policy for 
    the next decade.</p>
    
    <p>The agreement, signed by representatives from 195 countries, 
    establishes new carbon emission targets and creates a $100 billion 
    fund for developing nations to transition to renewable energy.</p>
    
    <div class="social-share">
      <button>Share on Twitter</button>
      <button>Share on Facebook</button>
    </div>
    
    <p>"This is a historic moment for our planet," said UN Secretary-General 
    Maria Santos during the closing ceremony. "We have shown that global 
    cooperation is possible when facing existential challenges."</p>
  </article>
  
  <aside class="sidebar">
    <div class="related-articles">Related Stories...</div>
    <div class="newsletter-signup">Subscribe to our newsletter</div>
  </aside>
  
  <footer>Copyright 2024 News Site</footer>
</body>
</html>
```

### Output (Extracted Content)
```json
{
  "clean_text": "World leaders gathered in Geneva today to finalize a groundbreaking climate agreement that could reshape global environmental policy for the next decade.\n\nThe agreement, signed by representatives from 195 countries, establishes new carbon emission targets and creates a $100 billion fund for developing nations to transition to renewable energy.\n\n\"This is a historic moment for our planet,\" said UN Secretary-General Maria Santos during the closing ceremony. \"We have shown that global cooperation is possible when facing existential challenges.\"",
  "word_count": 67,
  "paragraph_count": 3,
  "extraction_method": "readability",
  "confidence_score": 0.85,
  "removed_elements": [
    "tag:nav",
    "tag:header", 
    "tag:aside",
    "tag:footer",
    "pattern:social-share",
    "pattern:ad-banner",
    "pattern:newsletter-signup"
  ]
}
```

### Key Features Demonstrated

- **Boilerplate Removal**: Navigation, headers, footers, ads, and social sharing buttons are automatically removed
- **Content Preservation**: Main article paragraphs and quotes are preserved with proper formatting
- **Quality Assessment**: Confidence score indicates extraction quality (0.0-1.0)
- **Metadata Tracking**: Word count, paragraph count, and extraction method are provided
- **Error Resilience**: System handles malformed HTML and encoding issues gracefully

## Development

### Running Tests
```bash
pytest
```

### Running Property-Based Tests
```bash
pytest tests/property/
```

### Testing Text Extraction Locally
```python
from src.scraper.extractor import TextExtractor

# Initialize extractor
extractor = TextExtractor()

# Extract content from HTML
html = "<html><body><article><p>Your news article content here...</p></article></body></html>"
result = extractor.extract_content(html)

print(f"Clean text: {result.clean_text}")
print(f"Confidence: {result.confidence_score}")
print(f"Removed elements: {result.removed_elements}")
```
