import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# ==========================================
# 1. CUSTOM EXCEPTIONS (Özelleştirilmiş Hatalar)
# ==========================================
class ExtractorError(Exception):
    pass

class APIUnavailableError(ExtractorError):
    pass

class RateLimitError(ExtractorError):
    pass

class EmptyFinancialDataError(ExtractorError):
    pass

class MalformedResponseError(ExtractorError):
    pass

# ==========================================
# 2. PYDANTIC SCHEMAS (Domain Objects & Validation)
# ==========================================
class FinancialRecord(BaseModel):
    itemCode: str
    itemDescTr: str
    itemDescEng: str
    model_config = {"extra": "allow"}

class IsYatirimResponse(BaseModel):
    """API yanıtının ana şeması - WAF hatalarını yakalamak için esnetildi"""
    value: Optional[List[FinancialRecord]] = None
    ok: Optional[bool] = None          # İş Yatırım WAF engeli için eklendi
    errorCode: Optional[str] = None    # İş Yatırım WAF engeli için eklendi

# ==========================================
# 3. TRANSPORT & EXTRACTION LAYER
# ==========================================
class IsYatirimExtractor:
    
    BASE_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"
    
    HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        # Bot korumasını aşmaya yardımcı olabilecek ekstra başlıklar:
        "Referer": "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(self, max_retries: int = 3, max_concurrent_requests: int = 5):
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        self._timeout = httpx.Timeout(
            connect=5.0,
            read=15.0,
            write=5.0,
            pool=10.0
        )
        self.client = httpx.AsyncClient(timeout=self._timeout, headers=self.HEADERS)

    async def close(self):
        await self.client.aclose()

    async def fetch_financials(self, ticker: str, periods: List[Dict[str, str]], financial_group: str) -> List[Dict[str, Any]]:
        
        params = {
            "companyCode": ticker,
            "exchange": "TRY",
            "financialGroup": financial_group
        }

        for idx, period_data in enumerate(periods[:4], start=1):
            params[f"year{idx}"] = period_data["year"]
            params[f"period{idx}"] = period_data["period"]

        async with self._semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await self.client.get(self.BASE_URL, params=params)
                    
                    if "application/json" not in response.headers.get("Content-Type", ""):
                        raise MalformedResponseError(f"Beklenmeyen Content-Type: {response.headers.get('Content-Type')}")

                    response.raise_for_status()
                    raw_json = response.json()
                    
                    # 2. Pydantic ile Schema Validation
                    validated_payload = IsYatirimResponse(**raw_json)
                    
                    # İŞ YATIRIM GİZLİ WAF ENGELİ KONTROLÜ
                    if validated_payload.ok is False:
                        raise APIUnavailableError(f"İş Yatırım güvenlik engeli (WAF) veya Cookie hatası. Kod: {validated_payload.errorCode}")
                    
                    if not validated_payload.value:
                        raise EmptyFinancialDataError(f"{ticker} için {periods} döneminde veri bulunamadı.")

                    return [record.model_dump() for record in validated_payload.value]

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status not in self.RETRYABLE_STATUS_CODES:
                        logger.error(f"Kalıcı HTTP hatası ({status}) - Ticker: {ticker}")
                        raise APIUnavailableError(f"HTTP {status}") from e
                    await self._handle_retry_backoff(attempt, ticker, f"HTTP {status}")

                except httpx.RequestError as e:
                    await self._handle_retry_backoff(attempt, ticker, "Ağ/Bağlantı Hatası")
                
                except ValidationError as e:
                    logger.error(f"Schema Validation Error ({ticker}): {e}")
                    raise MalformedResponseError("API yanıtı domain şemasına uymuyor.") from e

            raise APIUnavailableError(f"{ticker} için {self.max_retries} deneme başarısız oldu.")

    async def _handle_retry_backoff(self, attempt: int, ticker: str, reason: str):
        if attempt == self.max_retries:
            return 
            
        base_delay = 2 ** attempt
        jitter = random.uniform(-0.25, 0.25) * base_delay
        sleep_time = max(0, base_delay + jitter)
        
        logger.warning(f"[Deneme {attempt}/{self.max_retries}] {ticker} başarısız ({reason}). {sleep_time:.2f} sn bekleniyor...")
        await asyncio.sleep(sleep_time)