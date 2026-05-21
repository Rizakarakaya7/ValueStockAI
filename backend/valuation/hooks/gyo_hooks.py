import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class GyoHook:
    """
    GYO SEKTÖRÜ PİYASA REJİMİ KANCASI
    Konut Kredisi Faiz Oranlarını (Mortgage Rates), Konut Fiyat Endeksini (HPI) ve 
    Kentsel Dönüşüm / Toplu Konut beklentilerini NAD çarpanına etki edecek şekilde uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] GYO Makro Hook devrede. Faiz Oranları ve Konut Talebi taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: KONUT KREDİSİ FAİZ ORANLARI (Mortgage Rates)
        # Faizler çok yüksekse ipotekli satışlar durur, stoklar elde kalır, GYO iskontosu büyür.
        mortgage_rate = macro_context.get("tr_mortgage_rate_annual", 40.0)
        if mortgage_rate > 35.0:
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "High Mortgage Rates (Demand Destruction)", "impact_pct": penalty * 100
            })
        elif mortgage_rate < 15.0:
            premium = 0.20
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Low Mortgage Rates (Housing Boom)", "impact_pct": premium * 100
            })

        # KURAL 2: KONUT FİYAT ENDEKSİ / REEL GETİRİ (Housing Price Trend)
        # Gayrimenkul fiyatları enflasyonun üzerinde artıyorsa portföy değeri (NAV) sürekli şişer.
        housing_trend = macro_context.get("housing_price_trend", "stable").lower()
        if housing_trend == "boom":
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Real Estate Valuation Boom", "impact_pct": premium * 100
            })
        elif housing_trend == "stagnation":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Housing Market Stagnation", "impact_pct": penalty * 100
            })

        # KURAL 3: KENTSEL DÖNÜŞÜM / MEGA PROJELER (Örn: EKGYO)
        # Devlet destekli toplu konut veya kentsel dönüşüm kampanyaları GYO'lara direkt ciro ve arsa tahsisi olarak yansır.
        urban_regeneration = macro_context.get("urban_regeneration_boom", False)
        if urban_regeneration:
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Urban Regeneration / Mega Project Tailwinds", "impact_pct": premium * 100
            })

        # CLAMPING (Sınırlandırma): GYO'lar fiziksel arsa/binalara dayandığı için sanal şirketler kadar
        # volatiliteye izin verilmez. Kancanın toplam gücü -%25 ile +%30 arasında kilitlenir.
        total_adjustment_pct = max(-0.25, min(0.30, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report