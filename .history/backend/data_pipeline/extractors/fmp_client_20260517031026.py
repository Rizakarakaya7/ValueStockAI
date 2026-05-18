import asyncio
import logging
import os
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)

class FMPDataExtractionError(Exception):
    pass

class FMPExtractor:
    """
    Financial Modeling Prep üzerinden Bilanço, Gelir Tablosu ve Nakit Akım
    verilerini resmi API üzerinden asenkron olarak çeker.
    """
    BASE_URL = "https://financialmodelingprep.com/api/v3"

    def __init__(self, max_retries: int = 3):
        # .env dosyasından API anahtarını otomatik alır
        self.api_key = os.getenv("FMP_API_KEY")
        if not self.api_key:
            raise ValueError("FMP_API_KEY ortam değişkenlerinde bulunamadı. Lütfen .env dosyanızı kontrol edin.")
            
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        await self.client.aclose()

    async def fetch_financials(self, ticker: str, limit: int = 4) -> Dict[str, Any]:
        """
        BİST şirketleri için gerekli olan 3 ana tabloyu (Bilanço, Gelir Tablosu, Nakit Akım) çeker.
        FMP'de Türk hisseleri sonuna '.IS' eki alarak çalışır (Örn: FROTO.IS).
        """
        fmp_ticker = f"{ticker}.IS" if not ticker.endswith(".IS") else ticker
        
        # Çekilecek 3 ana tablonun uç noktaları
        endpoints = {
            "income_statement": f"/income-statement/{fmp_ticker}",
            "balance_sheet": f"/balance-sheet-statement/{fmp_ticker}",
            "cash_flow": f"/cash-flow-statement/{fmp_ticker}"
        }

        results = {}
        
        for statement_name, endpoint in endpoints.items():
            url = f"{self.BASE_URL}{endpoint}?limit={limit}&apikey={self.api_key}"
            
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await self.client.get(url)
                    response.raise_for_status()
                    
                    data = response.json()
                    if not data:
                        logger.warning(f"[{fmp_ticker}] için {statement_name} verisi boş döndü.")
                    
                    results[statement_name] = data
                    break  # Başarılı olursa döngüden çık, diğer tabloya geç
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning(f"FMP Rate Limit aşıldı ({fmp_ticker}). Bekleniyor...")
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise FMPDataExtractionError(f"HTTP Hatası {e.response.status_code} - {statement_name}")
                except Exception as e:
                    if attempt == self.max_retries:
                        raise FMPDataExtractionError(f"FMP API'sine ulaşılamadı: {str(e)}")
                    await asyncio.sleep(2 ** attempt)

        return results