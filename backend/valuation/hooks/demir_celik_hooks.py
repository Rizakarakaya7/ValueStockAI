import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DemirCelikHook:
    """
    DEMİR-ÇELİK (AĞIR SANAYİ) PİYASA REJİMİ KANCASI
    PMI Daralmaları, CBAM Riskleri ve 'Stok Erimesi' (Inventory Write-down) cezaları içerir.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Demir-Çelik Makro Hook devrede. PMI, CBAM ve Stok riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        model_report = metadata.get("model_report", {})
        enterprise_value_tl = model_report.get("enterprise_value_tl", base_intrinsic_value_tl)
        
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_adjustment = 0.0
        global_pmi_trend = macro_context.get("global_pmi_trend", "contraction") # Varsayılan: Daralma (Trough)

        # KURAL 1: KÜRESEL İMALAT (Global PMI) ve STOK ERİMESİ (Trough Cycle Risk)
        if global_pmi_trend == "contraction" or global_pmi_trend == "severe_contraction":
            # 1.A: Resesyon Şoku
            demand_shock_tl = enterprise_value_tl * 0.15 
            total_tl_adjustment -= demand_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Global PMI Contraction (Trough Cycle)", 
                "impact_tl": -demand_shock_tl,
                "logic": "Küresel resesyon nedeniyle Firma Değerinden %15 talep daralması iskontosu."
            })
            
            # 1.B: Stok Erimesi (Inventory Write-down) - steel.py'den entegre edildi!
            # Krize yüksek nakit eksiği ve devasa işletme sermayesi ile giren şirket ceza yer.
            net_debt_tl = model_report.get("net_debt_deducted_tl", 0)
            if net_debt_tl > (enterprise_value_tl * 0.20): 
                inventory_penalty_tl = enterprise_value_tl * 0.10
                total_tl_adjustment -= inventory_penalty_tl
                hook_report["applied_adjustments"].append({
                    "factor": "Trough Cycle Inventory & Working Capital Burden", 
                    "impact_tl": -inventory_penalty_tl,
                    "logic": "Krize yüksek borç/stok yüküyle yakalanma (Write-down) cezası: -%10 EV iskontosu."
                })

        elif global_pmi_trend == "expansion":
            demand_boom_tl = enterprise_value_tl * 0.10
            total_tl_adjustment += demand_boom_tl
            hook_report["applied_adjustments"].append({
                "factor": "Global Expansion (PMI > 52)", 
                "impact_tl": demand_boom_tl,
                "logic": "Küresel büyüme döngüsü nedeniyle Firma Değerine %10 prim."
            })

        # KURAL 2: KARBON VERGİSİ & YEŞİL DÖNÜŞÜM (CBAM Risk)
        cbam_risk = macro_context.get("cbam_capex_risk", "high")
        if cbam_risk == "high":
            green_capex_shock_tl = enterprise_value_tl * 0.10
            total_tl_adjustment -= green_capex_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "CBAM & Green Steel CAPEX Shock", 
                "impact_tl": -green_capex_shock_tl,
                "logic": "AB Karbon Vergisi uyum maliyeti (Negative NPV) iskonto edildi."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        # Son Koruma: Hisse değeri sıfırın altına inemez
        if adjusted_value < 0:
            adjusted_value = 0.0

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report