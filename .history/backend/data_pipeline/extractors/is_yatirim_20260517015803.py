import asyncio
import logging
import random
import urllib.parse
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

# =========================================================
# EXCEPTIONS
# =========================================================

class ExtractorError(Exception):
    pass

class APIUnavailableError(ExtractorError):
    pass

class EmptyFinancialDataError(ExtractorError):
    pass

class MalformedResponseError(ExtractorError):
    pass

# =========================================================
# SCHEMAS
# =========================================================

class FinancialRecord(BaseModel):
    itemCode: str
    itemDescTr: Optional[str] = None
    itemDescEng: Optional[str] = None
    model_config = {"extra": "allow"}

class IsYatirimResponse(BaseModel):
    value: Optional[List[FinancialRecord]] = None
    ok: Optional[bool] = None
    errorCode: Optional[str] = None

# =========================================================
# EXTRACTOR (PLAYWRIGHT)
# =========================================================

class IsYatirimExtractor:

    BASE_URL = (
        "https://www.isyatirim.com.tr/"
        "_layouts/15/IsYatirim.Website/"
        "Common/Data.aspx/MaliTablo"
    )

    BOOTSTRAP_URL = (
        "https://www.isyatirim.com.tr/"
        "tr-tr/analiz/hisse/"
        "Sayfalar/default.aspx"
    )

    def __init__(
        self,
        max_retries: int = 3,
        max_concurrent_requests: int = 5
    ):
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Playwright nesneleri
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._session_initialized = False

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # =====================================================
    # SESSION BOOTSTRAP (WAF BYPASS)
    # =====================================================

    async def _initialize_session(self):
        if self._session_initialized:
            return

        try:
            logger.info("Playwright başlatılıyor...")
            self.playwright = await async_playwright().start()
            
            # Headless Chromium başlatıyoruz
            self.browser = await self.playwright.chromium.launch(headless=True)
            
            # Gerçekçi bir tarayıcı profili oluşturuyoruz
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="tr-TR"
            )
            
            self.page = await self.context.new_page()
            
            # Basit anti-bot bypass scripleri (webdriver bayrağını gizleme)
            await self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info("İş Yatırım bootstrap sayfasına gidiliyor (JS Challenge/Cookies için)...")
            
            # networkidle: Sayfadaki tüm ağ istekleri bitene kadar (WAF challenge dahil) bekle
            await self.page.goto(self.BOOTSTRAP_URL, wait_until="networkidle")
            
            # Challenge'ın geçildiğinden emin olmak için kısa bir bekleme
            await asyncio.sleep(2)

            self._session_initialized = True
            logger.info("İş Yatırım Playwright session bootstrap başarılı. WAF aşıldı.")

        except Exception as e:
            logger.error(f"Playwright Bootstrap başarısız: {e}")
            await self.close()
            raise APIUnavailableError(f"Browser başlatılamadı: {e}")

    # =====================================================
    # MAIN FETCH
    # =====================================================

    async def fetch_financials(
        self,
        ticker: str,
        periods: List[Dict[str, str]],
        financial_group: str
    ) -> List[Dict[str, Any]]:

        await self._initialize_session()

        params = {
            "companyCode": ticker,
            "exchange": "TRY",
            "financialGroup": financial_group
        }

        for idx, period_data in enumerate(periods[:4], start=1):
            params[f"year{idx}"] = period_data["year"]
            params[f"period{idx}"] = period_data["period"]

        # Parametreleri URL encode yapıyoruz
        query_string = urllib.parse.urlencode(params)
        target_url = f"{self.BASE_URL}?{query_string}"

        async with self._semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    # DİKKAT: İsteği dışarıdan değil, WAF'ı geçmiş sayfanın İÇİNDEN atıyoruz.
                    # Bu sayede Akamai tüm sensör verilerini ve tarayıcı context'ini doğrular.
                    raw_json = await self.page.evaluate(f'''async () => {{
                        const response = await fetch("{target_url}", {{
                            headers: {{
                                "X-Requested-With": "XMLHttpRequest",
                                "Accept": "application/json"
                            }}
                        }});
                        return await response.json();
                    }}''')

                    validated = IsYatirimResponse(**raw_json)

                    # =====================================
                    # WAF DETECT
                    # =====================================
                    if validated.ok is False:
                        logger.warning(f"WAF detected inside browser ({validated.errorCode})")
                        self._session_initialized = False
                        await self.close() # Browser'ı tamamen kapatıp temizle
                        await self._initialize_session() # Yeni browser ile tekrar dene
                        
                        if attempt < self.max_retries:
                            await asyncio.sleep(2)
                            continue
                            
                        raise APIUnavailableError(f"WAF blocked in browser: {validated.errorCode}")

                    if not validated.value:
                        raise EmptyFinancialDataError(f"{ticker} financial data empty.")

                    return [record.model_dump() for record in validated.value]

                except PlaywrightTimeoutError as e:
                    logger.warning(f"[{ticker}] Playwright Timeout - Attempt {attempt}")
                    if attempt == self.max_retries: raise APIUnavailableError("Playwright timeout") from e
                    await asyncio.sleep(2)

                except ValidationError as e:
                    raise MalformedResponseError(f"Pydantic validation error: {e}") from e

                except Exception as e:
                    logger.warning(f"[{ticker}] Attempt {attempt} failed: {e}")
                    if attempt == self.max_retries:
                        raise APIUnavailableError(f"{ticker} extraction failed in browser.") from e
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)

        raise APIUnavailableError(f"{ticker} extraction failed.")