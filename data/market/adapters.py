"""Market Data Adapters - Real Data Sources

Provides interfaces for real-time and historical market data from
multiple vendors (Yahoo Finance, Alpha Vantage, Polygon.io, etc.)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence
import pandas as pd
import numpy as np


class DataType(Enum):
    """Market data types"""
    TICK = "tick"
    L1 = "l1"  # Level 1 quotes
    L2 = "l2"  # Level 2 order book
    BAR = "bar"  # OHLCV bars
    TRADE = "trade"
    QUOTE = "quote"
    CORPORATE_ACTION = "corporate_action"
    DIVIDEND = "dividend"
    SPLIT = "split"


class DataFrequency(Enum):
    """Data frequency"""
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    HOURLY = "1h"
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1m"


@dataclass(frozen=True, slots=True)
class MarketData:
    """Unified market data structure"""
    symbol: str
    timestamp: datetime
    data_type: DataType
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[int] = None
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    trade_price: Optional[Decimal] = None
    trade_size: Optional[int] = None
    exchange: Optional[str] = None
    conditions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass(frozen=True, slots=True)
class CorporateAction:
    """Corporate action data"""
    symbol: str
    action_type: str  # DIVIDEND, SPLIT, MERGER, SPINOFF, etc.
    declaration_date: datetime
    ex_date: datetime
    record_date: datetime
    payable_date: datetime
    ratio: Optional[Decimal] = None  # For splits
    amount: Optional[Decimal] = None  # For dividends
    metadata: Optional[Dict[str, Any]] = None


class MarketDataAdapter(ABC):
    """Abstract base class for market data adapters"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to data source"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source"""
        pass
    
    @abstractmethod
    async def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        frequency: DataFrequency = DataFrequency.DAILY,
    ) -> pd.DataFrame:
        """Get historical OHLCV bars"""
        pass
    
    @abstractmethod
    async def get_real_time_quote(self, symbol: str) -> MarketData:
        """Get current quote for a symbol"""
        pass
    
    @abstractmethod
    async def get_corporate_actions(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> List[CorporateAction]:
        """Get corporate actions for a symbol"""
        pass
    
    @abstractmethod
    async def subscribe_real_time(
        self,
        symbols: Sequence[str],
        callback: callable,
    ) -> None:
        """Subscribe to real-time data for symbols"""
        pass
    
    def is_connected(self) -> bool:
        """Check if adapter is connected"""
        return self._connected


class YahooFinanceAdapter(MarketDataAdapter):
    """Yahoo Finance adapter (free, good for development)"""
    
    def __init__(self):
        super().__init__()
        try:
            import yfinance as yf
            self._yf = yf
        except ImportError:
            raise ImportError("yfinance required: pip install yfinance")
    
    async def connect(self) -> bool:
        """Yahoo Finance doesn't require explicit connection"""
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        """Yahoo Finance doesn't require explicit disconnection"""
        self._connected = False
    
    async def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        frequency: DataFrequency = DataFrequency.DAILY,
    ) -> pd.DataFrame:
        """Get historical bars from Yahoo Finance"""
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        
        # Map frequency to yfinance interval
        interval_map = {
            DataFrequency.MINUTE: "1m",
            DataFrequency.HOURLY: "1h", 
            DataFrequency.DAILY: "1d",
            DataFrequency.WEEKLY: "1wk",
            DataFrequency.MONTHLY: "1mo",
        }
        interval = interval_map.get(frequency, "1d")
        
        # Convert datetime to string format for yfinance
        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        
        try:
            data = ticker.history(
                start=start_str,
                end=end_str,
                interval=interval,
                auto_adjust=True,  # Adjust for splits/dividends
                prepost=False,
            )
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
        
        if data.empty:
            return pd.DataFrame()
        
        # Standardize column names
        data.columns = [col.lower() for col in data.columns]
        data.index.name = "timestamp"
        data.reset_index(inplace=True)
        
        return data
    
    async def get_real_time_quote(self, symbol: str) -> MarketData:
        """Get current quote from Yahoo Finance"""
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Get latest price
        history = ticker.history(period="1d", interval="1m")
        if not history.empty:
            latest = history.iloc[-1]
            close = Decimal(str(latest['Close']))
            volume = int(latest['Volume'])
        else:
            close = Decimal(str(info.get('currentPrice', info.get('regularMarketPrice', 0))))
            volume = 0
        
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            data_type=DataType.QUOTE,
            close=close,
            volume=volume,
            bid=Decimal(str(info.get('bid', 0))),
            ask=Decimal(str(info.get('ask', 0))),
            bid_size=info.get('bidSize'),
            ask_size=info.get('askSize'),
        )
    
    async def get_corporate_actions(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> List[CorporateAction]:
        """Get corporate actions from Yahoo Finance"""
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        actions = ticker.actions
        
        if actions is None or actions.empty:
            return []
        
        corporate_actions = []
        for date, row in actions.iterrows():
            if start <= date <= end:
                # Determine action type
                if 'Dividends' in str(row):
                    action_type = "DIVIDEND"
                    amount = Decimal(str(row['Dividends']))
                    corporate_actions.append(
                        CorporateAction(
                            symbol=symbol,
                            action_type=action_type,
                            declaration_date=date,
                            ex_date=date,
                            record_date=date,
                            payable_date=date + timedelta(days=30),
                            amount=amount,
                        )
                    )
                elif 'Stock Splits' in str(row):
                    action_type = "SPLIT"
                    ratio = Decimal(str(row['Stock Splits']))
                    corporate_actions.append(
                        CorporateAction(
                            symbol=symbol,
                            action_type=action_type,
                            declaration_date=date,
                            ex_date=date,
                            record_date=date,
                            payable_date=date,
                            ratio=ratio,
                        )
                    )
        
        return corporate_actions
    
    async def subscribe_real_time(
        self,
        symbols: Sequence[str],
        callback: callable,
    ) -> None:
        """Yahoo Finance doesn't support real-time streaming"""
        raise NotImplementedError("Yahoo Finance doesn't support real-time streaming")


class AlphaVantageAdapter(MarketDataAdapter):
    """Alpha Vantage adapter (free tier available)"""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        import requests
        self._requests = requests
    
    async def connect(self) -> bool:
        """Test API connection"""
        try:
            response = self._requests.get(
                self.BASE_URL,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": "AAPL",
                    "apikey": self.api_key,
                },
                timeout=10,
            )
            self._connected = response.status_code == 200
            return self._connected
        except Exception:
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Alpha Vantage doesn't require explicit disconnection"""
        self._connected = False
    
    async def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        frequency: DataFrequency = DataFrequency.DAILY,
    ) -> pd.DataFrame:
        """Get historical bars from Alpha Vantage"""
        # Map frequency to Alpha Vantage function
        function_map = {
            DataFrequency.DAILY: "TIME_SERIES_DAILY",
            DataFrequency.WEEKLY: "TIME_SERIES_WEEKLY",
            DataFrequency.MONTHLY: "TIME_SERIES_MONTHLY",
        }
        function = function_map.get(frequency, "TIME_SERIES_DAILY")
        
        response = self._requests.get(
            self.BASE_URL,
            params={
                "function": function,
                "symbol": symbol,
                "apikey": self.api_key,
                "outputsize": "full",
            },
            timeout=30,
        )
        
        data = response.json()
        
        # Parse response based on function
        time_series_key = f"{function.replace('_', ' ')}"
        if time_series_key not in data:
            return pd.DataFrame()
        
        time_series = data[time_series_key]
        
        # Convert to DataFrame
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.index = pd.to_datetime(df.index)
        df.columns = [col.split('. ')[1] for col in df.columns]
        df.columns = [col.lower() for col in df.columns]
        
        # Filter by date range
        df = df[(df.index >= start) & (df.index <= end)]
        
        # Convert to numeric
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.reset_index(inplace=True)
        df.rename(columns={'index': 'timestamp'}, inplace=True)
        
        return df
    
    async def get_real_time_quote(self, symbol: str) -> MarketData:
        """Get current quote from Alpha Vantage"""
        response = self._requests.get(
            self.BASE_URL,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key,
            },
            timeout=10,
        )
        
        data = response.json()
        quote = data.get('Global Quote', {})
        
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            data_type=DataType.QUOTE,
            open=Decimal(quote.get('02. open', 0)),
            high=Decimal(quote.get('03. high', 0)),
            low=Decimal(quote.get('04. low', 0)),
            close=Decimal(quote.get('05. price', 0)),
            volume=int(quote.get('06. volume', 0)),
            bid=Decimal(quote.get('08. previous close', 0)),  # Alpha Vantage limited bid/ask
            ask=Decimal(quote.get('08. previous close', 0)),
        )
    
    async def get_corporate_actions(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> List[CorporateAction]:
        """Alpha Vantage has limited corporate action data"""
        # Use dividends and earnings endpoints
        response = self._requests.get(
            self.BASE_URL,
            params={
                "function": "DIVIDENDS",
                "symbol": symbol,
                "apikey": self.api_key,
            },
            timeout=30,
        )
        
        data = response.json()
        dividends = data.get('data', [])
        
        corporate_actions = []
        for item in dividends:
            ex_date = datetime.strptime(item['ex_dividend_date'], '%Y-%m-%d')
            if start <= ex_date <= end:
                corporate_actions.append(
                    CorporateAction(
                        symbol=symbol,
                        action_type="DIVIDEND",
                        declaration_date=ex_date,
                        ex_date=ex_date,
                        record_date=ex_date,
                        payable_date=ex_date + timedelta(days=30),
                        amount=Decimal(str(item['amount'])),
                    )
                )
        
        return corporate_actions
    
    async def subscribe_real_time(
        self,
        symbols: Sequence[str],
        callback: callable,
    ) -> None:
        """Alpha Vantage doesn't support real-time streaming"""
        raise NotImplementedError("Alpha Vantage doesn't support real-time streaming")


class RealTimeAdapter(MarketDataAdapter):
    """Real-time streaming adapter (e.g., Polygon.io, WebSocket-based)"""
    
    def __init__(self, api_key: str, provider: str = "polygon"):
        super().__init__(api_key)
        self.provider = provider
        self._websocket = None
        self._callbacks = {}
    
    async def connect(self) -> bool:
        """Connect to real-time data WebSocket"""
        if self.provider == "polygon":
            try:
                import websockets
                import json
                
                uri = f"wss://stream.polygon.io/stocks?apiKey={self.api_key}"
                self._websocket = await websockets.connect(uri)
                
                # Subscribe to ticker data
                await self._websocket.send(json.dumps({
                    "action": "subscribe",
                    "params": "T.*"
                }))
                
                self._connected = True
                return True
            except Exception as e:
                print(f"Failed to connect to Polygon: {e}")
                self._connected = False
                return False
        else:
            raise NotImplementedError(f"Provider {self.provider} not implemented")
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        if self._websocket:
            await self._websocket.close()
            self._websocket = None
        self._connected = False
    
    async def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        frequency: DataFrequency = DataFrequency.DAILY,
    ) -> pd.DataFrame:
        """Real-time adapters may not support historical data"""
        raise NotImplementedError("Use historical adapter for historical data")
    
    async def get_real_time_quote(self, symbol: str) -> MarketData:
        """Get current quote from real-time stream"""
        # This would typically come from the WebSocket stream
        # For now, return a placeholder
        return MarketData(
            symbol=symbol,
            timestamp=datetime.now(),
            data_type=DataType.QUOTE,
        )
    
    async def get_corporate_actions(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> List[CorporateAction]:
        """Real-time adapters don't typically provide corporate actions"""
        return []
    
    async def subscribe_real_time(
        self,
        symbols: Sequence[str],
        callback: callable,
    ) -> None:
        """Subscribe to real-time data for symbols"""
        if not self._connected:
            await self.connect()
        
        for symbol in symbols:
            self._callbacks[symbol] = callback
        
        # Start listening to WebSocket messages
        # This would be implemented in a separate async task
        raise NotImplementedError("WebSocket message handling to be implemented")


class HistoricalAdapter(MarketDataAdapter):
    """Historical data adapter using multiple providers"""
    
    def __init__(self, primary_adapter: MarketDataAdapter, fallback_adapters: List[MarketDataAdapter] = None):
        self.primary_adapter = primary_adapter
        self.fallback_adapters = fallback_adapters or []
    
    async def connect(self) -> bool:
        """Connect to primary adapter"""
        return await self.primary_adapter.connect()
    
    async def disconnect(self) -> None:
        """Disconnect from all adapters"""
        await self.primary_adapter.disconnect()
        for adapter in self.fallback_adapters:
            await adapter.disconnect()
    
    async def get_historical_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        frequency: DataFrequency = DataFrequency.DAILY,
    ) -> pd.DataFrame:
        """Try primary adapter, then fallbacks"""
        try:
            return await self.primary_adapter.get_historical_bars(symbol, start, end, frequency)
        except Exception as e:
            print(f"Primary adapter failed: {e}, trying fallbacks")
            for adapter in self.fallback_adapters:
                try:
                    return await adapter.get_historical_bars(symbol, start, end, frequency)
                except Exception:
                    continue
            raise
    
    async def get_real_time_quote(self, symbol: str) -> MarketData:
        """Historical adapter doesn't support real-time"""
        raise NotImplementedError("Use real-time adapter for real-time data")
    
    async def get_corporate_actions(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> List[CorporateAction]:
        """Try primary adapter, then fallbacks"""
        try:
            return await self.primary_adapter.get_corporate_actions(symbol, start, end)
        except Exception as e:
            print(f"Primary adapter failed: {e}, trying fallbacks")
            for adapter in self.fallback_adapters:
                try:
                    return await adapter.get_corporate_actions(symbol, start, end)
                except Exception:
                    continue
            raise
    
    async def subscribe_real_time(
        self,
        symbols: Sequence[str],
        callback: callable,
    ) -> None:
        """Historical adapter doesn't support real-time"""
        raise NotImplementedError("Use real-time adapter for real-time streaming")
