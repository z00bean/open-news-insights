# Open News Insights

**Transform messy news websites into clean, structured data with AI-powered analysis.**

Open News Insights is a serverless AWS Lambda application that automatically extracts, cleans, and analyzes news articles from any public website. It turns cluttered web pages into structured data with optional AI-powered insights like sentiment analysis, topic extraction, and content summarization.

## What Does This Do?

**Input**: Send a news article URL  
**Process**: Extract clean content, remove ads/navigation  
**Analyze**: Optional AI analysis (sentiment, topics, PII detection)  
**Output**: Structured JSON with clean text and insights  

### Real-World Use Cases

- **News Aggregation**: Clean content from multiple news sources for consistent formatting
- **Content Analysis**: Analyze sentiment and topics across news articles at scale  
- **Research Tools**: Extract clean text for academic or market research
- **Content Moderation**: Detect PII and inappropriate content in news articles
- **API Integration**: Forward processed results to your existing systems

## How It Works

The system processes news articles through a configurable pipeline:

1. **Web Scraping**: Fetches HTML from news websites with retry logic and bot avoidance
2. **Content Extraction**: Removes navigation, ads, and boilerplate using intelligent selectors
3. **AI Normalization**: (Optional) Uses AWS Bedrock Claude to further clean and normalize text
4. **NLP Analysis**: (Optional) AWS Comprehend provides sentiment, topics, and PII detection
5. **Result Delivery**: Formats and optionally forwards results to external APIs

### Architecture Components

- **News Scraper**: Fetches and parses HTML content from news websites
- **Text Extractor**: Removes boilerplate and extracts clean article content  
- **LLM Normalizer**: Uses AWS Bedrock for advanced text cleanup (optional)
- **NLP Enricher**: Performs sentiment analysis, PII detection, and topic extraction using AWS Comprehend (optional)
- **Result Formatter**: Formats and forwards results to external APIs

## Project Structure

```
open-news-insights/
├── src/                           # Source code
│   ├── handler.py                # 🚪 Lambda handler (main entry point)
│   ├── scraper/                  # 🌐 News scraping components
│   │   ├── scraper.py           #   Main scraper orchestrator
│   │   ├── fetcher.py           #   HTTP client with retry logic
│   │   ├── parser.py            #   HTML parsing and site detection
│   │   └── extractor.py         #   Content extraction and cleanup
│   ├── analysis/                 # 🤖 AI/ML processing
│   │   ├── normalizer.py        #   AWS Bedrock text normalization
│   │   ├── enricher.py          #   AWS Comprehend NLP analysis
│   │   └── error_handler.py     #   AWS service error handling
│   ├── postprocess/             # 📊 Result formatting
│   │   └── formatter.py         #   Response formatting and API forwarding
│   └── config/                  # ⚙️ Configuration management
│       ├── manager.py           #   Configuration loading and caching
│       ├── models.py            #   Data models and validation
│       ├── sites.py             #   Site-specific CSS selectors
│       └── defaults.py          #   Default settings and fallbacks
├── tests/                        # 🧪 Test suite
│   ├── unit/                    #   Component-level tests
│   ├── integration/             #   End-to-end pipeline tests
│   └── property/                #   Property-based tests (future)
├── infra/                       # 🏗️ Infrastructure as code
│   ├── parameters/              #   Environment-specific configs
│   │   ├── dev.json            #   Development settings
│   │   ├── staging.json        #   Staging settings
│   │   └── prod.json           #   Production settings
│   └── deploy.sh               #   Deployment scripts
├── template.yaml               # 📋 SAM template for AWS resources
├── requirements.txt            # 📦 Python dependencies
└── README.md                   # 📖 This file
```

## API Reference

### Request Format
```http
POST /process
Content-Type: application/json

{
  "url": "string (required)",           // News article URL to process
  "features": {                         // Optional feature flags
    "llm_normalization": boolean,       // Use AI for text cleanup
    "sentiment": boolean,               // Analyze sentiment
    "pii": boolean,                     // Detect PII entities  
    "topics": boolean,                  // Extract topics/keywords
    "summary": boolean,                 // Generate summary
    "external_api": boolean             // Forward to external API
  }
}
```

### Response Format
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "success": boolean,
  "article_metadata": {
    "url": "string",
    "title": "string", 
    "author": "string|null",
    "publish_date": "string|null",
    "domain": "string",
    "scrape_timestamp": "string (ISO 8601)"
  },
  "extracted_content": "string",      // Clean article text
  "normalized_content": "string|null", // AI-cleaned text (if enabled)
  "sentiment_analysis": {...}|null,    // Sentiment results (if enabled)
  "pii_detection": {...}|null,         // PII results (if enabled)  
  "topic_analysis": {...}|null,        // Topic results (if enabled)
  "summary": {...}|null,               // Summary (if enabled)
  "processing_metadata": {
    "processing_time_ms": number,
    "features_used": ["string"],
    "word_count": number,
    "extraction_method": "string",
    "confidence_score": number
  }
}
```

### Error Response Format
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "success": false,
  "error": {
    "type": "VALIDATION_ERROR|PROCESSING_ERROR|SERVICE_ERROR",
    "message": "Human-readable error description",
    "step": "parsing|scraping|extraction|normalization|enrichment|formatting",
    "details": {...}                    // Additional error context
  },
  "partial_results": {...}|null        // Any successfully processed data
}
```

## Performance & Limits

### Processing Times
- **Basic extraction**: 200-500ms
- **With AI normalization**: +300-800ms  
- **With NLP analysis**: +200-600ms
- **Complete pipeline**: 800-2000ms

### Content Limits
- **Maximum article length**: 100KB raw HTML
- **Bedrock text limit**: 100KB per request
- **Comprehend text limit**: 5KB per request (auto-truncated)

### Rate Limits
- **Lambda concurrency**: Configurable (default: 10)
- **AWS service limits**: Per service quotas apply
- **External API calls**: Configurable retry with exponential backoff

## Troubleshooting

### Common Issues

**❌ "Invalid URL format"**
```json
{"error": {"type": "VALIDATION_ERROR", "message": "Invalid URL format"}}
```
- Ensure URL starts with `http://` or `https://`
- Check for typos in the URL

**❌ "Content extraction failed"**  
```json
{"error": {"type": "PROCESSING_ERROR", "step": "extraction"}}
```
- Website may have unusual HTML structure
- Try with `llm_normalization: true` for better results
- Check if site blocks automated requests

**❌ "AWS service timeout"**
```json
{"error": {"type": "SERVICE_ERROR", "step": "enrichment"}}
```
- Temporary AWS service issue
- Retry the request
- Check AWS service status

### Debug Mode
Enable detailed logging by setting environment variable:
```bash
export LOG_LEVEL=DEBUG
```

## Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Add tests** for your changes
4. **Run the test suite**: `pytest`
5. **Commit your changes**: `git commit -m 'Add amazing feature'`
6. **Push to the branch**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

### Development Guidelines
- Write tests for all new functionality
- Follow PEP 8 style guidelines
- Add docstrings to public functions
- Update documentation for API changes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/open-news-insights/issues)
- **Documentation**: [Wiki](https://github.com/your-org/open-news-insights/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/open-news-insights/discussions)

## Quick Start Example

### 1. Basic Request
Send a POST request to process a news article:

```bash
curl -X POST https://your-api-gateway-url/process \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://theguardian.com/world/2024/climate-summit-agreement",
    "features": {
      "llm_normalization": true,
      "sentiment": true,
      "topics": true
    }
  }'
```

### 2. Response Example
```json
{
  "success": true,
  "article_metadata": {
    "url": "https://theguardian.com/world/2024/climate-summit-agreement",
    "title": "World Leaders Reach Historic Climate Agreement",
    "author": "Jane Reporter",
    "domain": "theguardian.com",
    "scrape_timestamp": "2024-01-15T14:30:00Z"
  },
  "extracted_content": "World leaders gathered in Geneva today to finalize a groundbreaking climate agreement that could reshape global environmental policy for the next decade...",
  "normalized_content": "World leaders reached a historic climate agreement in Geneva, establishing new carbon emission targets and creating a $100 billion fund for developing nations...",
  "sentiment_analysis": {
    "sentiment": "POSITIVE",
    "confidence": 0.89,
    "scores": {
      "positive": 0.89,
      "negative": 0.05,
      "neutral": 0.06
    }
  },
  "topic_analysis": {
    "key_phrases": [
      {"text": "climate agreement", "confidence": 0.95},
      {"text": "carbon emissions", "confidence": 0.87},
      {"text": "renewable energy", "confidence": 0.82}
    ],
    "topics": [
      {"name": "Environment", "confidence": 0.94},
      {"name": "Politics", "confidence": 0.78}
    ]
  },
  "processing_metadata": {
    "processing_time_ms": 1250,
    "features_used": ["scraping", "extraction", "llm_normalization", "sentiment", "topics"],
    "word_count": 245
  }
}
```

### 3. Feature Flags
Control which processing steps to run:

```json
{
  "url": "https://example-news.com/article",
  "features": {
    "llm_normalization": false,    // Skip AI text cleanup
    "sentiment": true,             // Analyze sentiment
    "pii": false,                 // Skip PII detection  
    "topics": true,               // Extract topics/keywords
    "summary": false,             // Skip summarization
    "external_api": false         // Don't forward to external API
  }
}
```

## Supported News Sites

The system works with any public news website, with optimized support for:

- **The Guardian** (theguardian.com)
- **Times of India** (timesofindia.indiatimes.com)  
- **Generic sites** using readability algorithms

### Site-Specific vs Generic Extraction

```python
# Site-specific selectors (higher accuracy)
guardian_config = {
    "domain": "theguardian.com",
    "title_selector": "h1[data-gu-name='headline']",
    "content_selector": "div[data-gu-name='body'] p",
    "author_selector": "address[aria-label='Contributor info'] a"
}

# Generic fallback (works on most sites)
generic_selectors = [
    "article p",           # Standard article paragraphs
    ".content p",          # Common content class
    "#main-content p",     # Main content ID
    "p"                    # All paragraphs as last resort
]
```

## Before & After: Content Extraction

### Input: Raw HTML from News Website
```html
<html>
<head><title>Breaking: Climate Summit Reaches Agreement</title></head>
<body>
  <!-- Navigation clutter -->
  <nav class="main-nav">
    <a href="/home">Home</a> | <a href="/politics">Politics</a>
  </nav>
  
  <!-- Advertisement -->
  <div class="ad-banner">
    <img src="ad.jpg" alt="Buy our product!">
  </div>
  
  <!-- Actual article content -->
  <article>
    <h1>World Leaders Reach Historic Climate Agreement</h1>
    <div class="byline">By Jane Reporter | Jan 15, 2024</div>
    
    <p>World leaders gathered in Geneva today to finalize a 
    groundbreaking climate agreement that could reshape global 
    environmental policy for the next decade.</p>
    
    <p>The agreement, signed by representatives from 195 countries, 
    establishes new carbon emission targets and creates a $100 billion 
    fund for developing nations.</p>
    
    <!-- Social sharing buttons -->
    <div class="social-share">
      <button>Share on Twitter</button>
      <button>Share on Facebook</button>
    </div>
    
    <p>"This is a historic moment," said UN Secretary-General 
    Maria Santos during the closing ceremony.</p>
  </article>
  
  <!-- Sidebar clutter -->
  <aside class="sidebar">
    <div class="newsletter">Subscribe to our newsletter!</div>
    <div class="related">You might also like...</div>
  </aside>
  
  <footer>© 2024 News Corp. All rights reserved.</footer>
</body>
</html>
```

### Output: Clean, Structured Data
```json
{
  "success": true,
  "article_metadata": {
    "title": "World Leaders Reach Historic Climate Agreement",
    "author": "Jane Reporter",
    "publish_date": "2024-01-15",
    "word_count": 67,
    "domain": "example-news.com"
  },
  "extracted_content": "World leaders gathered in Geneva today to finalize a groundbreaking climate agreement that could reshape global environmental policy for the next decade.\n\nThe agreement, signed by representatives from 195 countries, establishes new carbon emission targets and creates a $100 billion fund for developing nations.\n\n\"This is a historic moment,\" said UN Secretary-General Maria Santos during the closing ceremony.",
  "extraction_metadata": {
    "method": "site_specific",
    "confidence_score": 0.92,
    "removed_elements": [
      "navigation", "advertisements", "social_buttons", 
      "sidebar", "footer", "newsletter_signup"
    ],
    "paragraph_count": 3
  }
}
```

### What Gets Removed vs Preserved

✅ **Preserved (Article Content)**:
- Main headline and subheadings
- Article paragraphs and body text  
- Author bylines and publication dates
- Quotes and important formatting
- Image captions (when relevant)

❌ **Removed (Boilerplate)**:
- Navigation menus and site headers
- Advertisements and promotional content
- Social sharing buttons and widgets
- Newsletter signup forms
- Related articles and sidebars
- Comments sections and user-generated content
- Cookie notices and legal disclaimers

## AI-Powered Analysis Features

### Sentiment Analysis
Understand the emotional tone of news articles:

```json
{
  "sentiment_analysis": {
    "sentiment": "POSITIVE",           // POSITIVE, NEGATIVE, NEUTRAL, MIXED
    "confidence": 0.89,               // How confident the AI is (0-1)
    "scores": {
      "positive": 0.89,
      "negative": 0.05, 
      "neutral": 0.06
    }
  }
}
```

### Topic & Keyword Extraction
Automatically identify key themes and topics:

```json
{
  "topic_analysis": {
    "key_phrases": [
      {"text": "climate change", "confidence": 0.95},
      {"text": "renewable energy", "confidence": 0.87},
      {"text": "carbon emissions", "confidence": 0.82}
    ],
    "topics": [
      {"name": "Environment", "confidence": 0.94},
      {"name": "Politics", "confidence": 0.78},
      {"name": "International Relations", "confidence": 0.65}
    ]
  }
}
```

### PII Detection
Identify and optionally redact personally identifiable information:

```json
{
  "pii_detection": {
    "entities_found": [
      {
        "type": "PERSON",
        "text": "John Smith", 
        "confidence": 0.99,
        "start_offset": 45,
        "end_offset": 55
      },
      {
        "type": "EMAIL",
        "text": "contact@example.com",
        "confidence": 0.95,
        "start_offset": 120,
        "end_offset": 139
      }
    ],
    "redacted_text": "The spokesperson [PERSON] can be reached at [EMAIL]..."
  }
}
```

### Content Summarization
Generate concise summaries using AI:

```json
{
  "summary": {
    "text": "World leaders signed a historic climate agreement in Geneva, establishing new carbon emission targets and creating a $100 billion fund for developing nations to transition to renewable energy.",
    "compression_ratio": 0.25,        // Original length vs summary length
    "key_points": [
      "Historic climate agreement signed",
      "195 countries participated", 
      "$100 billion fund established"
    ]
  }
}
```

## Installation & Deployment

### Prerequisites
- Python 3.11+
- AWS CLI configured with appropriate permissions
- AWS SAM CLI installed

### Local Development Setup

1. **Clone and install dependencies**:
   ```bash
   git clone https://github.com/your-org/open-news-insights.git
   cd open-news-insights
   pip install -r requirements.txt
   ```

2. **Run tests**:
   ```bash
   pytest tests/                    # All tests
   pytest tests/unit/              # Unit tests only  
   pytest tests/integration/       # Integration tests only
   ```

3. **Test locally with SAM**:
   ```bash
   sam build
   sam local start-api
   ```

### AWS Deployment

1. **Build the application**:
   ```bash
   sam build
   ```

2. **Deploy with guided setup** (first time):
   ```bash
   sam deploy --guided
   ```

3. **Deploy updates**:
   ```bash
   sam deploy
   ```

### Environment Configuration

Set up environment-specific parameters in `infra/parameters/`:

```json
// infra/parameters/prod.json
{
  "Parameters": {
    "Environment": "prod",
    "BedrockModelId": "anthropic.claude-3-haiku-20240307-v1:0",
    "MaxRetries": "3",
    "TimeoutSeconds": "30",
    "ExternalApiEndpoint": "https://your-api.com/webhook"
  }
}
```

## Configuration

### Site-Specific Selectors
Add support for new news sites by configuring CSS selectors:

```python
# src/config/sites.py
SITE_CONFIGS = {
    "example-news.com": {
        "title_selector": "h1.article-title",
        "content_selector": ".article-body p",
        "author_selector": ".byline .author",
        "date_selector": ".publish-date",
        "fallback_selectors": ["article p", ".content p"]
    }
}
```

### Feature Flags
Control processing pipeline via request parameters:

| Feature | Description | AWS Service |
|---------|-------------|-------------|
| `llm_normalization` | AI-powered text cleanup | AWS Bedrock |
| `sentiment` | Sentiment analysis | AWS Comprehend |
| `pii` | PII detection | AWS Comprehend |
| `topics` | Topic/keyword extraction | AWS Comprehend |
| `summary` | Content summarization | AWS Bedrock |
| `external_api` | Forward results to external API | HTTP POST |

## Development & Testing

### Running Tests Locally
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test categories
pytest tests/unit/test_scraper.py          # Specific component
pytest tests/integration/                  # Integration tests
pytest -k "test_sentiment"                # Tests matching pattern
```

### Testing Individual Components
```python
# Test text extraction
from src.scraper.extractor import TextExtractor

extractor = TextExtractor()
html = "<article><p>Your news content here...</p></article>"
result = extractor.extract_content(html)
print(f"Clean text: {result.clean_text}")

# Test sentiment analysis  
from src.analysis.enricher import NLPEnricher
from src.config.models import AWSSettings

enricher = NLPEnricher(AWSSettings(region="us-east-1"))
sentiment = enricher.analyze_sentiment("This is great news!")
print(f"Sentiment: {sentiment.sentiment}")
```

### Adding New Features
1. **Add configuration** in `src/config/`
2. **Implement component** in appropriate module
3. **Add tests** in `tests/unit/` and `tests/integration/`
4. **Update handler** in `src/handler.py` to wire new feature
5. **Update documentation** and examples
