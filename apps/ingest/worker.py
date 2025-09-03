"""Main ingestion worker module"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import psycopg
from simhash import Simhash
import trafilatura
from playwright.sync_api import sync_playwright
from .utils import sha256_bytes, get_domain

# Add the API directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '../api'))
from core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_html(url: str) -> str:
    """Fetch HTML content using Playwright with Firefox headless"""
    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)  # 30 second timeout
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        if "Playwright" in str(e):
            raise RuntimeError(
                "Playwright not properly installed. Run: playwright install --with-deps"
            ) from e
        raise


def extract_text(html: str) -> str:
    """Extract clean text from HTML using trafilatura"""
    extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
    return extracted or ""


def compute_simhash(text_or_title: str) -> int:
    """Compute simhash of text for near-duplicate detection"""
    if not text_or_title.strip():
        return 0
    # Ensure the value fits in PostgreSQL bigint (-2^63 to 2^63-1)
    raw_value = Simhash(text_or_title).value
    # Convert unsigned 64-bit to signed 64-bit
    return raw_value if raw_value < 2**63 else raw_value - 2**64


def near_duplicate(conn: psycopg.Connection, simhash: int, days_back: int = 14) -> bool:
    """Check if article is near-duplicate based on simhash within last N days"""
    if simhash == 0:
        return False
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT simhash FROM articles 
            WHERE created_at >= %s AND simhash IS NOT NULL
        """, (cutoff_date,))
        
        existing_hashes = [row[0] for row in cur.fetchall()]
        
        # Check Hamming distance <= 3 for near duplicates
        for existing_hash in existing_hashes:
            hamming_distance = bin(simhash ^ existing_hash).count('1')
            if hamming_distance <= 3:
                return True
    
    return False


def upsert_article(
    conn: psycopg.Connection,
    url: str,
    title: Optional[str],
    body: str,
    published_at: Optional[datetime],
    source_domain: str
) -> Optional[int]:
    """Insert article if unique, return article_id or None if duplicate"""
    url_hash = sha256_bytes(url)
    
    # Compute simhash from title + first 2000 chars of body
    simhash_text = (title or "") + " " + body[:2000]
    simhash_value = compute_simhash(simhash_text)
    
    # Check for near duplicates
    if near_duplicate(conn, simhash_value):
        logger.info(f"Near duplicate detected for URL: {url}")
        return None
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO articles (url, url_hash, title, body, published_at, simhash, source_domain)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO NOTHING
                RETURNING id
            """, (url, url_hash, title, body, published_at, simhash_value, source_domain))
            
            result = cur.fetchone()
            if result:
                article_id = result[0]
                conn.commit()
                logger.info(f"Inserted article {article_id}: {title or url}")
                return article_id
            else:
                logger.info(f"Article already exists: {url}")
                return None
                
    except Exception as e:
        conn.rollback()
        logger.error(f"Error upserting article {url}: {e}")
        return None


def ingest_url(url: str) -> Dict[str, Any]:
    """Ingest a single URL and return stats"""
    stats = {"url": url, "success": False, "article_id": None, "error": None}
    
    try:
        # Convert SQLAlchemy URL to psycopg format
        db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg.connect(db_url)
        
        # Fetch and extract content
        logger.info(f"Fetching URL: {url}")
        html = fetch_html(url)
        
        logger.info(f"Extracting text from {url}")
        body = extract_text(html)
        
        if not body.strip():
            stats["error"] = "No extractable content"
            return stats
        
        # Extract basic metadata (title from first line or URL)
        lines = body.split('\n')
        title = lines[0].strip()[:200] if lines and lines[0].strip() else None
        source_domain = get_domain(url)
        
        # Upsert article
        article_id = upsert_article(
            conn, url, title, body, None, source_domain
        )
        
        if article_id:
            stats["article_id"] = article_id
            stats["success"] = True
            # TODO: Enqueue for embedding processing
        
        conn.close()
        
    except Exception as e:
        stats["error"] = str(e)
        logger.error(f"Failed to ingest {url}: {e}")
    
    return stats


def main():
    """CLI entrypoint for ingestion worker"""
    # Create seeds.txt if it doesn't exist
    seeds_file = "seeds.txt"
    if not os.path.exists(seeds_file):
        sample_urls = [
            "https://example.com/news/article1",
            "https://example.com/news/article2",
            "https://example.com/news/article3"
        ]
        with open(seeds_file, 'w') as f:
            f.write('\n'.join(sample_urls))
        logger.info(f"Created {seeds_file} with sample URLs")
    
    # Read URLs from seeds file
    try:
        with open(seeds_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        logger.error(f"Seeds file {seeds_file} not found")
        sys.exit(1)
    
    if not urls:
        logger.warning("No URLs found in seeds file")
        sys.exit(0)
    
    logger.info(f"Starting ingestion of {len(urls)} URLs")
    
    # Process each URL
    success_count = 0
    error_count = 0
    
    for url in urls:
        stats = ingest_url(url)
        if stats["success"]:
            success_count += 1
        else:
            error_count += 1
            logger.error(f"Failed {url}: {stats['error']}")
    
    # Print final stats
    logger.info(f"Ingestion complete. Success: {success_count}, Errors: {error_count}")
    
    # Exit with non-zero code if too many failures
    if error_count > len(urls) / 2:
        logger.error("Too many failures")
        sys.exit(1)


if __name__ == "__main__":
    main()