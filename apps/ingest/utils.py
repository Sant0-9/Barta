"""Utility functions for ingestion pipeline"""

import hashlib
from urllib.parse import urlparse


def sha256_bytes(url: str) -> bytes:
    """Generate SHA256 hash of URL as bytes"""
    return hashlib.sha256(url.encode('utf-8')).digest()


def get_domain(url: str) -> str:
    """Extract domain from URL"""
    parsed = urlparse(url)
    return parsed.netloc.lower()


# TODO: Add robots.txt respect
# TODO: Add rate limiting per domain