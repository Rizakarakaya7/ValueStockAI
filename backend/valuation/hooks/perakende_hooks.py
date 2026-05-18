import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class PerakendeHook:
    """
    PERAKENDE SEKTÖRÜ PİYASA REJİMİ KANCASI
    Asgari ücret şokları, Tüketici Güven Endeksi ve Regülatif cezalar gibi 
    iç pazar dinamiklerini matematiksel değere yansıtır.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Perakende Makro Hook devrede. Enflasyon ve Asgari Ücret taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0
        is_regulated = metadata.get("regulated_business", False)

        # KURAL 1: ASGARİ ÜCRET ŞOKU (Minimum Wage Surge)
        # Perakendeciler on binlerce personeli asgari ücretle çalıştırır. Beklenmedik yüksek zamlar marjları yutar.
        min_wage_hike_surprise = macro_context.get("min_wage_hike_surprise_pct", 0.0)
        
        if min_wage_hike_surprise > 10.0:
            # Beklentinin %10 üzerinde asgari ücret zammı geldi. Kâr marjları daralacak.
            penalty = -0.08
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Minimum Wage Shock Margin Squeeze", "impact_pct": penalty * 100
            })

        # KURAL 2: TÜKETİCİ GÜVENİ VE REEL SATIN ALMA GÜCÜ
        # Gıda enflasyonu varsa ciro nominal artar, ancak alım gücü çökerse sepet küçülür (Volume drop).
        consumer_confidence = macro_context.get("tr_consumer_confidence_index", 75.0)
        
        if consumer_confidence < 60.0:
            penalty = -0.05
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Consumer Purchasing Power Drop", "impact_pct": penalty * 100
            })
        elif consumer_confidence > 85.0:
            premium = 0.05
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong Consumer Volume Expansion", "impact_pct": premium * 100
            })

        # KURAL 3: REGÜLASYON VE CEZA RİSKİ (Politik Basınç)
        # Enflasyonist dönemlerde hükümetler faturaları zincir marketlere kesme eğilimindedir (Tavan fiyat, rekabet cezası).
        regulatory_pressure = macro_context.get("retail_regulatory_pressure_level", "low")
        
        if regulatory_pressure == "high":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "High Regulatory & Fining Risk", "impact_pct": penalty * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Yeni Değer: {adjusted_value:.2f}")

        return adjusted_value, hook_report