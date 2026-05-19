import logging
import yfinance as yf
from pyrate_limiter import Duration, RequestRate, Limiter
from typing import Dict, Any
import asyncio
import requests
import time

logger = logging.getLogger(__name__)

class YFinanceEngine:
    """
    BIST hisselerini rate-limit, User-Agent maskelemesi, Çeyreklik Fallback 
    ve Retry (Tekrar Deneme) mekanizması ile korumalı olarak çeken motor.
    """

    def __init__(self):
        # Güvenli rate limit (Güvenli mod: 3 saniyede 1 istek, dakikada max 10 istek)
        rate_sec = RequestRate(1, Duration.SECOND * 3)
        rate_min = RequestRate(10, Duration.MINUTE)
        self.limiter = Limiter(rate_sec, rate_min)

        # Sahte tarayıcı kimliği (User-Agent) taklit eden kalıcı oturum
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })

        self.proxies = {}

    def _apply_rate_limit(self):
        """Her istek öncesi token bucket kontrolü yapar."""
        self.limiter.ratelimit("yfinance_api")

    def get_financials_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak bilançoları çeker. Hata durumunda 3 kez tekrar dener."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker

        for attempt in range(3):
            try:
                # ENTEGRE EDİLEN DÜZELTME: Maskeli session yfinance içine başarıyla beslendi!
                stock = yf.Ticker(yf_ticker, session=self.session)

                # Güncel yfinance API metodları
                inc = stock.income_stmt
                bal = stock.balance_sheet
                cf = stock.cashflow

                # Çeyreklik bilanço yedekleme (Fallback) mekanizması
                if inc is None or inc.empty:
                    inc = stock.quarterly_income_stmt

                if bal is None or bal.empty:
                    bal = stock.quarterly_balance_sheet

                if cf is None or cf.empty:
                    cf = stock.quarterly_cashflow

                # DEBUG LOGS
                logger.warning(f"[{ticker}] stock.info: {stock.info}")
                logger.warning(f"[{ticker}] stock.fast_info: {stock.fast_info}")

                # Veri başarılı bir şekilde geldiyse sözlük olarak döndür
                if inc is not None and not inc.empty:
                    return {
                        "income_statement": inc.to_dict(),
                        "balance_sheet": bal.to_dict() if bal is not None and not bal.empty else {},
                        "cash_flow": cf.to_dict() if cf is not None and not cf.empty else {}
                    }

                logger.warning(
                    f"[{ticker}] Finansal tablo boş geldi, {attempt + 1}. deneme yapılıyor..."
                )
                time.sleep(2)

            except Exception as e:
                logger.error(
                    f"[{ticker}] Finansal tablo çekilirken hata ({attempt + 1}. deneme): {e}"
                )
                time.sleep(2)

        return {
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {}
        }

    def get_market_data_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak piyasa verilerini çeker. Hata durumunda 3 kez tekrar dener."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker

        for attempt in range(3):
            try:
                # ENTEGRE EDİLEN DÜZELTME: Maskeli session yfinance içine başarıyla beslendi!
                stock = yf.Ticker(yf_ticker, session=self.session)

                # 1. Anlık Fiyatı Bulma Algoritması
                current_price = stock.fast_info.get("last_price")

                if not current_price or str(current_price) == 'nan':
                    current_price = stock.fast_info.get("previous_close")

                if not current_price or str(current_price) == 'nan':
                    current_price = stock.info.get(
                        "currentPrice",
                        stock.info.get("previousClose")
                    )

                # 2. Toplam Lot Sayısını (Shares Outstanding) Bulma Algoritması
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
                logger.error(
                    f"[{ticker}] Piyasa verisi çekilirken hata ({attempt + 1}. deneme): {e}"
                )
                time.sleep(2)

        return {
            "current_price": None,
            "shares_outstanding": None,
            "market_cap_tl": None,
            "currency": "TRY",
            "source": "Yahoo_Finance_Protected"
        }

    async def fetch_all_data_async(self, ticker: str) -> Dict[str, Any]:
        """Asenkron orchestrator için tekil giriş noktası."""
        financials = await asyncio.to_thread(self.get_financials_sync, ticker)
        market_data = await asyncio.to_thread(self.get_market_data_sync, ticker)

        return {
            "ticker": ticker,
            "financials": financials,
            "market_data": market_data
        }