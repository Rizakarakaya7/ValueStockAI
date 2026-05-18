import asyncio
import logging
import random
from typing import Dict, Any, Optional
import yfinance as yf
from pydantic import BaseModel, Field, ValidationError

# Sadece modül seviyesinde logger
logger = logging.getLogger(__name__)

# ==========================================
# 1. CUSTOM EXCEPTIONS
# ==========================================
class YFinanceExtractorError(Exception):
    """YFinance işlemleri için temel hata sınıfı."""
    pass

class MarketDataMissingError(YFinanceExtractorError):
    pass

class YFinanceAPIError(YFinanceExtractorError):
    pass


# ==========================================
# 2. PYDANTIC SCHEMAS (Domain Objects)
# ==========================================
class MarketDataResponse(BaseModel):
    """Orkestratör'e dönecek olan anlık piyasa verisi şeması."""
    current_price: Optional[float] = Field(default=None, description="Anlık hisse fiyatı")
    market_cap_tl: Optional[float] = Field(default=None, description="Piyasa değeri (TL)")
    currency: str = Field(default="TRY")
    source: str = Field(default="Yahoo_Finance")
    error: Optional[str] = Field(default=None, description="Hata varsa detayı")


# ==========================================
# 3. EXTRACTION LAYER (Async Wrapper)
# ==========================================
class YFinanceClient:
    """
    Yahoo Finance üzerinden anlık fiyatı ve temel piyasa verilerini çeker.
    Senkron kütüphaneyi (yfinance) Thread Pool içinde çalıştırarak 
    Event Loop'u bloklamasını (darboğaz yaratmasını) engeller.
    """

    def __init__(self, max_retries: int = 3, max_concurrent_requests: int = 5):
        self.max_retries = max_retries
        # Yahoo Finance'in IP Ban (429 Too Many Requests) riskine karşı Semaphore
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    def _get_price_sync(self, yf_ticker: str) -> Dict[str, Any]:
        """
        Senkron çalışan, arka planda (Thread içinde) koşturulacak asıl fonksiyon.
        """
        try:
            stock = yf.Ticker(yf_ticker)
            
            # NOT: '.info' metodu devasa veri indirir ve çok yavaştır. 
            # '.fast_info' sadece anlık fiyat ve market_cap gibi verileri milisaniyeler içinde çeker.
            fast_info = stock.fast_info
            
            last_price = fast_info.get("last_price")
            market_cap = fast_info.get("market_cap")

            if last_price is None:
                raise MarketDataMissingError(f"{yf_ticker} için fiyat verisi bulunamadı (Delist veya geçersiz kod olabilir).")

            return {
                "current_price": float(last_price),
                "market_cap_tl": float(market_cap) if market_cap else None,
                "currency": "TRY",
                "source": "Yahoo_Finance"
            }
            
        except Exception as e:
            # YFinance'in fırlattığı karmaşık hataları kendi Exception'ımıza sarıyoruz (Wrap)
            raise YFinanceAPIError(str(e)) from e

    async def fetch_current_market_data(self, ticker: str) -> Dict[str, Any]:
        """
        Şirketin anlık hisse fiyatını çeker. Hata durumunda retries uygular, 
        başarısız olursa sistemi patlatmadan None/Error dönerek Orkestratörü uyarır.
        """
        yf_ticker = f"{ticker}.IS"  # BİST şirketleri için zorunlu uzantı
        
        async with self._semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    # Senkron fonksiyonu Event Loop'u bloklamaması için ayrı bir Thread'e atıyoruz
                    raw_data = await asyncio.to_thread(self._get_price_sync, yf_ticker)
                    
                    # Pydantic ile doğrulama
                    validated_payload = MarketDataResponse(**raw_data)
                    return validated_payload.model_dump()

                except YFinanceAPIError as e:
                    logger.warning(f"YFinance API Hatası ({yf_ticker}): {e}")
                    await self._handle_retry_backoff(attempt, ticker, "API Reddi/Hatası")
                    
                except MarketDataMissingError as e:
                    logger.error(f"Piyasa verisi eksik ({yf_ticker}): {e}")
                    # Delist olmuş bir hisse için beklemenin anlamı yok, direkt hata paketi dön
                    break 
                
                except ValidationError as e:
                    logger.error(f"Schema Validation Error ({ticker}): {e}")
                    break

            # Tüm denemeler başarısız olduysa Orkestratörü çökertmek yerine güvenli bir hata şeması dönüyoruz.
            logger.error(f"[{ticker}] YFinance'ten veri çekilemedi. Tüm denemeler ({self.max_retries}) tükendi.")
            fallback_response = MarketDataResponse(
                current_price=None,
                market_cap_tl=None,
                error=f"YFinance {self.max_retries} deneme sonunda yanıt vermedi."
            )
            return fallback_response.model_dump()

    async def _handle_retry_backoff(self, attempt: int, ticker: str, reason: str):
        """Exponential backoff with Jitter (is_yatirim.py ile birebir aynı mantık)"""
        if attempt == self.max_retries:
            return 
            
        base_delay = 2 ** attempt
        jitter = random.uniform(-0.25, 0.25) * base_delay
        sleep_time = max(0, base_delay + jitter)
        
        logger.debug(f"[YFinance Deneme {attempt}/{self.max_retries}] {ticker} başarısız ({reason}). {sleep_time:.2f} sn bekleniyor...")
        await asyncio.sleep(sleep_time)