"""
Proxy health checker to avoid wasting API quota
"""
import requests
from typing import Dict, Optional


class ProxyHealthChecker:
    """Check if proxy is working before making expensive API calls"""

    def __init__(self, proxies: Dict[str, str], timeout: int = 5):
        """
        Initialize proxy health checker

        Args:
            proxies: Proxy configuration dict
            timeout: Connection timeout in seconds
        """
        self.proxies = proxies
        self.timeout = timeout

    def is_healthy(self) -> bool:
        """
        Check if proxy can connect to Google services

        Returns:
            True if proxy is working, False otherwise
        """
        if not self.proxies:
            # No proxy configured, assume direct connection
            return True

        test_urls = [
            "https://www.google.com",
            "https://generativelanguage.googleapis.com/v1beta/models",
        ]

        for url in test_urls:
            try:
                response = requests.head(
                    url,
                    proxies=self.proxies,
                    timeout=self.timeout,
                    verify=True
                )

                # If we get any response (even 404), proxy is working
                if response.status_code in [200, 404, 403]:
                    print(f"✓ Proxy health check passed: {url}")
                    return True

            except (requests.exceptions.ProxyError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout) as e:
                print(f"⚠ Proxy health check failed for {url}: {type(e).__name__}")
                continue

        print("❌ Proxy is not healthy - all health checks failed")
        return False

    def wait_until_healthy(self, max_attempts: int = 3, retry_delay: int = 10) -> bool:
        """
        Wait until proxy becomes healthy

        Args:
            max_attempts: Maximum number of health check attempts
            retry_delay: Delay between attempts in seconds

        Returns:
            True if proxy became healthy, False otherwise
        """
        import time

        for attempt in range(max_attempts):
            if self.is_healthy():
                return True

            if attempt < max_attempts - 1:
                print(f"Waiting {retry_delay}s before next health check...")
                time.sleep(retry_delay)

        return False
