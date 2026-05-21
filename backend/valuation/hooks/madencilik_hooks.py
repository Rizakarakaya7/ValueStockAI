import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class MadencilikHook:
    """
    MADENCİLİK SEKTÖRÜ PİYASA REJİMİ KANCASI
    Küresel Altın (XAU/USD) Trendlerini, Peak Cycle Değer Tuzaklarını ve 
    Çevresel Regülasyon (Ruhsat) risklerini modele uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Madencilik Makro Hook devrede. Emtia Döngüsü ve Ruhsat Riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: KÜRESEL ALTIN / EMTİA DÖNGÜSÜ VE DEĞER TUZAĞI KORUMASI (Peak Cycle)
        gold_price_trend = macro_context.get("global_gold_price_trend", "stable").lower()
        
        if gold_price_trend == "peak_cycle_bubble":
            # Değer Tuzağı Koruması: Emtia tarihi zirvedeyse şirket kâr patlaması yaşar ama bu sürdürülemez.
            # Çarpanların (veya DCF değerinin) sanal olarak şişmesini engellemek için tersine iskonto uygulanır.
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Peak Cycle Value Trap Protection (Commodity Bubble)", "impact_pct": penalty * 100
            })
        elif gold_price_trend == "bull_market":
            premium = 0.15 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Global Gold/Commodity Bull Market", "impact_pct": premium * 100
            })
        elif gold_price_trend == "bear_market":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Commodity Bear Market Margin Squeeze", "impact_pct": penalty * 100
            })

        # KURAL 2: MALİYET VE GELİR KUR MAKASI (Kur Avantajı)
        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        if try_depreciation_forecast > 40.0:
            premium = 0.10 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Favorable USD Revenue / TRY Cost Mismatch", "impact_pct": premium * 100
            })

        # KURAL 3: ÇEVRESEL RİSKLER VE RUHSAT İPTALİ (Erzincan İliç vb. Senaryolar)
        environmental_regulatory_risk = macro_context.get("mining_regulatory_risk", "low").lower()
        if environmental_regulatory_risk == "high":
            penalty = -0.30 # Ruhsat iptali madeni tamamen kilitler
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Environmental / License Revocation Risk", "impact_pct": penalty * 100
            })

        # CLAMPING: Madencilikte regülasyon ve emtia şokları sert olsa da total etki -%40 ile +%25 arasında tutulur.
        total_adjustment_pct = max(-0.40, min(0.25, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report