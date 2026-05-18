import logging
import yfinance as yf
from pyrate_limiter import Duration, RequestRate, Limiter
from typing import Dict, Any
import asyncio
import requests
import time  # <-- Bekleme (sleep) mekanizması için eklendi

logger = logging.getLogger(__name__)

class YFinanceEngine:
    """
    BIST hisselerini rate-limit, User-Agent maskelemesi ve Retry (Tekrar Deneme) mekanizması ile korumalı olarak çeken motor.
    """
    def __init__(self):
        # 1. GÜNCELLEME: İstek hızını iyice yavaşlatıyoruz (Güvenli mod: 3 saniyede 1 istek, dakikada max 10 istek)
        rate_sec = RequestRate(1, Duration.SECOND * 3)
        rate_min = RequestRate(10, Duration.MINUTE)
        self.limiter = Limiter(rate_sec, rate_min)
        
        # DOCKER HAYAT KURTARICISI: Yahoo'nun bizi bot sanıp engellememesi için kalıcı oturum
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        })
        
        # İleride proxy kullanmak gerekirse diye altyapı hazırlığı
        self.proxies = {}

    def _apply_rate_limit(self):
        """Her istek öncesi token bucket kontrolü yapar."""
        self.limiter.ratelimit("yfinance_api")

    def get_financials_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak bilançoları çeker. Hata durumunda 3 kez tekrar dener."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        # 2. GÜNCELLEME: İNATÇI RETRY MEKANİZMASI (3 KEZ DENER)
        for attempt in range(3):
            try:
                # Maskeli session'ı yfinance'e besliyoruz!
                stock = yf.Ticker(yf_ticker, session=self.session)
                
                inc = stock.financials
                bal = stock.balance_sheet
                cf = stock.cashflow

                # Veri geldiyse ve boş değilse hemen sistemi besle
                if inc is not None and not inc.empty:
                    return {
                        "income_statement": inc.to_dict(),
                        "balance_sheet": bal.to_dict() if bal is not None and not bal.empty else {},
                        "cash_flow": cf.to_dict() if cf is not None and not cf.empty else {}
                    }
                
                # Eğer veri boş döndüyse Yahoo engellemiş olabilir, bekle ve tekrar dene
                logger.warning(f"[{ticker}] Finansal tablo boş geldi, {attempt + 1}. deneme yapılıyor...")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"[{ticker}] Finansal tablo çekilirken hata ({attempt + 1}. deneme): {e}")
                time.sleep(2)
                
        # 3 denemenin sonunda hala inatla vermiyorsa boş dön (Pipeline çökecek ama en azından savaştık)
        return {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    def get_market_data_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron olarak piyasa verilerini çeker. Hata durumunda 3 kez tekrar dener."""
        self._apply_rate_limit()
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        # Piyasa verisi için de aynı inatçı döngüyü kuruyoruz
        for attempt in range(3):
            try:
                stock = yf.Ticker(yf_ticker, session=self.session)
                
                # 1. Fiyatı Bul
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
                logger.error(f"[{ticker}] Piyasa verisi çekilirken hata ({attempt + 1}. deneme): {e}")
                time.sleep(2)
                
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