import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HavacilikHook:
    """
    HAVACILIK SEKTÖRÜ PİYASA REJİMİ KANCASI
    Havacılığın zayıf karınları olan; Jet Yakıtı maliyetleri (Brent), 
    Küresel Jeopolitik Riskler (Turizm) ve EUR/USD paritesini modele tokat olarak atar.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Havacılık Makro Hook devrede. Jet Yakıtı ve Jeopolitik Risk taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: JET YAKITI (BRENT PETROL ŞOKU)
        # Giderlerin %30-35'i yakıttır. Yakıt fırlarsa ve şirket bunu bilet fiyatlarına yansıtamazsa marjlar erir.
        brent_crude_trend = macro_context.get("brent_crude_price_trend", "stable")
        
        if brent_crude_trend == "severe_spike":
            penalty = -0.15 # Maliyet şoku faturası
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Jet Fuel Cost Spike", "impact_pct": penalty * 100
            })
        elif brent_crude_trend == "sharp_decline":
            premium = 0.10 # Düşük petrol, havayolu için ralli sebebidir
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Low Jet Fuel Cost Advantage", "impact_pct": premium * 100
            })

        # KURAL 2: JEOPOLİTİK RİSK (GEOPOLITICAL RISK INDEX - GPR) / TURİZM TALEBİ
        # Savaş, pandemi, sınır kapanmaları havayollarının en büyük kabusudur.
        geopolitical_risk_level = macro_context.get("global_geopolitical_risk", "normal")
        
        if geopolitical_risk_level == "extreme":
            penalty = -0.25 # Uçaklar yerde kalırsa Nakit Yanma (Cash Burn) başlar.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Extreme Geopolitical Risk (Flight Disruptions)", "impact_pct": penalty * 100
            })

        # KURAL 3: EUR / USD PARİTE MAKASI (Currency Mismatch)
        # Türk havayolları (özellikle THY) gelirlerinin çoğunu EUR, giderlerinin (Yakıt, Uçak Kirası) 
        # çoğunu USD cinsinden yapar. EUR zayıflar USD güçlenirse (Parite düşerse) çapraz kurdan zarar yazarlar.
        eur_usd_parity = macro_context.get("eur_usd_parity", 1.08)
        
        if eur_usd_parity < 1.02:
            penalty = -0.05
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Unfavorable EUR/USD Parity Mismatch", "impact_pct": penalty * 100
            })
        elif eur_usd_parity > 1.12:
            premium = 0.05
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Favorable EUR/USD Parity Expansion", "impact_pct": premium * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Yeni Değer: {adjusted_value:.2f}")

        return adjusted_value, hook_report