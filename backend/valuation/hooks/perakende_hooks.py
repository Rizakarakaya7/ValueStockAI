import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class PerakendeHook:
    """
    PERAKENDE PİYASA REJİMİ KANCASI
    Asgari ücret (Personel Gideri) şoklarını ve enflasyonist 
    ortamda ucuz marketlerin (Discount Retail) kazandığı defansif primi fiyatlar.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Perakende Makro Hook devrede. Asgari ücret şokları ve Tüketici Güveni taranıyor.")
        
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

        # KURAL 1: ASGARİ ÜCRET ŞOKU (Labor Cost Squeeze)
        # Perakendenin en büyük masrafı on binlerce çalışanının maaşıdır. Sert asgari ücret artışları kâr marjını ezer.
        wage_inflation_trend = macro_context.get("wage_inflation", "aggressive")
        
        if wage_inflation_trend == "aggressive":
            # Agresif maaş artışları, zaten %5 olan dar kâr marjını %4'e iter. EV üzerinden %10 iskonto.
            labor_shock_tl = enterprise_value_tl * 0.10 
            total_tl_adjustment -= labor_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Minimum Wage Hikes (Margin Squeeze)", 
                "impact_tl": -labor_shock_tl,
                "logic": "Sert asgari ücret artışlarının düşük kâr marjlarını ezme riski (-%10 EV iskontosu)."
            })

        # KURAL 2: TÜKETİCİ GÜVENİ VE DEFANSİF PRİM (Defensive Premium in Contraction)
        # Ekonomi kötüye gittiğinde (Resesyon/Kriz), insanlar AVM'den alışverişi keser ama yemeği BİM/A101/Şok'tan almaya başlar (Trade-down).
        consumer_confidence = macro_context.get("consumer_confidence", "contraction")
        
        if consumer_confidence == "contraction":
            # Kriz zamanında gıda perakendesi "Güvenli Liman" olarak görülür ve premium ile fiyatlanır.
            defensive_premium_tl = enterprise_value_tl * 0.15
            total_tl_adjustment += defensive_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Recession Defensive Premium (Trade-down Effect)", 
                "impact_tl": defensive_premium_tl,
                "logic": "Tüketici güvenindeki düşüş, indirimli marketlere pazar payı kazandırır (+%15 EV primi)."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        # Son Koruma: Hisse değeri sıfırın altına inemez
        if adjusted_value < 0:
            adjusted_value = 0.0

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report