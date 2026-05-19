import logging
import yfinance as yf
from pyrate_limiter import Duration, RequestRate, Limiter
from typing import Dict, Any
import asyncio
import time
import random

logger = logging.getLogger(__name__)

class YFinanceEngine:
    """
    BIST hisselerini yfinance'ın NATIVE (Dahili) curl_cffi korumasıyla çeken, 
    kendi yazdığımız dış hız sınırlandırıcı (Rate Limit) ve Exponential Backoff'a sahip motor.
    """

    def __init__(self):
        # Güvenli rate limit: Dakikada max 10 istek (Session yaratmıyoruz, sadece bekleme süresini ölçüyoruz)
        rate_sec = RequestRate(1, Duration.SECOND * 3)
        rate_min = RequestRate(10, Duration.MINUTE)
        self.limiter = Limiter(rate_sec, rate_min)

    def _apply_rate_limit(self):
        """İstek atmadan önce token kovanı (bucket) üzerinden sınırları kontrol eder."""
        self.limiter.ratelimit("yfinance_api")

    def _get_sleep_time(self, attempt: int) -> float:
        # Exponential Backoff + Jitter (Doğal insan bekleme süresi simülasyonu)
        return (3 * (2 ** attempt)) + random.uniform(1.0, 3.0)

    def get_financials_sync(self, ticker: str) -> Dict[str, Any]:
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker

        for attempt in range(3):
            try:
                # KRİTİK ÇÖZÜM: session=self.session parametresi TAMAMEN SİLİNDİ.
                # Artık yfinance kendi içindeki güçlü anti-bot kalkanını kullanacak.
                stock = yf.Ticker(yf_ticker)

                inc = stock.income_stmt
                bal = stock.balance_sheet
                cf = stock.cashflow

                if inc is None or inc.empty:
                    inc = stock.quarterly_income_stmt
                if bal is None or bal.empty:
                    bal = stock.quarterly_balance_sheet
                if cf is None or cf.empty:
                    cf = stock.quarterly_cashflow

                if inc is not None and not inc.empty:
                    return {
                        "income_statement": inc.to_dict(),
                        "balance_sheet": bal.to_dict() if bal is not None and not bal.empty else {},
                        "cash_flow": cf.to_dict() if cf is not None and not cf.empty else {}
                    }

                sleep_t = self._get_sleep_time(attempt)
                logger.warning(f"[{ticker}] Finansal tablo boş geldi, {attempt + 1}. deneme {sleep_t:.1f} sn sonra yapılacak...")
                time.sleep(sleep_t)

            except Exception as e:
                sleep_t = self._get_sleep_time(attempt)
                logger.error(f"[{ticker}] Finansal tablo hatası ({attempt + 1}. deneme): {e}")
                time.sleep(sleep_t)

        return {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    def get_market_data_sync(self, ticker: str) -> Dict[str, Any]:
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker

        for attempt in range(3):
            try:
                # KRİTİK ÇÖZÜM: session parametresi yok.
                stock = yf.Ticker(yf_ticker)

                current_price = stock.fast_info.get("last_price")
                if not current_price or str(current_price) == 'nan':
                    current_price = stock.fast_info.get("previous_close")
                if not current_price or str(current_price) == 'nan':
                    current_price = stock.info.get("currentPrice", stock.info.get("previousClose"))

                shares_outstanding = stock.fast_info.get("shares")
                if not shares_outstanding or str(shares_outstanding) == 'nan':
                    shares_outstanding = stock.info.get("sharesOutstanding")

                return {
                    "current_price": float(current_price) if current_price else None,
                    "shares_outstanding": int(shares_outstanding) if shares_outstanding else None,
                    "market_cap_tl": float(stock.fast_info.get("market_cap")) if stock.fast_info.get("market_cap") else None,
                    "currency": "TRY",
                    "source": "Yahoo_Finance_Native_Protected"
                }

            except Exception as e:
                sleep_t = self._get_sleep_time(attempt)
                logger.error(f"[{ticker}] Piyasa verisi hatası ({attempt + 1}. deneme): {e}")
                time.sleep(sleep_t)

        return {
            "current_price": None, "shares_outstanding": None, 
            "market_cap_tl": None, "currency": "TRY", "source": "Yahoo_Finance_Native_Protected"
        }

    async def fetch_all_data_async(self, ticker: str) -> Dict[str, Any]:
        financials = await asyncio.to_thread(self.get_financials_sync, ticker)
        await asyncio.sleep(random.uniform(2.0, 4.0)) # Toplu istekler arası nefes payı
        market_data = await asyncio.to_thread(self.get_market_data_sync, ticker)

        return {
            "ticker": ticker,
            "financials": financials,
            "market_data": market_data
        }