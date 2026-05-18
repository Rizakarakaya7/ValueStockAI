import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class MadencilikHook:
    """
    MADENCİLİK SEKTÖRÜ PİYASA REJİMİ KANCASI
    Küresel Altın/Emtia rüzgarlarını (XAU/USD), Kur avantajını ve çevresel regülasyon / 
    ruhsat iptal risklerini modele Hakikat Tokadı olarak uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Madencilik Makro Hook devrede. Küresel Ons (Gold) ve Ruhsat Riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: KÜRESEL ALTIN / EMTİA FİYATLARI (XAU/USD Trend)
        # Altın fiyatları yükseliyorsa, üretim maliyeti sabit kalan madencinin kâr marjı patlar.
        gold_price_trend = macro_context.get("global_gold_price_trend", "stable")
        
        if gold_price_trend == "bull_market":
            premium = 0.20 # Emtia rallisi, maden hisselerine roket takar.
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Global Gold/Commodity Bull Market", "impact_pct": premium * 100
            })
        elif gold_price_trend == "bear_market":
            penalty = -0.15 # Altın düşerse kârlılık erir.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Commodity Bear Market Margin Squeeze", "impact_pct": penalty * 100
            })

        # KURAL 2: MALİYET VE GELİR KUR MAKASI (TL Depreciation vs USD Revenue)
        # Geliri Dolar, gideri TL. TL'deki sert değer kaybı madenciler için kusursuz fırtınadır (Pozitif yönde).
        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        
        if try_depreciation_forecast > 40.0:
            premium = 0.10 # Kur kaynaklı "Havadan Gelen Kâr" (Windfall Profit)
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Favorable USD Revenue / TRY Cost Mismatch", "impact_pct": premium * 100
            })

        # KURAL 3: ÇEVRESEL RİSKLER VE RUHSAT İPTALİ (Environmental/ESG Risk)
        # Maden kazaları (Siyanür sızıntısı vs.) veya devletin ruhsat iptali şirketi bir günde sıfırlar.
        environmental_regulatory_risk = macro_context.get("mining_regulatory_risk", "low")
        
        if environmental_regulatory_risk == "high":
            penalty = -0.30 # Ağır iskonto! Maden kapatılırsa FCF sıfıra iner.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Environmental / License Revocation Risk", "impact_pct": penalty * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Yeni Değer: {adjusted_value:.2f}")

        return adjusted_value, hook_report