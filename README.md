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

## Development

Run tests:
```bash
pytest
```

Run property-based tests:
```bash
pytest tests/property/
```

## License

See LICENSE file for details.