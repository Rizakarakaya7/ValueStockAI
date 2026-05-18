import asyncio
import logging
import random
from typing import Dict, Any, Optional

import yfinance as yf
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class YFinanceExtractorError(Exception):
    pass


class MarketDataResponse(BaseModel):
    current_price: Optional[float] = Field(default=None)
    market_cap_tl: Optional[float] = Field(default=None)
    currency: str = Field(default="TRY")
    source: str = Field(default="Yahoo_Finance")
    error: Optional[str] = None


class YFinanceClient:

    def __init__(
        self,
        max_retries: int = 3,
        max_concurrent_requests: int = 5
    ):
        self.max_retries = max_retries

        self._semaphore = asyncio.Semaphore(
            max_concurrent_requests
        )

    def _get_price_sync(
        self,
        yf_ticker: str
    ) -> Dict[str, Any]:

        stock = yf.Ticker(yf_ticker)

        last_price = None
        market_cap = None

        # ============================================
        # PRIMARY
        # ============================================

        try:
            fast_info = stock.fast_info

            last_price = (
                fast_info.get("last_price")
                or fast_info.get("regularMarketPrice")
            )

            market_cap = (
                fast_info.get("market_cap")
            )

        except Exception as e:
            logger.warning(
                f"fast_info başarısız "
                f"({yf_ticker}): {e}"
            )

        # ============================================
        # FALLBACK #1
        # ============================================

        if last_price is None:

            try:
                hist = stock.history(period="5d")

                if not hist.empty:
                    last_price = float(
                        hist["Close"].iloc[-1]
                    )

            except Exception as e:
                logger.warning(
                    f"history fallback başarısız "
                    f"({yf_ticker}): {e}"
                )

        # ============================================
        # FALLBACK #2
        # ============================================

        if last_price is None:

            try:
                info = stock.info

                last_price = (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                )

                market_cap = (
                    market_cap
                    or info.get("marketCap")
                )

            except Exception as e:
                logger.warning(
                    f"info fallback başarısız "
                    f"({yf_ticker}): {e}"
                )

        if last_price is None:
            raise YFinanceExtractorError(
                f"{yf_ticker} için fiyat verisi alınamadı."
            )

        return {
            "current_price": float(last_price),
            "market_cap_tl": (
                float(market_cap)
                if market_cap
                else None
            ),
            "currency": "TRY",
            "source": "Yahoo_Finance"
        }

    async def fetch_current_market_data(
        self,
        ticker: str
    ) -> Dict[str, Any]:

        yf_ticker = f"{ticker}.IS"

        async with self._semaphore:

            for attempt in range(
                1,
                self.max_retries + 1
            ):

                try:
                    raw_data = await asyncio.to_thread(
                        self._get_price_sync,
                        yf_ticker
                    )

                    validated = MarketDataResponse(
                        **raw_data
                    )

                    return validated.model_dump()

                except Exception as e:

                    logger.warning(
                        f"YFinance hata "
                        f"({yf_ticker}) "
                        f"| Attempt {attempt} "
                        f"| {e}"
                    )

                    await self._handle_retry_backoff(
                        attempt
                    )

            logger.error(
                f"{yf_ticker} market data alınamadı."
            )

            return MarketDataResponse(
                error="Market data unavailable."
            ).model_dump()

    async def _handle_retry_backoff(
        self,
        attempt: int
    ):
        if attempt == self.max_retries:
            return

        base_delay = 2 ** attempt

        jitter = random.uniform(
            -0.25,
            0.25
        ) * base_delay

        await asyncio.sleep(
            max(0, base_delay + jitter)
        )