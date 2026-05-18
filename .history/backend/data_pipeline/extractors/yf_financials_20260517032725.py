import asyncio
import logging
import requests
from typing import Dict, Any
import yfinance as yf

logger = logging.getLogger(__name__)

class YFinanceDataExtractionError(Exception):
    pass

class YFinanceFinancialsExtractor:
    """
    Yahoo Finance üzerinden Bilanço, Gelir Tablosu ve Nakit Akım
    verilerini asenkron Thread havuzunda çeker ve 429 hatalarına karşı
    Custom Session kullanır.
    """
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        
        # Yahoo Finance IP Ban (429) korumasını aşmak için Custom Session
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })

    def _fetch_sync(self, ticker: str) -> Dict[str, Any]:
        """Senkron çalışan yfinance metodlarını çalıştırır."""
        yf_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        # Session'ı yfinance nesnesine paslıyoruz
        stock = yf.Ticker(yf_ticker, session=self.session)
        
        # DataFrame'leri dict'e çevirerek Orchestrator'a iletiyoruz
        return {
            "income_statement": stock.financials.to_dict() if not stock.financials.empty else {},
            "balance_sheet": stock.balance_sheet.to_dict() if not stock.balance_sheet.empty else {},
            "cash_flow": stock.cashflow.to_dict() if not stock.cashflow.empty else {}
        }

    async def fetch_financials(self, ticker: str) -> Dict[str, Any]:
        """Asenkron Orchestrator çağrısı."""
        for attempt in range(1, self.max_retries + 1):
            try:
                # yfinance I/O bloklaması yapmaması için arka plan thread'ine atıyoruz
                data = await asyncio.to_thread(self._fetch_sync, ticker)
                
                if not data["income_statement"] and not data["balance_sheet"]:
                    logger.warning(f"[{ticker}] YFinance tabloları boş döndürdü.")
                    
                return data
                
            except Exception as e:
                logger.warning(f"[{ticker}] YFinance çekim hatası (Deneme {attempt}): {e}")
                if attempt == self.max_retries:
                    raise YFinanceDataExtractionError(f"YFinance finansal veri çekilemedi: {str(e)}")
                await asyncio.sleep(2 ** attempt)