import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HoldingHook:
    """
    HOLDİNG PİYASA REJİMİ KANCASI
    Holding İskontosunu (Conglomerate Discount) ve Yabancı Sermaye İştahını fiyatlar.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        archetype = metadata.get("archetype", "UNKNOWN")
        
        logger.info(f"[{ticker}] Holding Makro Hook devrede. Holding İskontosu ve Yabancı Takası taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_adjustment = 0.0

        # KURAL 1: YAPISAL HOLDİNG İSKONTOSU VEYA MUAFİYETİ
        if archetype == "Operational_Holding":
            # Operasyonel holdingler (AEFES vb.) üretim yapar, bu yüzden yapısal iskontodan muaftırlar.
            hook_report["applied_adjustments"].append({
                "factor": "Operational Holding Exemption", 
                "impact_tl": 0.0,
                "logic": "Şirket 'Operasyonel Holding' statüsünde olduğu için %35 yapısal iskonto uygulanmamıştır."
            })
        else:
            # Standart holding iskontosu (KCHOL, SAHOL vb.)
            base_discount_pct = 0.35
            holding_discount_tl = base_intrinsic_value_tl * base_discount_pct
            total_tl_adjustment -= holding_discount_tl
            
            hook_report["applied_adjustments"].append({
                "factor": "Structural Conglomerate Discount", 
                "impact_tl": -holding_discount_tl,
                "logic": "Yapısal Holding İskontosu (Yönetim maliyetleri ve hantallık) nedeniyle EV'den %35 kesinti."
            })

        # KURAL 2: YABANCI YATIRIMCI İŞTAHI
        foreign_flow = macro_context.get("foreign_investor_flow", "neutral")
        
        if foreign_flow == "strong_inflow":
            foreign_premium_tl = base_intrinsic_value_tl * 0.15 
            total_tl_adjustment += foreign_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Strong Foreign Inflow (Discount Narrowing)", 
                "impact_tl": foreign_premium_tl,
                "logic": "Güçlü yabancı sermaye girişi Holding İskontosunu daraltarak hisseye %15 likidite primi sağladı."
            })
        elif foreign_flow == "strong_outflow":
            foreign_penalty_tl = base_intrinsic_value_tl * 0.10
            total_tl_adjustment -= foreign_penalty_tl
            hook_report["applied_adjustments"].append({
                "factor": "Foreign Outflow (Discount Widening)", 
                "impact_tl": -foreign_penalty_tl,
                "logic": "Yabancı sermaye çıkışı nedeniyle Holding İskontosu genişledi (-%10 ilave iskonto)."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        if adjusted_value < 0:
            adjusted_value = 0.0

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report