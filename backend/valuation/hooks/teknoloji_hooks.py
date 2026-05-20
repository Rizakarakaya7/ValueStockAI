import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class TeknolojiHook:
    """
    TEKNOLOJİ PİYASA REJİMİ KANCASI
    Yapay Zeka (AI) trendlerini ve büyüme hisselerinin korkulu rüyası olan
    Faiz (Duration) şoklarını fiyatlar.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Teknoloji Makro Hook devrede. Faiz hassasiyeti (Duration) ve Mega Trendler taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_adjustment = 0.0

        # KURAL 1: FAİZ VE SÜRE RİSKİ (Interest Rate & Duration Shock)
        # Teknoloji şirketlerinin kazançları çok uzun vadelidir. Merkez bankası faiz artırırsa ağır darbe alırlar.
        tcmb_policy_stance = macro_context.get("tcmb_rate_cycle", "neutral")
        
        if tcmb_policy_stance == "aggressive_hiking":
            # Agresif faiz artışları teknoloji hisselerine acımaz. EV üzerinden %25 ağır iskonto.
            duration_shock_tl = base_intrinsic_value_tl * 0.25 
            total_tl_adjustment -= duration_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Rate Hikes (Duration Risk Shock)", 
                "impact_tl": -duration_shock_tl,
                "logic": "Yüksek faizler, uzaktaki kârların bugünkü değerini sert şekilde eritir (-%25 EV iskontosu)."
            })
        elif tcmb_policy_stance == "easing":
            # Faizler düşerse piyasada para bollaşır, teknoloji ralli yapar.
            duration_premium_tl = base_intrinsic_value_tl * 0.15
            total_tl_adjustment += duration_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Rate Easing Cycle (Duration Premium)", 
                "impact_tl": duration_premium_tl,
                "logic": "Faiz indirim döngüsü, büyüme hisselerinin çarpanlarını doğrudan genişletir (+%15 EV primi)."
            })

        # KURAL 2: YAPAY ZEKA VE DİJİTALLEŞME TRENDİ (AI Megatrend)
        global_tech_sentiment = macro_context.get("global_tech_sentiment", "bullish")
        
        if global_tech_sentiment == "bullish":
            ai_premium_tl = base_intrinsic_value_tl * 0.10
            total_tl_adjustment += ai_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "AI & Digitalization Megatrend Premium", 
                "impact_tl": ai_premium_tl,
                "logic": "Yapay zeka devrimi sektöre ciddi bir hikaye (Narrative) primi sağlıyor (+%10 EV primi)."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        if adjusted_value < 0:
            adjusted_value = 0.0

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report