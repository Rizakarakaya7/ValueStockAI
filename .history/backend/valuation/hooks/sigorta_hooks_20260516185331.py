import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SigortaHook:
    @staticmethod
    def apply_market_regime(base_intrinsic_value_tl: float, metadata: Dict[str, Any], macro_context: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Sigorta Hook: Faiz getirisi ve Hasar enflasyonu taranıyor.")
        
        if base_intrinsic_value_tl <= 0: return base_intrinsic_value_tl, {}

        total_adjustment_pct = 0.0
        hook_report = {"applied_adjustments": []}

        # KURAL 1: TAHVİL/MEVDUAT FAİZLERİ (FLOAT GETİRİSİ)
        # Faizler artarsa şirket yatırım portföyünden havadan para kazanır.
        interest_rate_trend = macro_context.get("tr_interest_rate_trend", "stable")
        if interest_rate_trend == "sharp_increase":
            premium = 0.15
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({"factor": "High Yield on Float Portfolio", "impact_pct": premium * 100})

        # KURAL 2: OTO/SAĞLIK YEDEK PARÇA ENFLASYONU (Hasar/Prim Oranı Baskısı)
        # Eğer yedek parça ve hastane maliyetleri poliçe zammından hızlı artıyorsa sistem kanar.
        claims_inflation_pressure = macro_context.get("auto_health_claims_inflation", "low")
        if claims_inflation_pressure == "severe":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Severe Claims/Severity Inflation", "impact_pct": penalty * 100})

        # KURAL 3: SİSTEMİK FELAKET RİSKİ (Catastrophe Risk)
        # Örn: Yakın zamanda büyük deprem/sel olmuşsa reasürans maliyetleri fırlar.
        catastrophe_environment = macro_context.get("catastrophe_risk_environment", "normal")
        if catastrophe_environment == "elevated":
            penalty = -0.12
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Elevated Reinsurance & Catastrophe Costs", "impact_pct": penalty * 100})

        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        return adjusted_value, hook_report