import logging
import yfinance as yf
import requests_cache
from pyrate_limiter import Duration, RequestRate, Limiter
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class YFinanceEngine:
    """
    BIST hisselerini banlanmadan, önbellekleyerek ve rate-limit uygulayarak çeken çekirdek motor.
    """
    def __init__(self, cache_expire_days: int = 1):
        # 1. Caching: Aynı gün içinde aynı veriyi tekrar indirme (SQLite tabanlı)
        self.session = requests_cache.CachedSession(
            'yfinance_bist_cache',
            expire_after=cache_expire_days * 86400 # Saniye cinsinden
        )

        # 2. Rate Limiting: Saniyede max 2, dakikada max 20 istek (Bot algılamasını kör eder)
        rate_sec = RequestRate(2, Duration.SECOND)
        rate_min = RequestRate(20, Duration.MINUTE)
        self.limiter = Limiter(rate_sec, rate_min)

        # 3. Retry Stratejisi: 429 veya 500 hatalarında artan sürelerle tekrar deneme
        retry_strategy = Retry(
            total=4,
            backoff_factor=2, # 2s, 4s, 8s, 16s bekleme
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Sahte başlıklar
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate, br"
        })

    def _apply_rate_limit(self):
        """Her istek öncesi token bucket kontrolü yapar."""
        self.limiter.ratelimit("yfinance_api")

    def get_financials_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak bilançoları çeker."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        try:
            stock = yf.Ticker(yf_ticker, session=self.session)
            return {
                "income_statement": stock.financials.to_dict() if not stock.financials.empty else {},
                "balance_sheet": stock.balance_sheet.to_dict() if not stock.balance_sheet.empty else {},
                "cash_flow": stock.cashflow.to_dict() if not stock.cashflow.empty else {}
            }
        except Exception as e:
            logger.error(f"[{ticker}] Finansal tablo çekilemedi: {e}")
            return {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    def get_market_data_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak piyasa verilerini çeker."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        try:
            stock = yf.Ticker(yf_ticker, session=self.session)
            fast_info = stock.fast_info
            
            return {
                "current_price": fast_info.get("last_price"),
                "market_cap_tl": fast_info.get("market_cap"),
                "currency": "TRY",
                "source": "Yahoo_Finance_Protected"
            }
        except Exception as e:
            logger.error(f"[{ticker}] Piyasa verisi çekilemedi: {e}")
            return {"current_price": None, "market_cap_tl": None, "currency": "TRY", "source": "Yahoo_Finance_Protected"}

    async def fetch_all_data_async(self, ticker: str) -> Dict[str, Any]:
        """Asenkron orchestrator için tekil giriş noktası."""
        financials = await asyncio.to_thread(self.get_financials_sync, ticker)
        market_data = await asyncio.to_thread(self.get_market_data_sync, ticker)
        
        return {
            "ticker": ticker,
            "financials": financials,
            "market_data": market_data
        }