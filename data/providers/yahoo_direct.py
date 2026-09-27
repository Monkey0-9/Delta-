"""
Direct HTTP/2 Yahoo Finance v8 chart client (zero external dependencies)
"""

import httpx
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from delta.data.base_provider import (
    MarketDataProvider, Quote, Bar, NewsItem, DataType, DataQuality
)

logger = logging.getLogger(__name__)


class YahooDirectProvider(MarketDataProvider):
    """Direct HTTP/2 client for Yahoo Finance v8 API"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = "https://query1.finance.yahoo.com"
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        self.current_user_agent_index = 0
    
    async def initialize(self) -> bool:
        """Initialize the HTTP client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": self._get_user_agent(),
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9"
                }
            )
            self._initialized = True
            logger.info("Initialized Yahoo Direct provider")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Yahoo Direct provider: {e}")
            return False
    
    def _get_user_agent(self) -> str:
        """Rotate user agents"""
        ua = self.user_agents[self.current_user_agent_index]
        self.current_user_agent_index = (self.current_user_agent_index + 1) % len(self.user_agents)
        return ua
    
    def _rotate_user_agent(self) -> None:
        """Rotate to next user agent"""
        if self.client:
            self.client.headers["User-Agent"] = self._get_user_agent()
    
    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote using v8 finance API"""
        if not self.client:
            return None
        
        try:
            url = f"{self.base_url}/v8/finance/chart/{symbol}"
            params = {
                "interval": "1m",
                "range": "1d",
                "includePrePost": "true"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            result = data.get("chart", {}).get("result", [])
            
            if not result:
                return None
            
            meta = result[0].get("meta", {})
            indicators = result[0].get("indicators", {})
            quote_data = indicators.get("quote", [{}])[0]
            
            if not quote_data:
                return None
            
            # Get latest data
            timestamps = quote_data.get("timestamp", [])
            if not timestamps:
                return None
            
            latest_idx = -1
            close = quote_data.get("close", [])[latest_idx]
            volume = quote_data.get("volume", [])[latest_idx]
            
            # Calculate bid/ask spread (approximate)
            spread = close * 0.001 if close else 0
            
            return Quote(
                symbol=symbol.upper(),
                bid=close - spread if close else 0,
                ask=close + spread if close else 0,
                bid_size=int(volume * 0.1) if volume else 0,
                ask_size=int(volume * 0.1) if volume else 0,
                last=close if close else 0,
                volume=int(volume) if volume else 0,
                timestamp=datetime.utcnow(),
                quality=DataQuality.LIVE
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting quote for {symbol}: {e}")
            self._rotate_user_agent()
            return None
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    async def get_bars(self, symbol: str, timeframe: str, 
                      start: datetime, end: datetime) -> List[Bar]:
        """Get historical bars using v8 finance API"""
        if not self.client:
            return []
        
        try:
            # Map timeframe to Yahoo interval
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "1h": "1h",
                "1d": "1d",
                "1w": "1wk"
            }
            interval = interval_map.get(timeframe, "1d")
            
            # Calculate range
            days_diff = (end - start).days
            range_map = {
                1: "1d",
                5: "5d",
                30: "1mo",
                90: "3mo",
                180: "6mo",
                365: "1y",
                730: "2y"
            }
            range_str = range_map.get(days_diff, "5y")
            
            url = f"{self.base_url}/v8/finance/chart/{symbol}"
            params = {
                "interval": interval,
                "range": range_str,
                "includePrePost": "true"
            }
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            result = data.get("chart", {}).get("result", [])
            
            if not result:
                return []
            
            indicators = result[0].get("indicators", {})
            quote_data = indicators.get("quote", [{}])[0]
            
            timestamps = quote_data.get("timestamp", [])
            opens = quote_data.get("open", [])
            highs = quote_data.get("high", [])
            lows = quote_data.get("low", [])
            closes = quote_data.get("close", [])
            volumes = quote_data.get("volume", [])
            
            bars = []
            for i, ts in enumerate(timestamps):
                if i >= len(opens) or i >= len(highs) or i >= len(lows) or i >= len(closes):
                    continue
                
                bar_date = datetime.fromtimestamp(ts)
                if start <= bar_date <= end:
                    bar = Bar(
                        symbol=symbol.upper(),
                        timestamp=bar_date,
                        open=opens[i] if opens[i] else 0,
                        high=highs[i] if highs[i] else 0,
                        low=lows[i] if lows[i] else 0,
                        close=closes[i] if closes[i] else 0,
                        volume=int(volumes[i]) if volumes[i] else 0,
                        quality=DataQuality.LIVE
                    )
                    bars.append(bar)
            
            return bars
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting bars for {symbol}: {e}")
            self._rotate_user_agent()
            return []
        except Exception as e:
            logger.error(f"Error getting bars for {symbol}: {e}")
            return []
    
    async def get_news(self, symbol: str, limit: int = 10) -> List[NewsItem]:
        """Yahoo doesn't provide news via v8 API, return empty list"""
        # News will be handled by Google Finance provider
        return []
    
    def supports_data_type(self, data_type: DataType) -> bool:
        """Yahoo Direct supports quotes and bars"""
        return data_type in [DataType.QUOTE, DataType.BARS]
    
    async def shutdown(self) -> None:
        """Shutdown the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("Yahoo Direct provider shutdown")


# Register the provider
from delta.core.registry import data_provider_registry
data_provider_registry.register_provider("yahoo", YahooDirectProvider)
