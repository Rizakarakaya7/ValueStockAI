import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class TeknolojiHook:
    @staticmethod
    def apply_market_regime(base_intrinsic_value_tl: float, metadata: Dict[str, Any], macro_context: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Teknoloji Hook: Global Likidite ve AI Çarpanları taranıyor.")
        
        if base_intrinsic_value_tl <= 0: return base_intrinsic_value_tl, {}

        total_adjustment_pct = 0.0
        hook_report = {"applied_adjustments": []}

        # KURAL 1: GLOBAL LİKİDİTE (NASDAQ & FED FAİZLERİ)
        # Teknoloji şirketleri düşük faiz ortamını sever (Gelecekteki nakitleri değerlenir).
        global_tech_liquidity = macro_context.get("global_tech_liquidity_environment", "neutral")
        if global_tech_liquidity == "expansion":
            premium = 0.15
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({"factor": "Global Tech Rally / Low Yields", "impact_pct": premium * 100})
        elif global_tech_liquidity == "tightening":
            penalty = -0.15
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "High Yield Tech Sell-off", "impact_pct": penalty * 100})

        # KURAL 2: YAPAY ZEKA VE R&D TEŞVİKLERİ (AI Hype Premium)
        # Şirket spesifik metadata'sında "AI Exposure" varsa piyasa çılgın çarpanlar ödemeye razıdır.
        is_ai_exposed = metadata.get("ai_revenue_exposure", False)
        if is_ai_exposed:
            premium = 0.20 # Yapay zeka köpüğü primi
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({"factor": "Artificial Intelligence Hype Premium", "impact_pct": premium * 100})

        # KURAL 3: KURUMSAL IT BÜTÇELERİ
        # Eğer Türkiye'de resesyon varsa şirketler ilk olarak "Yeni yazılım alma" bütçelerini kısarlar.
        corporate_capex_trend = macro_context.get("tr_corporate_capex_trend", "stable")
        if corporate_capex_trend == "contraction":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Frozen Corporate IT Budgets", "impact_pct": penalty * 100})

        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        return adjusted_value, hook_report