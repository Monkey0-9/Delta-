"""
Google Finance and News RSS scraper (zero-browser HTTP/2)
"""

import httpx
import xml.etree.ElementTree as ET
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from delta.data.base_provider import (
    MarketDataProvider, NewsItem, DataType, DataQuality
)

logger = logging.getLogger(__name__)


class GoogleFinanceNewsProvider(MarketDataProvider):
    """Google Finance News RSS scraper"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = "https://news.google.com/rss"
    
    async def initialize(self) -> bool:
        """Initialize the HTTP client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            self._initialized = True
            logger.info("Initialized Google Finance News provider")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Google Finance News provider: {e}")
            return False
    
    async def get_quote(self, symbol: str) -> Optional[object]:
        """Google Finance doesn't provide quotes via RSS"""
        return None
    
    async def get_bars(self, symbol: str, timeframe: str, 
                      start: datetime, end: datetime) -> List:
        """Google Finance doesn't provide bars via RSS"""
        return []
    
    async def get_news(self, symbol: str, limit: int = 10) -> List[NewsItem]:
        """Get news from Google Finance RSS"""
        if not self.client:
            return []
        
        try:
            # Construct RSS URL for stock news
            url = f"{self.base_url}/search"
            params = {
                "q": f"{symbol} stock financial",
                "hl": "en-US",
                "gl": "US",
                "ceid": "US:en"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            # Parse XML
            root = ET.fromstring(response.content)
            
            news_items = []
            seen_hashes = set()
            
            for item in root.findall(".//item"):
                if len(news_items) >= limit:
                    break
                
                title = item.find("title")
                link = item.find("link")
                pub_date = item.find("pubDate")
                source = item.find("source")
                
                if title is None or link is None:
                    continue
                
                title_text = title.text
                link_text = link.text
                
                # Deduplicate using hash
                title_hash = hash(title_text)
                if title_hash in seen_hashes:
                    continue
                seen_hashes.add(title_hash)
                
                # Parse publication date
                pub_datetime = datetime.utcnow()
                if pub_date is not None and pub_date.text:
                    try:
                        pub_datetime = datetime.strptime(pub_date.text, "%a, %d %b %Y %H:%M:%S %Z")
                    except ValueError:
                        pass
                
                # Extract tickers from title
                tickers = self._extract_tickers(title_text)
                if symbol.upper() not in [t.upper() for t in tickers]:
                    tickers.append(symbol.upper())
                
                # Calculate sentiment (simple keyword-based)
                sentiment = self._calculate_sentiment(title_text)
                
                # Get source
                source_text = source.text if source is not None else "Google News"
                
                news_item = NewsItem(
                    title=title_text,
                    url=link_text,
                    source=source_text,
                    published_at=pub_datetime,
                    symbols=tickers,
                    sentiment=sentiment
                )
                
                news_items.append(news_item)
            
            logger.info(f"Retrieved {len(news_items)} news items for {symbol}")
            return news_items
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting news for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting news for {symbol}: {e}")
            return []
    
    def _extract_tickers(self, text: str) -> List[str]:
        """Extract stock tickers from text using regex"""
        # Match uppercase words 1-5 characters (common ticker pattern)
        ticker_pattern = r'\b[A-Z]{1,5}\b'
        potential_tickers = re.findall(ticker_pattern, text)
        
        # Filter out common words
        common_words = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HAD', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'HAS', 'HAVE', 'BEEN'}
        tickers = [t for t in potential_tickers if t not in common_words]
        
        return tickers
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score based on keywords"""
        positive_keywords = [
            'beat', 'surge', 'rally', 'gain', 'growth', 'profit', 'rise', 'jump',
            'strong', 'bullish', 'upgrade', 'buy', 'outperform', 'success', 'expand'
        ]
        negative_keywords = [
            'fall', 'drop', 'decline', 'loss', 'miss', 'weak', 'bearish', 'downgrade',
            'sell', 'underperform', 'fail', 'cut', 'layoff', 'concern', 'risk'
        ]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # Normalize to [-1, 1]
        sentiment = (positive_count - negative_count) / total
        return sentiment
    
    def supports_data_type(self, data_type: DataType) -> bool:
        """Google Finance News provider only supports news"""
        return data_type == DataType.NEWS
    
    async def shutdown(self) -> None:
        """Shutdown the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("Google Finance News provider shutdown")


# Register the provider
from delta.core.registry import data_provider_registry
data_provider_registry.register_provider("google_news", GoogleFinanceNewsProvider)
