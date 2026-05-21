import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class OtomotivHook:
    """
    OTOMOTİV PİYASA REJİMİ KANCASI
    Avrupa İhracat Pazarı (Eurozone PMI) ve Elektrikli Araç (EV) 
    Dönüşüm CAPEX risklerini doğrudan Firma Değerine (EV) yansıtır.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Otomotiv Makro Hook devrede. Avrupa İhracat Pazarı ve EV Şokları taranıyor.")
        
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

        # KURAL 1: AVRUPA İHRACAT PAZARI (Eurozone PMI)
        eurozone_demand = macro_context.get("eurozone_pmi", "contraction")
        
        if eurozone_demand == "contraction":
            export_shock_tl = enterprise_value_tl * 0.15 
            total_tl_adjustment -= export_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Eurozone Recession (Export Demand Shock)", 
                "impact_tl": -export_shock_tl,
                "logic": "Ana ihracat pazarı olan Avrupa'daki daralma nedeniyle EV'den %15 iskonto."
            })
        elif eurozone_demand == "expansion":
            export_premium_tl = enterprise_value_tl * 0.10
            total_tl_adjustment += export_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Eurozone Expansion (Export Boom)", 
                "impact_tl": export_premium_tl,
                "logic": "Avrupa pazarındaki güçlü talep nedeniyle EV'ye %10 kapasite artış primi."
            })

        # KURAL 2: ELEKTRİKLİ ARAÇ (EV) DÖNÜŞÜM RİSKİ
        ev_transition_risk = macro_context.get("ev_capex_risk", "high")
        
        if ev_transition_risk == "high":
            ev_capex_shock_tl = enterprise_value_tl * 0.10
            total_tl_adjustment -= ev_capex_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "EV Transition Heavy CAPEX Shock", 
                "impact_tl": -ev_capex_shock_tl,
                "logic": "Elektrikli araca geçiş sürecinin yaratacağı NAKİT YAKIMI (-%10 EV iskontosu)."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        book_value_cents = metadata.get("valuation_safeguards", {}).get("book_value_floor_cents", 0)
        absolute_floor_tl = (book_value_cents / 100.0) * 0.80
        
        if adjusted_value < absolute_floor_tl and absolute_floor_tl > 0:
            adjusted_value = absolute_floor_tl
            hook_report["applied_adjustments"].append({
                "factor": "Asset Value Floor (P/B 0.80)",
                "logic": "Şoklar şirketi aşırı ucuzlattı, değerleme fabrika/makine asgari değerine (0.80x P/B) sabitlendi."
            })

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report