import asyncio
import logging
import random
from typing import List, Dict, Any
import httpx
from pydantic import BaseModel, ValidationError

# Sadece modül seviyesinde logger (Root override engellendi)
logger = logging.getLogger(__name__)


# ==========================================
# 1. CUSTOM EXCEPTIONS (Özelleştirilmiş Hatalar)
# ==========================================
class ExtractorError(Exception):
    """Data pipeline extractors için temel hata sınıfı."""
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
    """Raw verinin yapısal doğrulaması. ItemCode (Canonical) zorunludur."""
    itemCode: str
    itemDescTr: str
    itemDescEng: str
    # API dinamik olarak value1, value2 döner. Strict type yerine raw string kabul ediyoruz.
    # Precision/Decimal dönüşümleri Normalizer'da yapılacak.
    model_config = {"extra": "allow"}

class IsYatirimResponse(BaseModel):
    """API yanıtının ana şeması"""
    value: List[FinancialRecord]


# ==========================================
# 3. TRANSPORT & EXTRACTION LAYER
# ==========================================
class IsYatirimExtractor:
    """
    İş Yatırım API'sinden Ham (Raw) finansal veriyi çeker.
    Veriyi temizlemez, DataFrame'e çevirmez. Sadece Pydantic ile doğrular ve iletir.
    """
    
    BASE_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"
    
    HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Sadece geçici/sunucu kaynaklı hatalarda Retry yapılır. (400 veya 404'te yapılmaz)
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(self, max_retries: int = 3, max_concurrent_requests: int = 5):
        self.max_retries = max_retries
        
        # Rate-limiting ve IP ban koruması için Semaphore (Aynı anda maks 5 istek)
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Ayrıştırılmış ve profesyonel Timeout modeli
        self._timeout = httpx.Timeout(
            connect=5.0,
            read=15.0,
            write=5.0,
            pool=10.0
        )
        
        # Connection Pool resetlenmemesi için Class-Level Reusable Client
        self.client = httpx.AsyncClient(timeout=self._timeout, headers=self.HEADERS)

    async def close(self):
        """Uygulama kapanırken client bağlantılarını temizler."""
        await self.client.aclose()

    async def fetch_financials(self, ticker: str, periods: List[Dict[str, str]], financial_group: str) -> List[Dict[str, Any]]:
        """
        Raw finansal veriyi çeker ve doğrulanmış domain object listesi olarak döndürür.
        
        Args:
            ticker: Hise kodu (Örn: "TUPRS")
            periods: Dönemler [{"year": "2023", "period": "12"}]
            financial_group: Sektör şablonu (Örn: Sanayi için "XI_29", Banka için "XI_59")
        """
        params = {
            "companyCode": ticker,
            "exchange": "TRY",
            "financialGroup": financial_group  # Hardcoded string kaldırıldı, dinamik yapıldı
        }

        for idx, period_data in enumerate(periods[:4], start=1):
            params[f"year{idx}"] = period_data["year"]
            params[f"period{idx}"] = period_data["period"]

        # Concurrency koruması (Semaphore)
        async with self._semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await self.client.get(self.BASE_URL, params=params)
                    
                    # 1. Content-Type Doğrulaması (HTML/Captcha koruması)
                    if "application/json" not in response.headers.get("Content-Type", ""):
                        raise MalformedResponseError(f"Beklenmeyen Content-Type: {response.headers.get('Content-Type')}")

                    # Hata kodlarını kontrol et
                    response.raise_for_status()
                    
                    raw_json = response.json()
                    
                    # 2. Pydantic ile Schema Validation (Sessiz kırılmaları engeller)
                    validated_payload = IsYatirimResponse(**raw_json)
                    
                    if not validated_payload.value:
                        raise EmptyFinancialDataError(f"{ticker} için {periods} döneminde veri bulunamadı.")

                    # Normalizer katmanına gidecek saf ve doğrulanmış raw payload
                    # (Pydantic modelini tekrar dict'e çeviriyoruz ki bağımlılık yaratmasın)
                    return [record.model_dump() for record in validated_payload.value]

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status not in self.RETRYABLE_STATUS_CODES:
                        # 400 Bad Request veya 404 Not Found ise direkt fırlat, retry yapma
                        logger.error(f"Kalıcı HTTP hatası ({status}) - Ticker: {ticker}")
                        raise APIUnavailableError(f"HTTP {status}") from e
                    
                    await self._handle_retry_backoff(attempt, ticker, f"HTTP {status}")

                except httpx.RequestError as e:
                    await self._handle_retry_backoff(attempt, ticker, "Ağ/Bağlantı Hatası")
                
                except ValidationError as e:
                    # JSON geldi ama beklenen formatta değilse anında patlat
                    logger.error(f"Schema Validation Error ({ticker}): {e}")
                    raise MalformedResponseError("API yanıtı domain şemasına uymuyor.") from e

            # Döngü biterse ve hala dönmediyse
            raise APIUnavailableError(f"{ticker} için {self.max_retries} deneme başarısız oldu.")

    async def _handle_retry_backoff(self, attempt: int, ticker: str, reason: str):
        """Exponential backoff with Jitter (Thundering herd problemini önler)"""
        if attempt == self.max_retries:
            return # Son denemede bekleme yapma, dışarı hata fırlatacak
            
        base_delay = 2 ** attempt
        # Jitter: +/-%25 oranında rastgelelik ekle
        jitter = random.uniform(-0.25, 0.25) * base_delay
        sleep_time = max(0, base_delay + jitter)
        
        logger.warning(f"[Deneme {attempt}/{self.max_retries}] {ticker} başarısız ({reason}). {sleep_time:.2f} sn bekleniyor...")
        await asyncio.sleep(sleep_time)