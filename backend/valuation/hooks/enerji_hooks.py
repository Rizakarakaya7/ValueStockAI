import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class EnerjiHook:
    """
    ENERJİ SEKTÖRÜ PİYASA REJİMİ KANCASI
    Enerji Piyasası Düzenleme Kurumu (EPDK) tavan fiyatlarını, Yenilenebilir (YEKDEM) 
    döviz garantilerini ve Spot Elektrik (PTF) fiyatlarını modele uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Enerji Makro Hook devrede. PTF, AUF ve İklim Şartları taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: REGÜLASYON TAVANI (AUF - Azami Uzlaştırma Fiyatı)
        # Spot elektrik fiyatları uçtuğunda devlet tavan fiyat koyar. Şirket kâr ralli şansını kaybeder.
        epdk_auf_pressure = macro_context.get("epdk_price_cap_pressure", "low")
        
        if epdk_auf_pressure == "high":
            penalty = -0.15 # Şirketin ürettiği kâr devlete/halka sübvansiyon olarak gidiyor.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe EPDK Price Cap (AUF) Intervention", "impact_pct": penalty * 100
            })

        # KURAL 2: SPOT ELEKTRİK FİYATLARI (PTF - Piyasa Takas Fiyatı)
        # Tavan fiyat yoksa ve kış sert geçiyorsa / doğal gaz pahalıysa, elektrik üreten şirketler bayram eder.
        spot_electricity_trend = macro_context.get("tr_spot_electricity_trend", "stable")
        
        if spot_electricity_trend == "surge" and epdk_auf_pressure != "high":
            premium = 0.12 # Elektrik pahalı satılıyor, kâr marjı rekor kıracak.
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Surging Spot Electricity Prices (PTF)", "impact_pct": premium * 100
            })
        elif spot_electricity_trend == "collapse":
            penalty = -0.10 # Bahar aylarında barajlar taşıyorsa elektrik fiyatı sıfıra yaklaşır.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Collapsing Spot Electricity Prices", "impact_pct": penalty * 100
            })

        # KURAL 3: KUR DEĞER KAYBI VE YEKDEM GARANTİLERİ (Yenilenebilir)
        # Metadata eğer "yenilenebilir" veya "yekdem_heavy" diyorsa; TL'deki değer kaybı şirkete yarar (Dolarla satış yaparlar).
        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        is_renewable_yekdem = metadata.get("renewable_yekdem_heavy", False)
        
        if try_depreciation_forecast > 45.0 and is_renewable_yekdem:
            premium = 0.10 # Kur fırladıkça Dolar garantili satışların TL ciro katkısı patlar.
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "FX Depreciation Advantage (USD Guaranteed Sales)", "impact_pct": premium * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Yeni Değer: {adjusted_value:.2f}")

        return adjusted_value, hook_report