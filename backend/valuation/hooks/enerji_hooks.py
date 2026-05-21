import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class EnerjiHook:
    """
    ENERJİ SEKTÖRÜ PİYASA REJİMİ KANCASI
    Enerji Piyasası Düzenleme Kurumu (EPDK) tavan fiyatlarını (AUF), Yenilenebilir (YEKDEM) 
    döviz garantilerini ve Spot Elektrik (PTF) fiyatlarını modele uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Enerji Makro Hook devrede. PTF, AUF ve YEKDEM riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: REGÜLASYON TAVANI (AUF - Azami Uzlaştırma Fiyatı)
        epdk_auf_pressure = macro_context.get("epdk_price_cap_pressure", "low").lower()
        if epdk_auf_pressure == "high":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe EPDK Price Cap (AUF) Intervention", "impact_pct": penalty * 100
            })

        # KURAL 2: SPOT ELEKTRİK FİYATLARI (PTF - Piyasa Takas Fiyatı)
        spot_electricity_trend = macro_context.get("tr_spot_electricity_trend", "stable").lower()
        if spot_electricity_trend == "surge" and epdk_auf_pressure != "high":
            premium = 0.12 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Surging Spot Electricity Prices (PTF)", "impact_pct": premium * 100
            })
        elif spot_electricity_trend == "collapse":
            penalty = -0.10 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Collapsing Spot Electricity Prices", "impact_pct": penalty * 100
            })

        # KURAL 3: KUR DEĞER KAYBI VE YEKDEM GARANTİLERİ
        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        is_renewable_yekdem = metadata.get("esg_metrics", {}).get("renewable_yekdem_heavy", False) # Metadata yapısı standartlaştırıldı
        
        if try_depreciation_forecast > 45.0 and is_renewable_yekdem:
            premium = 0.10 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "FX Depreciation Advantage (USD Guaranteed YEKDEM Sales)", "impact_pct": premium * 100
            })

        # KURAL 4: İKLİM RİSKİ (Kuraklık) - Hidroelektrik Ağırlıklı Şirketler İçin
        climate_drought_risk = macro_context.get("climate_drought_risk", "low").lower()
        if climate_drought_risk == "high" and is_renewable_yekdem:
             penalty = -0.08
             total_adjustment_pct += penalty
             hook_report["applied_adjustments"].append({
                "factor": "Severe Drought Risk (Hydroelectric Production Drop)", "impact_pct": penalty * 100
            })

        # CLAMPING (Sınırlandırma Koruması): Enerji sektöründe regülasyonlar marjları koruduğu için şoklar -%25 ile +%20 arasında tutulur.
        total_adjustment_pct = max(-0.25, min(0.20, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report