import logging
import yfinance as yf
from pyrate_limiter import Duration, RequestRate, Limiter
from typing import Dict, Any
import asyncio

logger = logging.getLogger(__name__)

class YFinanceEngine:
    """
    BIST hisselerini rate-limit ile korumalı olarak çeken motor.
    Not: yfinance'in kendi crumb/cookie yöneticisinin çalışması için Custom Session kaldırıldı.
    """
    def __init__(self):
        # Sadece Rate Limiting: Saniyede max 2, dakikada max 20 istek (Bot algılamasını kör eder)
        rate_sec = RequestRate(2, Duration.SECOND)
        rate_min = RequestRate(20, Duration.MINUTE)
        self.limiter = Limiter(rate_sec, rate_min)

    def _apply_rate_limit(self):
        """Her istek öncesi token bucket kontrolü yapar."""
        self.limiter.ratelimit("yfinance_api")

    def get_financials_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak bilançoları çeker."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        try:
            # Custom Session YOK. yfinance kendi session'ını yönetsin.
            stock = yf.Ticker(yf_ticker)
            
            inc = stock.financials
            bal = stock.balance_sheet
            cf = stock.cashflow

            return {
                "income_statement": inc.to_dict() if inc is not None and not inc.empty else {},
                "balance_sheet": bal.to_dict() if bal is not None and not bal.empty else {},
                "cash_flow": cf.to_dict() if cf is not None and not cf.empty else {}
            }
        except Exception as e:
            logger.error(f"[{ticker}] Finansal tablo çekilemedi: {e}")
            return {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    def get_market_data_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak piyasa verilerini çeker."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        try:
            stock = yf.Ticker(yf_ticker)
            
            # 1. Fiyatı Bul (Piyasa kapalıyken fast_info.last_price boş dönebilir, previous_close'a düş)
            current_price = stock.fast_info.get("last_price")
            if not current_price or str(current_price) == 'nan':
                current_price = stock.fast_info.get("previous_close")
            if not current_price or str(current_price) == 'nan':
                current_price = stock.info.get("currentPrice", stock.info.get("previousClose"))

            # 2. Toplam Hisse Adedini (Lot Sayısını) Bul
            shares_outstanding = stock.fast_info.get("shares")
            if not shares_outstanding or str(shares_outstanding) == 'nan':
                shares_outstanding = stock.info.get("sharesOutstanding")

            return {
                "current_price": float(current_price) if current_price else None,
                "shares_outstanding": int(shares_outstanding) if shares_outstanding else None,
                "market_cap_tl": float(stock.fast_info.get("market_cap")) if stock.fast_info.get("market_cap") else None,
                "currency": "TRY",
                "source": "Yahoo_Finance_Protected"
            }
        except Exception as e:
            logger.error(f"[{ticker}] Piyasa verisi çekilemedi: {e}")
            return {"current_price": None, "shares_outstanding": None, "market_cap_tl": None, "currency": "TRY", "source": "Yahoo_Finance_Protected"}

    async def fetch_all_data_async(self, ticker: str) -> Dict[str, Any]:
        """Asenkron orchestrator için tekil giriş noktası."""
        financials = await asyncio.to_thread(self.get_financials_sync, ticker)
        market_data = await asyncio.to_thread(self.get_market_data_sync, ticker)
        
        return {
            "ticker": ticker,
            "financials": financials,
            "market_data": market_data
        }