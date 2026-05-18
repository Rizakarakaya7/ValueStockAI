import asyncio
import logging
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
import pandas as pd
from pydantic import BaseModel, Field

# Core ve Registry Modülleri
from valuation.bist_registry import BistRegistryService, TickerConfig
from core.exceptions import ValuationPipelineError, DataExtractionError

# Yönlendiriciler (Dispatcher) - Sektöre özel Model ve Kancaları bulan fabrikalar
from valuation.engine.dispatcher import ModelDispatcher, HookDispatcher

# Data Pipeline Modülleri (Varsayılan Extractor Interface'leri)
from data_pipeline.extractors.is_yatirim import IsYatirimExtractor
from data_pipeline.extractors.yfinance_client import YFinanceClient
from data_pipeline.normalizer import FinancialNormalizer

# Core Logic (Kantitatif Çekirdek Filtreler) Modülleri
from valuation.core_logic.normalization import EarningsNormalizer
from valuation.core_logic.capex_deduction import CapexDeductor
from valuation.core_logic.debt_adjuster import NetDebtAdjuster
from valuation.core_logic.floors_multiples import ValuationSafeguards

# Durum Makinesi (State Machine) Modülü
from valuation.engine.state_machine import JobState, PipelineStatus, StateManager

logger = logging.getLogger(__name__)

# ==========================================
# 1. PIPELINE CONTEXT (Boru Hattı Bağlamı)
# ==========================================
class PipelineContext(BaseModel):
    """
    Orkestratör içindeki adımlar arasında dolaşan 'Evrensel Veri Taşıyıcısı'.
    Fonksiyonlara 10 farklı parametre geçmek yerine bu Context objesi geçirilir.
    """
    job_id: str
    ticker: str
    config: TickerConfig
    df: Optional[Any] = None # Pandas DataFrame (Pydantic validasyonunu esnetmek için Any)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    telemetry: Dict[str, float] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


# ==========================================
# 2. THE ORCHESTRATOR (Sistemin Ana Şefi)
# ==========================================
class ValuationOrchestrator:
    """
    İstekleri alır, Hisse Haritasına (Registry) bakar, asenkron verileri çeker,
    kantitatif süzgeçleri sırayla çalıştırır, Dispatcher ile doğru Modeli ve Kancayı 
    tetikleyerek Ajanlar (LLM) için nihai JSON paketini üretir.
    """
    
    def __init__(self, state_manager: StateManager):
        # Durum Makinesi (State Manager)
        self.state_manager = state_manager
        
        # Dispatcher (Yönlendirici) Fabrikaları - Singleton
        self.model_dispatcher = ModelDispatcher()
        self.hook_dispatcher = HookDispatcher()
        
        # Veri Çekiciler (Extractors)
        self.extractor_is = IsYatirimExtractor()
        self.extractor_yf = YFinanceClient()
        self.normalizer = FinancialNormalizer()
        
        # Kantitatif Süzgeçler (Core Logic Filters)
        self.earn_normalizer = EarningsNormalizer()
        self.capex_deductor = CapexDeductor()
        self.debt_adjuster = NetDebtAdjuster()
        self.safeguards = ValuationSafeguards()

    async def _measure_time(self, step_name: str, context: PipelineContext, func, *args, **kwargs):
        """Performans izleme (Telemetry) için mikro-zamanlayıcı Wrapper'ı."""
        start_time = time.perf_counter()
        try:
            # Asenkron ve Senkron fonksiyonları dinamik ayırma
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

    # ==========================================
    # ANA ÇALIŞTIRMA AKIŞI (THE PIPELINE)
    # ==========================================
    async def execute_job(self, job_id: str, ticker: str) -> Dict[str, Any]:
        """Bir değerleme işleminin uçtan uca (End-to-End) yaşam döngüsü."""
        
        logger.info(f"[{job_id}] PIPELINE BAŞLADI: {ticker}")
        await self.state_manager.update_state(job_id, PipelineStatus.PENDING)
        
        try:
            # ADIM 1: Yönlendirme ve Kimlik Tespiti (Registry Lookup)
            config = BistRegistryService.get_ticker_config(ticker)
            ctx = PipelineContext(job_id=job_id, ticker=ticker, config=config)
            
            # ADIM 2: Asenkron Veri Toplama (Concurrent Extraction)
            await self._measure_time("extraction", ctx, self._step_extract_data, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.DATA_FETCHED)
            
            # ADIM 3: Veri Rafinerisi (Normalization JSON -> DataFrame)
            await self._measure_time("normalization", ctx, self._step_normalize_data, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.NORMALIZED)
            
            # ADIM 4: Kantitatif Çekirdek Filtreler (Earnings, CapEx, Debt, Floors)
            await self._measure_time("core_logic", ctx, self._step_apply_core_logic, ctx)
            
            # ADIM 5: Sektörel Finansal Model (Dispatcher ile dinamik tahsis)
            await self._measure_time("valuation_model", ctx, self._step_run_valuation_model, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.VALUED)
            
            # ADIM 6: Acı Gerçekler ve Piyasa Rejimi (Dispatcher ile dinamik tahsis)
            await self._measure_time("hooks", ctx, self._step_apply_hooks, ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.HOOKED)
            
            # ADIM 7: Tamamlanma ve Paketleme
            final_payload = self._build_final_payload(ctx)
            await self.state_manager.update_state(job_id, PipelineStatus.COMPLETED)
            
            logger.info(f"[{job_id}] PIPELINE BAŞARIYLA TAMAMLANDI: {ticker} | Hedef Fiyat: {final_payload['intrinsic_value']}")
            return final_payload

        except Exception as e:
            # Kurumsal Hata Yönetimi: Sessizce çökme, iz bırak!
            error_trace = traceback.format_exc()
            logger.error(f"[{job_id}] PIPELINE ÇÖKTÜ: {ticker} | Hata: {str(e)}\n{error_trace}")
            await self.state_manager.update_state(job_id, PipelineStatus.FAILED, error_msg=str(e))
            raise ValuationPipelineError(f"Değerleme boru hattı {ticker} için başarısız oldu: {str(e)}") from e


    # ==========================================
    # ALT ADIM UYGULAMALARI (Step Implementations)
    # ==========================================
    
    async def _step_extract_data(self, ctx: PipelineContext):
        """Tüm dış API'lere aynı anda (Concurrent) istek atarak gecikmeyi (Latency) minimize eder."""
        # TODO: Dynamic period calculator eklenebilir. Şimdilik simülasyon.
        requested_periods = [{"year": "2023", "period": "12"}, {"year": "2023", "period": "9"}] 
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        
        # asyncio.gather ile Bilanço ve Fiyat verisini AYNI ANDA çekeriz.
        is_yatirim_task = self.extractor_is.fetch_financials(ctx.ticker, requested_periods, ctx.config.reporting_template.value)
        yfinance_task = self.extractor_yf.fetch_current_market_data(ctx.ticker)
        
        raw_financials, market_data = await asyncio.gather(is_yatirim_task, yfinance_task)
        
        ctx.metadata["raw_financials"] = raw_financials
        ctx.metadata["actual_periods"] = requested_periods
        ctx.metadata["extraction_timestamp_utc"] = timestamp_utc
        ctx.metadata["market_data"] = market_data

    def _step_normalize_data(self, ctx: PipelineContext):
        """Ham JSON verisini sütunları kronolojik dizilmiş temiz bir Int64 DataFrame'e çevirir."""
        df, meta = self.normalizer.normalize_isyatirim_payload(
            ticker=ctx.ticker,
            raw_data=ctx.metadata["raw_financials"],
            actual_periods=ctx.metadata["actual_periods"],
            extraction_timestamp_utc=ctx.metadata["extraction_timestamp_utc"]
        )
        ctx.df = df
        ctx.metadata.update(meta)
        del ctx.metadata["raw_financials"] # RAM optimizasyonu

    def _step_apply_core_logic(self, ctx: PipelineContext):
        """4 Aşamalı Quant Filtrelerini sırayla uygular (Mutable Pipeline)."""
        
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
            company_hist_multiple=7.5, sector_med_multiple=8.2 # Placeholder
        )

    async def _step_run_valuation_model(self, ctx: PipelineContext):
        """
        [DISPATCHER ENTEGRASYONU] 
        Hissenin sektörüne uygun modeli Fabrikadan ister ve çalıştırır.
        """
        # 1. Modeli Çek
        model = self.model_dispatcher.get_model(ctx.config.sector)
        
        # 2. Çalıştır
        intrinsic_value, report = model.calculate_intrinsic_value(ctx.df, ctx.metadata)
        
        # 3. Sonuçları Kaydet
        ctx.metadata["base_intrinsic_value"] = intrinsic_value
        ctx.metadata["model_report"] = report

    async def _step_apply_hooks(self, ctx: PipelineContext):
        """
        [DISPATCHER ENTEGRASYONU] 
        Hissenin sektörüne uygun Hakikat Tokadını (Hook) Fabrikadan ister ve çalıştırır.
        """
        # 1. Hook Sınıfını Çek
        hook_class = self.hook_dispatcher.get_hook(ctx.config.sector)
        
        # TODO: Macro extractor ileride buraya entegre edilecek.
        macro_data = ctx.metadata.get("macro_context", {}) 
        
        # 2. Makro veriyi ve hesaplanan değeri Hook'a sok
        adjusted_value, hook_report = hook_class.apply_market_regime(
            base_intrinsic_value_tl=ctx.metadata.get("base_intrinsic_value", 0.0), 
            metadata=ctx.metadata, 
            macro_context=macro_data
        )
        
        # 3. Sonuçları Kaydet
        ctx.metadata["final_intrinsic_value"] = adjusted_value
        ctx.metadata["hook_adjustments"] = hook_report

    def _build_final_payload(self, ctx: PipelineContext) -> Dict[str, Any]:
        """Ajanların (LLM) veya Arayüzün (UI) tüketmesi için kusursuz JSON paketini hazırlar."""
        current_price = ctx.metadata.get("market_data", {}).get("current_price", 1.0)
        final_value = ctx.metadata.get("final_intrinsic_value", 0.0)
        
        # Sıfıra bölünme veya 0 fiyattan kaçınma güvenliği
        upside_pct = 0.0
        if current_price and current_price > 0:
            upside_pct = round(((final_value / current_price) - 1) * 100, 2)
            
        return {
            "job_id": ctx.job_id,
            "ticker": ctx.ticker,
            "sector": ctx.config.sector.value,
            "archetype": ctx.config.archetype.value,
            "current_price": current_price,
            "base_intrinsic_value": ctx.metadata.get("base_intrinsic_value"),
            "intrinsic_value": final_value,
            "upside_potential_pct": upside_pct,
            "valuation_metadata": ctx.metadata,
            "telemetry": ctx.telemetry # Performans metrikleri
        }