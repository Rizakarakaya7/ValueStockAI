import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class IcecekHook:
    """
    İÇECEK SEKTÖRÜ PİYASA REJİMİ KANCASI
    Turizm etkisi, hammadde (Şeker/Pet/Alüminyum) şokları, ÖTV riskleri 
    ve yurt dışı operasyonel riskleri (AEFES/CCOLA/ULKER vb.) yönetir.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] İçecek Makro Hook devrede. Yurt dışı ve Maliyet riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: YURT DIŞI OPERASYONEL RİSK (International Exposure)
        # AEFES, CCOLA, ULKER gibi şirketlerin yurt dışı (Rusya, MENA, BDT) operasyonları 
        # yüksek jeopolitik ve kur riski taşır.
        international_exposure_tickers = ["AEFES", "CCOLA", "ULKER"] 
        if ticker in international_exposure_tickers:
            penalty = -0.10 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Geopolitical / FX Risk (International Ops)", "impact_pct": penalty * 100
            })

        # KURAL 2: TURİZM SEZONU BEKLENTİSİ (Volume Driver)
        tourism_trend = macro_context.get("tr_tourism_season_forecast", "stable").lower()
        if tourism_trend == "record_high":
            premium = 0.12 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Record High Tourism Expectations (Volume Boom)", "impact_pct": premium * 100
            })
        elif tourism_trend == "contraction":
            penalty = -0.10 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Tourism Contraction (Volume Shrinkage)", "impact_pct": penalty * 100
            })

        # KURAL 3: HAMMADDE (COMMODITY) ŞOKLARI
        commodity_cost_trend = macro_context.get("soft_commodities_cost_trend", "stable").lower()
        if commodity_cost_trend == "spike":
            penalty = -0.08
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Raw Material Cost Spike (Sugar/Aluminum/PET)", "impact_pct": penalty * 100
            })
        elif commodity_cost_trend == "drop":
            premium = 0.08
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Falling Raw Material Costs (Margin Expansion)", "impact_pct": premium * 100
            })

        # KURAL 4: REGÜLATİF VERGİ BASKISI (ÖTV / SCT Risk)
        excise_tax_risk = macro_context.get("excise_tax_hike_risk", "low").lower()
        if excise_tax_risk == "high":
            penalty = -0.15
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "High Excise Tax (ÖTV) Hike Risk", "impact_pct": penalty * 100
            })

        # CLAMPING: Defansif bir sektör olduğu için kanca etkisi limitli tutulur (-%25 ile +%20).
        total_adjustment_pct = max(-0.25, min(0.20, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report