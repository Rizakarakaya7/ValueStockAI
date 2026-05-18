import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class BankacilikHook:
    """
    BANKACILIK SEKTÖRÜ PİYASA REJİMİ KANCASI
    TCMB Faiz Politikalarını, Takipteki Kredi (NPL) risklerini ve 
    Enflasyon Muhasebesi (TMS-29) erozyonunu modele entegre eder.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Bankacılık Makro Hook devrede. NPL, Faiz ve Regülasyon taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: TAKİPTEKİ KREDİLER (NPL - Non-Performing Loans) RİSKİ
        # Eğer piyasada durgunluk varsa ve şirketler batıyorsa, banka milyarlarca lira karşılık (zarar) ayırmak zorundadır.
        npl_trend = macro_context.get("systemic_npl_risk", "stable")
        
        if npl_trend == "deteriorating_sharply":
            penalty = -0.20 # Banka kârlılığını yok eden en büyük risk. Acımasızca cezalandır.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe NPL (Bad Debt) Wave Warning", "impact_pct": penalty * 100
            })

        # KURAL 2: TCMB FAİZ POLİTİKASI (Net Faiz Marjı - NIM Squeeze)
        # Faizler çok sert artarsa, bankanın mevduata ödediği faiz (maliyet) hemen artar ama elindeki eski kredilerin getirisi sabittir. Bu marjları daraltır.
        tcmb_policy_stance = macro_context.get("tcmb_rate_cycle", "neutral")
        
        if tcmb_policy_stance == "aggressive_hiking":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Rate Hikes (NIM Squeeze & Bond Portfolio Loss)", "impact_pct": penalty * 100
            })
        elif tcmb_policy_stance == "easing":
            premium = 0.10 # Faiz indirim döngüsü bankalara yazar (Elindeki tahviller değerlenir, kredi iştahı açılır).
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Rate Easing Cycle (NIM Expansion)", "impact_pct": premium * 100
            })

        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report