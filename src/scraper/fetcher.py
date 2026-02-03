"""
HTTP client for fetching news articles with retry logic and bot avoidance.

This module provides a robust HTTP client that implements retry logic with
exponential backoff, appropriate headers for bot avoidance, and error handling
for various network conditions.
"""

import time
import random
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class FetchResult:
    """Result of an HTTP fetch operation."""
    
    url: str
    content: str
    status_code: int
    headers: Dict[str, str]
    encoding: Optional[str] = None
    fetch_time_ms: int = 0
    attempts: int = 1
    success: bool = True
    error_message: Optional[str] = None


class HTTPFetcher:
    """
    HTTP client with retry logic and bot avoidance techniques.
    
    Implements exponential backoff retry logic, appropriate HTTP headers,
    and various techniques to avoid being blocked by news websites.
    """
    
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        user_agent: Optional[str] = None
    ):
        """
        Initialize HTTP fetcher with configuration.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Multiplier for exponential backoff
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        
        # Default user agent that mimics a real browser
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Create session with retry configuration
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_headers(self, url: str) -> Dict[str, str]:
        """
        Generate appropriate headers for bot avoidance.
        
        Args:
            url: Target URL for header customization
            
        Returns:
            Dictionary of HTTP headers
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        
        headers = {
            "User-Agent": self.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0"
        }
        
        # Add referer for some sites to appear more legitimate
        if domain:
            headers["Referer"] = f"https://{domain}/"
        
        return headers
    
    def _add_random_delay(self) -> None:
        """Add random delay to avoid appearing bot-like."""
        delay = random.uniform(0.5, 2.0)  # Random delay between 0.5-2 seconds
        time.sleep(delay)
    
    def fetch(self, url: str) -> FetchResult:
        """
        Fetch content from URL with retry logic and bot avoidance.
        
        Args:
            url: URL to fetch
            
        Returns:
            FetchResult containing response data and metadata
        """
        start_time = time.time()
        attempts = 0
        last_error = None
        
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            return FetchResult(
                url=url,
                content="",
                status_code=0,
                headers={},
                success=False,
                error_message="Invalid URL format"
            )
        
        headers = self._get_headers(url)
        
        for attempt in range(self.max_retries + 1):
            attempts = attempt + 1
            
            try:
                # Add random delay for bot avoidance (except first attempt)
                if attempt > 0:
                    self._add_random_delay()
                
                # Make the request
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                
                # Calculate fetch time
                fetch_time_ms = int((time.time() - start_time) * 1000)
                
                # Check if request was successful
                if response.status_code == 200:
                    return FetchResult(
                        url=response.url,  # Final URL after redirects
                        content=response.text,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        encoding=response.encoding,
                        fetch_time_ms=fetch_time_ms,
                        attempts=attempts,
                        success=True
                    )
                
                # Handle specific error codes
                elif response.status_code == 403:
                    last_error = f"Access forbidden (403) - possible bot detection"
                elif response.status_code == 404:
                    last_error = f"Page not found (404)"
                elif response.status_code == 429:
                    last_error = f"Rate limited (429) - too many requests"
                else:
                    last_error = f"HTTP {response.status_code}: {response.reason}"
                
                # For client errors (4xx), don't retry
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    break
                    
            except requests.exceptions.Timeout:
                last_error = f"Request timeout after {self.timeout} seconds"
            except requests.exceptions.ConnectionError:
                last_error = "Connection error - unable to reach server"
            except requests.exceptions.TooManyRedirects:
                last_error = "Too many redirects"
            except requests.exceptions.RequestException as e:
                last_error = f"Request failed: {str(e)}"
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
        
        # All attempts failed
        fetch_time_ms = int((time.time() - start_time) * 1000)
        
        return FetchResult(
            url=url,
            content="",
            status_code=0,
            headers={},
            fetch_time_ms=fetch_time_ms,
            attempts=attempts,
            success=False,
            error_message=last_error or "Unknown error occurred"
        )
    
    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()