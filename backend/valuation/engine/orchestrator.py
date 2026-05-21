# orchestrator.py

import asyncio
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

import pandas as pd
import numpy as np
from pydantic import BaseModel, Field

# Core ve Registry Modülleri
from valuation.bist_registry import BistRegistryService, TickerConfig
from core.exceptions import ValuationPipelineError, DataExtractionError

# Dispatcher
from valuation.engine.dispatcher import ModelDispatcher, HookDispatcher

# Yeni YFinance Motoru
from data_pipeline.extractors.yf_engine import YFinanceEngine
from data_pipeline.normalizer import FinancialNormalizer

# Core Logic
from valuation.core_logic.normalization import EarningsNormalizer
from valuation.core_logic.capex_deduction import CapexDeductor
from valuation.core_logic.debt_adjuster import NetDebtAdjuster
from valuation.core_logic.floors_multiples import ValuationSafeguards

# State Machine
from valuation.engine.state_machine import JobState, PipelineStatus, StateManager

logger = logging.getLogger(__name__)

# =========================================================
# PIPELINE CONTEXT
# =========================================================
class PipelineContext(BaseModel):
    job_id: str
    ticker: str
    config: Any
    df: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    telemetry: Dict[str, float] = Field(default_factory=dict)

    model_config = {
        "arbitrary_types_allowed": True
    }

# =========================================================
# ORCHESTRATOR
# =========================================================
class ValuationOrchestrator:

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.model_dispatcher = ModelDispatcher()
        self.hook_dispatcher = HookDispatcher()
        self.yf_engine = YFinanceEngine()
        self.normalizer = FinancialNormalizer()
        self.earn_normalizer = EarningsNormalizer()
        self.capex_deductor = CapexDeductor()
        self.debt_adjuster = NetDebtAdjuster()
        self.safeguards = ValuationSafeguards()

    async def _measure_time(self, step_name: str, context: PipelineContext, func, *args, **kwargs):
        start_time = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            elapsed = time.perf_counter() - start_time
            context.telemetry[f"{step_name}_ms"] = round(elapsed * 1000, 2)
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            context.telemetry[f"{step_name}_fail_ms"] = round(elapsed * 1000, 2)
            raise e

    async def execute_job(self, job_id: str, ticker: str) -> Dict[str, Any]:
        logger.info(f"[{job_id}] PIPELINE BAŞLADI: {ticker}")
        await self.state_manager.update_state(job_id, PipelineStatus.PENDING)

        try:
            config = BistRegistryService.get_ticker_config(ticker)
            ctx = PipelineContext(job_id=job_id, ticker=ticker, config=config)
            
            # Dinamik modeller ve kancalar (hooks) için arketipi metadata'ya ekliyoruz
            ctx.metadata["archetype"] = config.archetype.value

            await self._measure_time("extraction", ctx, self._step_extract_data, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.DATA_FETCHED)

            await self._measure_time("normalization", ctx, self._step_normalize_data, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.NORMALIZED)

            await self._measure_time("core_logic", ctx, self._step_apply_core_logic, ctx)

            await self._measure_time("valuation_model", ctx, self._step_run_valuation_model, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.VALUED)

            await self._measure_time("hooks", ctx, self._step_apply_hooks, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.HOOKED)

            final_payload = self._build_final_payload(ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.COMPLETED)

            logger.info(f"[{job_id}] PIPELINE TAMAMLANDI: {ticker} | Intrinsic Value: {final_payload.get('intrinsic_company_value')}")
            return final_payload

        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"[{job_id}] PIPELINE ÇÖKTÜ: {ticker} | Hata: {str(e)}\n{error_trace}")
            await self.state_manager.update_state(job_id, PipelineStatus.FAILED, error_msg=str(e))
            raise ValuationPipelineError(f"Değerleme boru hattı {ticker} için başarısız oldu: {str(e)}") from e

    async def _step_extract_data(self, ctx: PipelineContext):
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        try:
            extracted_data = await self.yf_engine.fetch_all_data_async(ctx.ticker)
            raw_financials = extracted_data.get("financials", {})
            market_data = extracted_data.get("market_data", {})
        except Exception as e:
            logger.error(f"[{ctx.ticker}] Data extraction completely failed: {e}")
            raw_financials = e
            market_data = e

        if isinstance(raw_financials, Exception) or not raw_financials:
            logger.error(f"[{ctx.ticker}] Financial extraction failed or empty.")
            ctx.metadata["financial_extraction_error"] = str(raw_financials)
            ctx.metadata["raw_financials"] = {}
        else:
            ctx.metadata["raw_financials"] = raw_financials

        if isinstance(market_data, Exception) or not market_data:
            logger.warning(f"[{ctx.ticker}] Market data unavailable.")
            market_data = {
                "current_price": None,
                "shares_outstanding": None,
                "market_cap_tl": None,
                "currency": "TRY",
                "source": "fallback",
                "error": str(market_data)
            }

        ctx.metadata["extraction_timestamp_utc"] = timestamp_utc
        ctx.metadata["market_data"] = market_data

    def _step_normalize_data(self, ctx: PipelineContext):
        raw_data = ctx.metadata.get("raw_financials")
        if not raw_data or isinstance(raw_data, Exception):
            raise DataExtractionError(f"{ctx.ticker} için finansal veri alınamadı. İşlem durduruldu.")

        df, meta = self.normalizer.normalize_financials(
            ticker=ctx.ticker,
            raw_financials=raw_data,
            extraction_timestamp_utc=ctx.metadata["extraction_timestamp_utc"]
        )

        if df.empty:
            raise DataExtractionError(f"{ctx.ticker} normalize edilecek geçerli bir finansal tablo döndürmedi.")

        ctx.df = df
        ctx.metadata.update(meta)
        del ctx.metadata["raw_financials"]

    def _step_apply_core_logic(self, ctx: PipelineContext):
        ctx.df, ctx.metadata = self.earn_normalizer.normalize_earnings(
            ctx.df, ctx.metadata, ctx.config.archetype
        )
        ctx.df, ctx.metadata = self.capex_deductor.apply_capex_deduction(
            ctx.df, ctx.metadata, ctx.config.archetype, ctx.config.reporting_template
        )
        ctx.df, ctx.metadata = self.debt_adjuster.adjust_for_net_debt(
            ctx.df, ctx.metadata, ctx.config.archetype, ctx.config.reporting_template
        )
        ctx.df, ctx.metadata = self.safeguards.apply_safeguards(
            ctx.df, ctx.metadata, ctx.config.archetype, ctx.config.reporting_template,
            company_hist_multiple=7.5, sector_med_multiple=8.2
        )

    async def _step_run_valuation_model(self, ctx: PipelineContext):
        model = self.model_dispatcher.get_model(ctx.config.sector)
        intrinsic_value, report = model.calculate_intrinsic_value(ctx.df, ctx.metadata)
        
        # --- DİNAMİK SOTP (SUM OF THE PARTS) KONTROLÜ ---
        if ctx.config.archetype.value == "Operational_Holding" and ctx.config.child_stakes:
            logger.info(f"[{ctx.ticker}] Dinamik SOTP (Parçaların Toplamı) Motoru devreye giriyor...")
            try:
                total_subsidiary_value = 0.0
                sotp_details = {}
                
                for child_ticker, stake in ctx.config.child_stakes.items():
                    child_data = await self.yf_engine.fetch_all_data_async(child_ticker)
                    market_data = child_data.get("market_data", {})
                    
                    mcap_tl = market_data.get("market_cap_tl")
                    if not mcap_tl:
                        c_price = market_data.get("current_price")
                        c_shares = market_data.get("shares_outstanding")
                        if c_price and c_shares:
                            mcap_tl = float(c_price) * float(c_shares)
                            
                    if mcap_tl and mcap_tl > 0:
                        stake_val = float(mcap_tl) * stake
                        total_subsidiary_value += stake_val
                        sotp_details[child_ticker] = {"stake_pct": stake * 100, "value_tl": stake_val}
                    else:
                        logger.warning(f"[{ctx.ticker}] SOTP Atlandı: {child_ticker} piyasa değeri hesaplanamadı!")

                if total_subsidiary_value > 0:
                    sotp_value_tl = total_subsidiary_value * 1.25
                    logger.info(f"[{ctx.ticker}] Dinamik SOTP Başarılı! İştirakler Toplamı: {total_subsidiary_value} TL, SOTP Değeri: {sotp_value_tl} TL")
                    
                    intrinsic_value = sotp_value_tl
                    report["model_used"] = "SOTP_Operational_Holding"
                    report["sotp_subsidiaries"] = sotp_details
                    report["core_operations_premium_pct"] = 25
                    
            except Exception as e:
                logger.error(f"[{ctx.ticker}] Dinamik SOTP hesaplaması başarısız oldu, klasik modele dönülüyor: {e}")

        # Zemin Koruması (Safeguards)
        safeguards = ctx.metadata.get("valuation_safeguards", {})
        book_value_floor_cents = safeguards.get("book_value_floor_cents", 0)
        
        if book_value_floor_cents > 0:
            floor_total_value_tl = book_value_floor_cents / 100.0
            
            if intrinsic_value <= 0 or intrinsic_value < floor_total_value_tl:
                logger.info(f"[{ctx.ticker}] DCF Değeri ({intrinsic_value} TL) zemin korumasının altında. Şirket değeri Defter Değeri Tabanına ({floor_total_value_tl} TL) sabitleniyor.")
                report["floor_triggered"] = True
                report["original_model_value"] = intrinsic_value
                intrinsic_value = floor_total_value_tl

        ctx.metadata["base_intrinsic_value"] = intrinsic_value
        ctx.metadata["model_report"] = report

    async def _step_apply_hooks(self, ctx: PipelineContext):
        hook_class = self.hook_dispatcher.get_hook(ctx.config.sector)
        macro_data = ctx.metadata.get("macro_context", {})
        
        try:
            # 1. Aşama: Sektörel Risk ve Veri Türetme (Adım 1'deki yapı)
            if hasattr(hook_class, "apply_sector_adjustments"):
                ctx.metadata = hook_class.apply_sector_adjustments(ctx.metadata)
            
            # 2. Aşama: Makro Rejim (Adım 2'deki yapı)
            adjusted_value, hook_report = hook_class.apply_market_regime(
                base_intrinsic_value_tl=ctx.metadata.get("base_intrinsic_value", 0.0),
                metadata=ctx.metadata,
                macro_context=macro_data
            )
            
            # KONTROL: Hook başarılı mı?
            if hook_report.get("hook_status") == "OK":
                ctx.metadata["final_intrinsic_value"] = adjusted_value
                ctx.metadata["hook_adjustments"] = hook_report
            else:
                raise Exception(f"Hook başarısız: {hook_report.get('hook_status')}")

        except Exception as e:
            logger.error(f"[{ctx.ticker}] Hook uygulaması çöktü: {e}")
            ctx.metadata["final_intrinsic_value"] = ctx.metadata.get("base_intrinsic_value", 0.0)
            ctx.metadata["hook_adjustments"] = {"status": "FAILED", "error": str(e)}
    def _sanitize_for_json(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                str(k) if isinstance(k, pd.Period) else k: self._sanitize_for_json(v) 
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [self._sanitize_for_json(v) for v in obj]
        elif isinstance(obj, pd.Period):
            return str(obj)
        elif pd.isna(obj):
            return None
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        else:
            return obj

    def _build_final_payload(self, ctx: PipelineContext) -> Dict[str, Any]:
        market_data = ctx.metadata.get("market_data", {})
        current_price = market_data.get("current_price")
        shares_outstanding = market_data.get("shares_outstanding")
        
        final_company_value = ctx.metadata.get("final_intrinsic_value", 0.0)
        
        intrinsic_price_per_share = None
        upside_pct = 0.0

        if shares_outstanding and shares_outstanding > 0 and final_company_value:
            intrinsic_price_per_share = final_company_value / shares_outstanding
            
            if current_price and current_price > 0:
                upside_pct = round(((intrinsic_price_per_share / current_price) - 1) * 100, 2)

        sanitized_metadata = self._sanitize_for_json(ctx.metadata)

        return {
            "job_id": ctx.job_id,
            "ticker": ctx.ticker,
            "sector": ctx.config.sector.value,
            "archetype": ctx.config.archetype.value,
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "intrinsic_company_value": final_company_value,
            "intrinsic_price_per_share": intrinsic_price_per_share,
            "upside_potential_pct": upside_pct,
            
            # --- 2. ADIM: AJANLAR İÇİN HAYATİ METRİKLERİ EN ÜSTE TAŞIDIK ---
            "ebitda": ctx.metadata.get("ebitda"),
            "net_debt": ctx.metadata.get("net_debt"),
            "sector_risk_score": ctx.metadata.get("sector_risk_score", 5),
            "sector_risk_flags": ctx.metadata.get("sector_risk_flags", []),
            
            "valuation_metadata": sanitized_metadata,
            "telemetry": ctx.telemetry
        }