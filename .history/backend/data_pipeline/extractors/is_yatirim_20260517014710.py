import asyncio
import logging
import random

from typing import List, Dict, Any, Optional

from curl_cffi.requests import AsyncSession

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

    model_config = {
        "extra": "allow"
    }


class IsYatirimResponse(BaseModel):

    value: Optional[
        List[FinancialRecord]
    ] = None

    ok: Optional[bool] = None

    errorCode: Optional[str] = None


# =========================================================
# EXTRACTOR
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

        self._semaphore = asyncio.Semaphore(
            max_concurrent_requests
        )

        # =================================================
        # CURL_CFFI SESSION
        # =================================================

        self.session = AsyncSession(
            impersonate="chrome124",
            timeout=30
        )

        self._session_initialized = False

    async def close(self):

        await self.session.close()

    # =====================================================
    # SESSION BOOTSTRAP
    # =====================================================

    async def _initialize_session(self):

        if self._session_initialized:
            return

        try:

            response = await self.session.get(
                self.BOOTSTRAP_URL
            )

            if response.status_code != 200:

                raise APIUnavailableError(
                    f"Bootstrap HTTP "
                    f"{response.status_code}"
                )

            self._session_initialized = True

            logger.info(
                "İş Yatırım session bootstrap başarılı."
            )

        except Exception as e:

            logger.error(
                f"Bootstrap başarısız: {e}"
            )

            raise

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

        for idx, period_data in enumerate(
            periods[:4],
            start=1
        ):

            params[f"year{idx}"] = (
                period_data["year"]
            )

            params[f"period{idx}"] = (
                period_data["period"]
            )

        async with self._semaphore:

            for attempt in range(
                1,
                self.max_retries + 1
            ):

                try:

                    response = (
                        await self.session.get(
                            self.BASE_URL,
                            params=params,
                            headers={
                                "Referer": (
                                    self.BOOTSTRAP_URL
                                ),
                                "X-Requested-With":
                                    "XMLHttpRequest"
                            }
                        )
                    )

                    if response.status_code != 200:

                        raise APIUnavailableError(
                            f"HTTP "
                            f"{response.status_code}"
                        )

                    raw_json = response.json()

                    validated = (
                        IsYatirimResponse(
                            **raw_json
                        )
                    )

                    # =====================================
                    # WAF DETECT
                    # =====================================

                    if validated.ok is False:

                        logger.warning(
                            f"WAF detected "
                            f"({validated.errorCode})"
                        )

                        self._session_initialized = False

                        await self._initialize_session()

                        if (
                            attempt
                            < self.max_retries
                        ):

                            await asyncio.sleep(
                                2
                            )

                            continue

                        raise APIUnavailableError(
                            f"WAF blocked: "
                            f"{validated.errorCode}"
                        )

                    if not validated.value:

                        raise EmptyFinancialDataError(
                            f"{ticker} "
                            f"financial data empty."
                        )

                    return [
                        record.model_dump()
                        for record
                        in validated.value
                    ]

                except ValidationError as e:

                    raise MalformedResponseError(
                        f"Pydantic validation error: {e}"
                    ) from e

                except Exception as e:

                    logger.warning(
                        f"[{ticker}] "
                        f"Attempt {attempt} failed: "
                        f"{e}"
                    )

                    if (
                        attempt
                        == self.max_retries
                    ):
                        raise

                    delay = (
                        (2 ** attempt)
                        + random.uniform(0, 1)
                    )

                    await asyncio.sleep(delay)

        raise APIUnavailableError(
            f"{ticker} extraction failed."
        )