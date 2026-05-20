import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class BankacilikHook:
    """
    BANKACILIK SEKTÖRÜ PİYASA REJİMİ KANCASI
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Bankacılık Makro Hook devrede. Rasyonel stres testleri uygulanıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        model_report = metadata.get("model_report", {})
        book_value_tl = model_report.get("current_book_value_tl", 0)
        
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_deduction = 0.0

        npl_trend = macro_context.get("systemic_npl_risk", "stable")
        
        if npl_trend == "deteriorating_sharply":
            npl_wipeout_tl = book_value_tl * 0.15 
            total_tl_deduction -= npl_wipeout_tl
            hook_report["applied_adjustments"].append({
                "factor": "Severe NPL Stress Test Wipeout", 
                "impact_tl": -npl_wipeout_tl,
                "logic": "Defter değerinin %15'i kadar ekstra karşılık (zarar) simülasyonu"
            })

        tcmb_policy_stance = macro_context.get("tcmb_rate_cycle", "neutral")
        
        # Justified P/B modeline geçtiğimiz için pv_of_ri_tl artık yok, 
        # iskontoyu doğrudan ana değer üzerinden simüle ediyoruz.
        if tcmb_policy_stance == "aggressive_hiking":
            nim_squeeze_tl = base_intrinsic_value_tl * 0.15
            total_tl_deduction -= nim_squeeze_tl
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Rate Hikes (NIM Squeeze)", 
                "impact_tl": -nim_squeeze_tl,
                "logic": "Değerlemeden %15 NIM daralma iskontosu"
            })
        elif tcmb_policy_stance == "easing":
            nim_expansion_tl = base_intrinsic_value_tl * 0.10
            total_tl_deduction += nim_expansion_tl
            hook_report["applied_adjustments"].append({
                "factor": "Rate Easing Cycle (NIM Expansion)", 
                "impact_tl": nim_expansion_tl,
                "logic": "Değerlemeye %10 genişleme primi"
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_deduction
        absolute_floor = book_value_tl * 0.50
        
        if adjusted_value < absolute_floor:
            adjusted_value = absolute_floor
            hook_report["applied_adjustments"].append({
                "factor": "Absolute Valuation Floor",
                "logic": "Değer P/B 0.50 zeminine sabitlendi."
            })

        hook_report["total_discount_or_premium_pct"] = round((total_tl_deduction / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report