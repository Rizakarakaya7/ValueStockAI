import asyncio
import logging
import random
from typing import List, Dict, Any, Optional

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# =========================================================
# CUSTOM EXCEPTIONS
# =========================================================

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


# =========================================================
# PYDANTIC SCHEMAS
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
# EXTRACTOR
# =========================================================

class IsYatirimExtractor:

    BASE_URL = (
        "https://www.isyatirim.com.tr/"
        "_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"
    )

    BOOTSTRAP_URL = (
        "https://www.isyatirim.com.tr/"
        "tr-tr/analiz/hisse/Sayfalar/default.aspx"
    )

    HEADERS = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": (
            "https://www.isyatirim.com.tr/"
            "tr-tr/analiz/hisse/Sayfalar/default.aspx"
        ),
        "Origin": "https://www.isyatirim.com.tr",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }

    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(
        self,
        max_retries: int = 3,
        max_concurrent_requests: int = 5
    ):
        self.max_retries = max_retries

        self._semaphore = asyncio.Semaphore(
            max_concurrent_requests
        )

        self._timeout = httpx.Timeout(
            connect=5.0,
            read=20.0,
            write=5.0,
            pool=15.0
        )

        self.client = httpx.AsyncClient(
            timeout=self._timeout,
            headers=self.HEADERS,
            http2=True,
            follow_redirects=True
        )

        self._session_initialized = False

    async def close(self):
        await self.client.aclose()

    async def _initialize_session(self):
        """
        İş Yatırım WAF bypass için
        önce ana sayfadan cookie/session oluşturur.
        """

        if self._session_initialized:
            return

        try:
            response = await self.client.get(
                self.BOOTSTRAP_URL
            )

            response.raise_for_status()

            self._session_initialized = True

            logger.info(
                "İş Yatırım session bootstrap başarılı."
            )

        except Exception as e:
            logger.warning(
                f"Session bootstrap başarısız: {e}"
            )

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

        for idx, period_data in enumerate(
            periods[:4],
            start=1
        ):
            params[f"year{idx}"] = period_data["year"]
            params[f"period{idx}"] = period_data["period"]

        async with self._semaphore:

            for attempt in range(
                1,
                self.max_retries + 1
            ):

                try:
                    response = await self.client.get(
                        self.BASE_URL,
                        params=params
                    )

                    response.raise_for_status()

                    content_type = response.headers.get(
                        "Content-Type",
                        ""
                    )

                    if "application/json" not in content_type:
                        raise MalformedResponseError(
                            f"Beklenmeyen Content-Type: "
                            f"{content_type}"
                        )

                    raw_json = response.json()

                    validated_payload = (
                        IsYatirimResponse(**raw_json)
                    )

                    # =================================================
                    # WAF DETECTION
                    # =================================================

                    if validated_payload.ok is False:

                        logger.warning(
                            f"WAF response alındı "
                            f"({validated_payload.errorCode}) "
                            f"- Session resetleniyor."
                        )

                        self._session_initialized = False

                        await self._initialize_session()

                        if attempt < self.max_retries:
                            await asyncio.sleep(1.5)
                            continue

                        raise APIUnavailableError(
                            f"İş Yatırım güvenlik engeli: "
                            f"{validated_payload.errorCode}"
                        )

                    if not validated_payload.value:
                        raise EmptyFinancialDataError(
                            f"{ticker} için finansal veri boş."
                        )

                    return [
                        record.model_dump()
                        for record in validated_payload.value
                    ]

                except httpx.HTTPStatusError as e:

                    status = e.response.status_code

                    if (
                        status
                        not in self.RETRYABLE_STATUS_CODES
                    ):
                        raise APIUnavailableError(
                            f"HTTP {status}"
                        ) from e

                    await self._handle_retry_backoff(
                        attempt,
                        ticker,
                        f"HTTP {status}"
                    )

                except httpx.RequestError:
                    await self._handle_retry_backoff(
                        attempt,
                        ticker,
                        "Network Error"
                    )

                except ValidationError as e:
                    logger.error(
                        f"Schema Validation Error "
                        f"({ticker}): {e}"
                    )

                    raise MalformedResponseError(
                        "API response invalid."
                    ) from e

            raise APIUnavailableError(
                f"{ticker} için "
                f"{self.max_retries} deneme başarısız."
            )

    async def _handle_retry_backoff(
        self,
        attempt: int,
        ticker: str,
        reason: str
    ):
        if attempt == self.max_retries:
            return

        base_delay = 2 ** attempt

        jitter = random.uniform(
            -0.25,
            0.25
        ) * base_delay

        sleep_time = max(
            0,
            base_delay + jitter
        )

        logger.warning(
            f"[{ticker}] Retry "
            f"{attempt}/{self.max_retries} "
            f"| Sebep: {reason} "
            f"| Bekleme: {sleep_time:.2f}s"
        )

        await asyncio.sleep(sleep_time)