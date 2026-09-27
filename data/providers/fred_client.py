"""
FRED (Federal Reserve Economic Data) API client for macro intelligence
"""

import httpx
import pandas as pd
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from delta.data.base_provider import (
    MacroDataProvider, MacroSeries, DataType, DataQuality
)

logger = logging.getLogger(__name__)


class FREDProvider(MacroDataProvider):
    """FRED API client for macro economic data"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client: Optional[httpx.AsyncClient] = None
        self.api_key = config.get("api_key", "")
        self.base_url = "https://api.stlouisfed.org/fred"
    
    async def initialize(self) -> bool:
        """Initialize the HTTP client"""
        try:
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "DELTA-OS/2.0"
                }
            )
            
            # Test connection with a simple call
            if self.api_key:
                await self._test_connection()
            
            self._initialized = True
            logger.info("Initialized FRED provider")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize FRED provider: {e}")
            return False
    
    async def _test_connection(self) -> bool:
        """Test API connection"""
        try:
            url = f"{self.base_url}/series/observations"
            params = {
                "series_id": "GDP",
                "api_key": self.api_key,
                "file_type": "json",
                "limit": 1
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"FRED API test failed: {e}")
            return False
    
    async def get_quote(self, symbol: str) -> Optional[object]:
        """FRED doesn't provide quotes"""
        return None
    
    async def get_bars(self, symbol: str, timeframe: str, 
                      start: datetime, end: datetime) -> List:
        """FRED doesn't provide bars"""
        return []
    
    async def get_news(self, symbol: str, limit: int = 10) -> List:
        """FRED doesn't provide news"""
        return []
    
    async def get_macro_series(self, series_id: str) -> Optional[MacroSeries]:
        """Get macro economic series from FRED"""
        if not self.client:
            return None
        
        try:
            # Get series info
            info_url = f"{self.base_url}/series"
            info_params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json"
            }
            info_response = await self.client.get(info_url, params=info_params)
            info_response.raise_for_status()
            info_data = info_response.json()
            
            series_info = info_data.get("seriess", [{}])[0]
            series_title = series_info.get("title", series_id)
            
            # Get observations
            obs_url = f"{self.base_url}/series/observations"
            obs_params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "observation_start": (datetime.utcnow() - timedelta(days=365*10)).strftime("%Y-%m-%d"),
                "observation_end": datetime.utcnow().strftime("%Y-%m-%d")
            }
            obs_response = await self.client.get(obs_url, params=obs_params)
            obs_response.raise_for_status()
            obs_data = obs_response.json()
            
            observations = obs_data.get("observations", [])
            
            # Convert to DataFrame
            df_data = []
            for obs in observations:
                date_str = obs.get("date", "")
                value_str = obs.get("value", "")
                
                if value_str and value_str != ".":
                    try:
                        date = datetime.strptime(date_str, "%Y-%m-%d")
                        value = float(value_str)
                        df_data.append({"date": date, "value": value})
                    except (ValueError, TypeError):
                        continue
            
            if not df_data:
                return None
            
            df = pd.DataFrame(df_data)
            df.set_index("date", inplace=True)
            df.sort_index(inplace=True)
            
            return MacroSeries(
                series_id=series_id,
                name=series_title,
                data=df,
                last_updated=datetime.utcnow(),
                quality=DataQuality.LIVE
            )
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting series {series_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting series {series_id}: {e}")
            return None
    
    async def get_yield_curve_spread(self) -> Optional[float]:
        """Get 10Y-2Y yield curve spread"""
        try:
            series_10y = await self.get_macro_series("DGS10")
            series_2y = await self.get_macro_series("DGS2")
            
            if not series_10y or not series_2y:
                return None
            
            latest_10y = series_10y.data.iloc[-1]["value"]
            latest_2y = series_2y.data.iloc[-1]["value"]
            
            spread = latest_10y - latest_2y
            return spread
            
        except Exception as e:
            logger.error(f"Error calculating yield spread: {e}")
            return None
    
    async def get_net_liquidity(self) -> Optional[float]:
        """Calculate net liquidity index"""
        try:
            # Fed Assets (WALCL)
            fed_assets = await self.get_macro_series("WALCL")
            # Treasury General Account (WTREGEN)
            treasury_account = await self.get_macro_series("WTREGEN")
            # Reverse Repo (RRPONTSYD)
            reverse_repo = await self.get_macro_series("RRPONTSYD")
            
            if not all([fed_assets, treasury_account, reverse_repo]):
                return None
            
            latest_assets = fed_assets.data.iloc[-1]["value"]
            latest_treasury = treasury_account.data.iloc[-1]["value"]
            latest_repo = reverse_repo.data.iloc[-1]["value"]
            
            net_liquidity = latest_assets - latest_treasury - latest_repo
            return net_liquidity
            
        except Exception as e:
            logger.error(f"Error calculating net liquidity: {e}")
            return None
    
    def supports_data_type(self, data_type: DataType) -> bool:
        """FRED provider supports macro data"""
        return data_type == DataType.MACRO
    
    async def shutdown(self) -> None:
        """Shutdown the HTTP client"""
        if self.client:
            await self.client.aclose()
            self._initialized = False
            logger.info("FRED provider shutdown")


# Register the provider
from delta.core.registry import data_provider_registry
data_provider_registry.register_provider("fred", FREDProvider)
