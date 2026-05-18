import asyncio
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

import pandas as pd
from pydantic import BaseModel, Field

# Core ve Registry Modülleri
from valuation.bist_registry import (
    BistRegistryService,
    TickerConfig
)

from core.exceptions import (
    ValuationPipelineError,
    DataExtractionError
)

# Dispatcher
from valuation.engine.dispatcher import (
    ModelDispatcher,
    HookDispatcher
)

# Extractors (FMP'ye geçiş yapıldı)
from data_pipeline.extractors.fmp_client import (
    FMPExtractor
)

from data_pipeline.extractors.yfinance_client import (
    YFinanceClient
)

from data_pipeline.normalizer import (
    FinancialNormalizer
)

# Core Logic
from valuation.core_logic.normalization import (
    EarningsNormalizer
)

from valuation.core_logic.capex_deduction import (
    CapexDeductor
)

from valuation.core_logic.debt_adjuster import (
    NetDebtAdjuster
)

from valuation.core_logic.floors_multiples import (
    ValuationSafeguards
)

# State Machine
from valuation.engine.state_machine import (
    JobState,
    PipelineStatus,
    StateManager
)

logger = logging.getLogger(__name__)


# =========================================================
# PIPELINE CONTEXT
# =========================================================

class PipelineContext(BaseModel):

    job_id: str
    ticker: str
    config: Any

    df: Optional[Any] = None

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )

    telemetry: Dict[str, float] = Field(
        default_factory=dict
    )

    model_config = {
        "arbitrary_types_allowed": True
    }


# =========================================================
# ORCHESTRATOR
# =========================================================

class ValuationOrchestrator:

    def __init__(
        self,
        state_manager: StateManager
    ):

        # ============================================
        # STATE
        # ============================================

        self.state_manager = state_manager

        # ============================================
        # DISPATCHERS
        # ============================================

        self.model_dispatcher = ModelDispatcher()
        self.hook_dispatcher = HookDispatcher()

        # ============================================
        # EXTRACTORS
        # ============================================

        self.extractor_fmp = FMPExtractor()

        self.extractor_yf = YFinanceClient()

        self.normalizer = FinancialNormalizer()

        # ============================================
        # CORE LOGIC
        # ============================================

        self.earn_normalizer = EarningsNormalizer()

        self.capex_deductor = CapexDeductor()

        self.debt_adjuster = NetDebtAdjuster()

        self.safeguards = ValuationSafeguards()

    # =====================================================
    # TELEMETRY WRAPPER
    # =====================================================

    async def _measure_time(
        self,
        step_name: str,
        context: PipelineContext,
        func,
        *args,
        **kwargs
    ):

        start_time = time.perf_counter()

        try:

            if asyncio.iscoroutinefunction(func):
                result = await func(
                    *args,
                    **kwargs
                )
            else:
                result = func(
                    *args,
                    **kwargs
                )

            elapsed = (
                time.perf_counter()
                - start_time
            )

            context.telemetry[
                f"{step_name}_ms"
            ] = round(elapsed * 1000, 2)

            return result

        except Exception as e:

            elapsed = (
                time.perf_counter()
                - start_time
            )

            context.telemetry[
                f"{step_name}_fail_ms"
            ] = round(elapsed * 1000, 2)

            raise e

    # =====================================================
    # MAIN PIPELINE
    # =====================================================

    async def execute_job(
        self,
        job_id: str,
        ticker: str
    ) -> Dict[str, Any]:

        logger.info(
            f"[{job_id}] "
            f"PIPELINE BAŞLADI: {ticker}"
        )

        await self.state_manager.update_state(
            job_id,
            PipelineStatus.PENDING
        )

        try:

            # =========================================
            # STEP 1
            # =========================================

            config = (
                BistRegistryService
                .get_ticker_config(ticker)
            )

            ctx = PipelineContext(
                job_id=job_id,
                ticker=ticker,
                config=config
            )

            # =========================================
            # STEP 2
            # =========================================

            await self._measure_time(
                "extraction",
                ctx,
                self._step_extract_data,
                ctx
            )

            await self.state_manager.update_state(
                job_id,
                PipelineStatus.DATA_FETCHED
            )

            # =========================================
            # STEP 3
            # =========================================

            await self._measure_time(
                "normalization",
                ctx,
                self._step_normalize_data,
                ctx
            )

            await self.state_manager.update_state(
                job_id,
                PipelineStatus.NORMALIZED
            )

            # =========================================
            # STEP 4
            # =========================================

            await self._measure_time(
                "core_logic",
                ctx,
                self._step_apply_core_logic,
                ctx
            )

            # =========================================
            # STEP 5
            # =========================================

            await self._measure_time(
                "valuation_model",
                ctx,
                self._step_run_valuation_model,
                ctx
            )

            await self.state_manager.update_state(
                job_id,
                PipelineStatus.VALUED
            )

            # =========================================
            # STEP 6
            # =========================================

            await self._measure_time(
                "hooks",
                ctx,
                self._step_apply_hooks,
                ctx
            )

            await self.state_manager.update_state(
                job_id,
                PipelineStatus.HOOKED
            )

            # =========================================
            # STEP 7
            # =========================================

            final_payload = (
                self._build_final_payload(ctx)
            )

            await self.state_manager.update_state(
                job_id,
                PipelineStatus.COMPLETED
            )

            logger.info(
                f"[{job_id}] "
                f"PIPELINE TAMAMLANDI: "
                f"{ticker} "
                f"| Intrinsic Value: "
                f"{final_payload['intrinsic_value']}"
            )

            return final_payload

        except Exception as e:

            error_trace = traceback.format_exc()

            logger.error(
                f"[{job_id}] PIPELINE ÇÖKTÜ: "
                f"{ticker} "
                f"| Hata: {str(e)}\n"
                f"{error_trace}"
            )

            await self.state_manager.update_state(
                job_id,
                PipelineStatus.FAILED,
                error_msg=str(e)
            )

            raise ValuationPipelineError(
                f"Değerleme boru hattı "
                f"{ticker} için başarısız oldu: "
                f"{str(e)}"
            ) from e

    # =====================================================
    # STEP 1 — EXTRACTION
    # =====================================================

    async def _step_extract_data(
        self,
        ctx: PipelineContext
    ):

        timestamp_utc = (
            datetime.now(timezone.utc)
            .isoformat()
        )

        # ============================================
        # CONCURRENT TASKS
        # ============================================

        # İş Yatırım yerine FMP kullanılıyor
        fmp_task = (
            self.extractor_fmp.fetch_financials(
                ticker=ctx.ticker,
                limit=4
            )
        )

        yfinance_task = (
            self.extractor_yf
            .fetch_current_market_data(
                ctx.ticker
            )
        )

        # ============================================
        # PARTIAL FAILURE SAFE GATHER
        # ============================================

        results = await asyncio.gather(
            fmp_task,
            yfinance_task,
            return_exceptions=True
        )

        raw_financials = results[0]

        market_data = results[1]

        # ============================================
        # CRITICAL FAILURE (GRACEFUL DEGRADATION)
        # ============================================
        if isinstance(raw_financials, Exception):
            logger.error(
                f"[{ctx.ticker}] Financial extraction failed: "
                f"{raw_financials}"
            )
            ctx.metadata["financial_extraction_error"] = str(
                raw_financials
            )
            ctx.metadata["raw_financials"] = []
        else:
            ctx.metadata["raw_financials"] = raw_financials

        # ============================================
        # NON-CRITICAL FAILURE
        # ============================================

        if isinstance(
            market_data,
            Exception
        ):

            logger.warning(
                f"[{ctx.ticker}] "
                f"Market data unavailable: "
                f"{market_data}"
            )

            market_data = {
                "current_price": None,
                "market_cap_tl": None,
                "currency": "TRY",
                "source": "fallback",
                "error": str(market_data)
            }

        # ============================================
        # STORE
        # ============================================

        ctx.metadata[
            "extraction_timestamp_utc"
        ] = timestamp_utc

        ctx.metadata["market_data"] = (
            market_data
        )

    # =====================================================
    # STEP 2 — NORMALIZATION
    # =====================================================

    def _step_normalize_data(
        self,
        ctx: PipelineContext
    ):
        
        raw_data = ctx.metadata.get("raw_financials")
        
        # Eğer veri boşsa veya bir Exception objesiyse doğrudan işlemi kes
        if not raw_data or isinstance(raw_data, Exception):
            raise DataExtractionError(
                f"{ctx.ticker} için finansal veri alınamadı. İşlem durduruldu."
            )

        # FMP verisine uygun normalizer fonksiyonu çağrılıyor
        df, meta = (
            self.normalizer
            .normalize_fmp_payload(
                ticker=ctx.ticker,
                raw_data=raw_data,
                extraction_timestamp_utc=(
                    ctx.metadata[
                        "extraction_timestamp_utc"
                    ]
                )
            )
        )

        ctx.df = df

        ctx.metadata.update(meta)

        del ctx.metadata["raw_financials"]

    # =====================================================
    # STEP 3 — CORE LOGIC
    # =====================================================

    def _step_apply_core_logic(
        self,
        ctx: PipelineContext
    ):

        ctx.df, ctx.metadata = (
            self.earn_normalizer
            .normalize_earnings(
                ctx.df,
                ctx.metadata,
                ctx.config.archetype
            )
        )

        ctx.df, ctx.metadata = (
            self.capex_deductor
            .apply_capex_deduction(
                ctx.df,
                ctx.metadata,
                ctx.config.archetype,
                ctx.config.reporting_template
            )
        )

        ctx.df, ctx.metadata = (
            self.debt_adjuster
            .adjust_for_net_debt(
                ctx.df,
                ctx.metadata,
                ctx.config.archetype,
                ctx.config.reporting_template
            )
        )

        ctx.df, ctx.metadata = (
            self.safeguards
            .apply_safeguards(
                ctx.df,
                ctx.metadata,
                ctx.config.archetype,
                ctx.config.reporting_template,
                company_hist_multiple=7.5,
                sector_med_multiple=8.2
            )
        )

    # =====================================================
    # STEP 4 — VALUATION MODEL
    # =====================================================

    async def _step_run_valuation_model(
        self,
        ctx: PipelineContext
    ):

        model = (
            self.model_dispatcher
            .get_model(ctx.config.sector)
        )

        intrinsic_value, report = (
            model.calculate_intrinsic_value(
                ctx.df,
                ctx.metadata
            )
        )

        ctx.metadata[
            "base_intrinsic_value"
        ] = intrinsic_value

        ctx.metadata[
            "model_report"
        ] = report

    # =====================================================
    # STEP 5 — HOOKS
    # =====================================================

    async def _step_apply_hooks(
        self,
        ctx: PipelineContext
    ):

        hook_class = (
            self.hook_dispatcher
            .get_hook(ctx.config.sector)
        )

        macro_data = (
            ctx.metadata.get(
                "macro_context",
                {}
            )
        )

        adjusted_value, hook_report = (
            hook_class.apply_market_regime(
                base_intrinsic_value_tl=(
                    ctx.metadata.get(
                        "base_intrinsic_value",
                        0.0
                    )
                ),
                metadata=ctx.metadata,
                macro_context=macro_data
            )
        )

        ctx.metadata[
            "final_intrinsic_value"
        ] = adjusted_value

        ctx.metadata[
            "hook_adjustments"
        ] = hook_report

    # =====================================================
    # FINAL PAYLOAD
    # =====================================================

    def _build_final_payload(
        self,
        ctx: PipelineContext
    ) -> Dict[str, Any]:

        current_price = (
            ctx.metadata
            .get("market_data", {})
            .get("current_price", 1.0)
        )

        final_value = (
            ctx.metadata.get(
                "final_intrinsic_value",
                0.0
            )
        )

        upside_pct = 0.0

        if current_price and current_price > 0:

            upside_pct = round(
                (
                    (
                        final_value
                        / current_price
                    ) - 1
                ) * 100,
                2
            )

        return {
            "job_id": ctx.job_id,
            "ticker": ctx.ticker,
            "sector": ctx.config.sector.value,
            "archetype": (
                ctx.config.archetype.value
            ),
            "current_price": current_price,
            "base_intrinsic_value": (
                ctx.metadata.get(
                    "base_intrinsic_value"
                )
            ),
            "intrinsic_value": final_value,
            "upside_potential_pct": upside_pct,
            "valuation_metadata": (
                ctx.metadata
            ),
            "telemetry": ctx.telemetry
        }