import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SavunmaHook:
    """
    SAVUNMA SANAYİ PİYASA REJİMİ KANCASI
    Devlet bütçe açıklarını (Tahsilat Gecikmesi), Jeopolitik Gerilimleri (Talep) 
    ve İhracat/Ambargo risklerini modele Hakikat Tokadı olarak uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Savunma Makro Hook devrede. Jeopolitik Gerilim ve Devlet Bütçesi taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: JEOPOLİTİK RİSK VE SAVUNMA BÜTÇESİ (Global Defense Spending)
        # Sınır ötesi operasyonlar veya NATO bütçe artışları sektörü ralliye sokar.
        geopolitical_tension = macro_context.get("global_geopolitical_risk", "normal")
        nato_spending_trend = macro_context.get("nato_defense_spending_trend", "stable")
        
        if geopolitical_tension == "extreme" or nato_spending_trend == "surge":
            premium = 0.15 # Artan savaş riski = Artan sipariş
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Elevated Geopolitical Tension / Defense Budget Surge", "impact_pct": premium * 100
            })

        # KURAL 2: TAHSİLAT RİSKİ VE DEVLET BÜTÇE AÇIĞI (Fiscal Deficit)
        # Hazine zor durumdaysa, Savunma Sanayii ödemeleri ertelenir. Şirket bankadan faizle borç almak zorunda kalır.
        tr_fiscal_deficit_trend = macro_context.get("tr_fiscal_deficit_trend", "stable")
        
        if tr_fiscal_deficit_trend == "deteriorating":
            penalty = -0.10 # Devlet geç ödeyecek, nakit akışı bozulacak.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Fiscal Deficit Expansion (Receivables Collection Risk)", "impact_pct": penalty * 100
            })

        # KURAL 3: İHRACAT AMBARGOLARI VE CAATSA (Export License Risk)
        # İhracat sözleşmesi imzalanmış olsa bile, Batılı ülkeler alt parçalar (Motor, Çip) için ambargo koyarsa ürün teslim edilemez.
        export_embargo_risk = macro_context.get("tr_defense_export_embargo_risk", "low")
        
        if export_embargo_risk == "high":
            penalty = -0.15 # Üretim felci ve ciro iptalleri riski.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "High Export License / Embargo Risk", "impact_pct": penalty * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Yeni Değer: {adjusted_value:.2f}")

        return adjusted_value, hook_report