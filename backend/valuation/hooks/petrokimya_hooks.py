import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class PetrokimyaHook:
    """
    PETROKİMYA SEKTÖRÜ PİYASA REJİMİ KANCASI
    Rafineri Marjlarını (Crack Spread), Petrol Stok Şoklarını ve 
    Karbon Emisyon / ESG risklerini modele uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Petrokimya Makro Hook devrede. Crack Spread ve Stok Etkisi taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: RAFİNERİ MARJLARI (Mediterranean Crack Spread)
        crack_spread_trend = macro_context.get("med_crack_spread_trend", "stable").lower()
        if crack_spread_trend == "severe_contraction":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Crack Spread Contraction", "impact_pct": penalty * 100
            })
        elif crack_spread_trend == "expansion":
            premium = 0.12 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong Crack Spread Expansion", "impact_pct": premium * 100
            })

        # KURAL 2: BRENT PETROL ŞOKLARI (Stok Kârı / Zararı)
        brent_shock = macro_context.get("brent_inventory_effect", "neutral").lower()
        if brent_shock == "massive_inventory_loss":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Expected Massive Inventory Loss (Brent Crash)", "impact_pct": penalty * 100
            })
        elif brent_shock == "massive_inventory_gain":
            premium = 0.08
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Expected Inventory Windfall Gain", "impact_pct": premium * 100
            })

        # KURAL 3: KARBON EMİSYON MALİYETİ (ESG & Sürdürülebilirlik Riski)
        # Rafineriler karbon vergisinden en çok etkilenen tesislerdir. Şirketin yeşil yatırımları yoksa uzun vadede marjları erir.
        green_transition_status = metadata.get("esg_metrics", {}).get("petchem_green_transition", "low").lower()
        carbon_tax_active = macro_context.get("global_carbon_tax_pressure", True)
        
        if carbon_tax_active and green_transition_status == "low":
             penalty = -0.05
             total_adjustment_pct += penalty
             hook_report["applied_adjustments"].append({
                "factor": "High Carbon Emission Penalty & Low Green Transition", "impact_pct": penalty * 100
            })

        # CLAMPING: Kümülatif etkinin ekstrem dalgalanmaları bozmasını engellemek için sınırlandırma
        total_adjustment_pct = max(-0.30, min(0.25, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report