import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HoldingHook:
    """
    HOLDİNG SEKTÖRÜ PİYASA REJİMİ KANCASI
    Yabancı yatırımcı akışlarını, Türkiye CDS (Risk Primi) seviyelerini ve 
    'Holding İskontosu' genişleme/daralma dinamiklerini modele uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Holding Makro Hook devrede. Yabancı Akışı ve Ülke Risk Primi (CDS) taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: YABANCI PORTFÖY GİRİŞİ (Foreign Inflows)
        # Yabancı BİST'e geldiğinde en likit varlıkları, yani holdingleri alır. Holding iskontosu kapanır.
        foreign_inflow_trend = macro_context.get("foreign_portfolio_flows", "neutral")
        
        if foreign_inflow_trend == "strong_inflow":
            premium = 0.15 # Holding İskontosu daralma primi
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong Foreign Inflows (Discount Narrowing)", "impact_pct": premium * 100
            })
        elif foreign_inflow_trend == "strong_outflow":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Foreign Outflows (Discount Widening)", "impact_pct": penalty * 100
            })

        # KURAL 2: ÜLKE RİSK PRİMİ (TR 5 Yıllık CDS)
        # CDS 600'ün üzerine çıkarsa piyasa felç olur. İştiraklerin değeri (NAV) kağıt üzerinde kalsa da piyasa bunu fiyatlamaz.
        tr_cds_spread = macro_context.get("tr_5yr_cds", 300)
        
        if tr_cds_spread > 500:
            penalty = -0.12 # Risk primi çok yüksek, holdingler en sert iskontoyu yer.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": f"Elevated Country Risk Premium (CDS: {tr_cds_spread})", "impact_pct": penalty * 100
            })

        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report