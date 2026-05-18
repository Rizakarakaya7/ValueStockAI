import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class PetrokimyaHook:
    """
    PETROKİMYA SEKTÖRÜ PİYASA REJİMİ KANCASI
    Rafineri Marjlarını (Crack Spread), Petrol fiyatlarındaki ani şokları (Stok Etkisi) 
    ve Küresel Sanayi talebini modele uygular.
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
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: RAFİNERİ MARJLARI (Mediterranean Crack Spread)
        # Ham petrol ile işlenmiş ürün (Motorin, Jet Yakıtı) arasındaki fiyat farkıdır. Şirketin ana kâr motorudur.
        crack_spread_trend = macro_context.get("med_crack_spread_trend", "stable")
        
        if crack_spread_trend == "severe_contraction":
            penalty = -0.15 # Marjlar daralıyor, operasyonel kâr çökecek.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Crack Spread Contraction", "impact_pct": penalty * 100
            })
        elif crack_spread_trend == "expansion":
            premium = 0.12 # Marj rallisi, şirket para basacak.
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong Crack Spread Expansion", "impact_pct": premium * 100
            })

        # KURAL 2: BRENT PETROL ŞOKLARI (Stok Kârı / Zararı)
        # Tüpraş gibi devler ellerinde aylarca yetecek petrol tutar. Petrol aniden düşerse milyarlarca lira "Stok Zararı" yazarlar.
        brent_shock = macro_context.get("brent_inventory_effect", "neutral")
        
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

        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report