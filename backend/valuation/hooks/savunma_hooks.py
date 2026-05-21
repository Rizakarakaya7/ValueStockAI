import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SavunmaHook:
    """
    SAVUNMA SANAYİ PİYASA REJİMİ KANCASI
    Devlet bütçe açıklarını (Tahsilat Gecikmesi), Jeopolitik Gerilimleri, 
    Döviz (Kur) Avantajını ve İhracat/Ambargo risklerini modele uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Savunma Makro Hook devrede. Jeopolitik Risk ve Tahsilat süreci taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: JEOPOLİTİK RİSK VE SAVUNMA BÜTÇESİ
        geopolitical_tension = macro_context.get("global_geopolitical_risk", "normal").lower()
        nato_spending_trend = macro_context.get("nato_defense_spending_trend", "stable").lower()
        
        if geopolitical_tension == "extreme" or nato_spending_trend == "surge":
            premium = 0.15 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Elevated Geopolitical Tension / Defense Budget Surge", "impact_pct": premium * 100
            })

        # KURAL 2: TAHSİLAT RİSKİ VE DEVLET BÜTÇE AÇIĞI
        tr_fiscal_deficit_trend = macro_context.get("tr_fiscal_deficit_trend", "stable").lower()
        if tr_fiscal_deficit_trend == "deteriorating":
            penalty = -0.10 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Fiscal Deficit Expansion (Receivables Collection Risk)", "impact_pct": penalty * 100
            })

        # KURAL 3: İHRACAT AMBARGOLARI VE CAATSA
        export_embargo_risk = macro_context.get("tr_defense_export_embargo_risk", "low").lower()
        if export_embargo_risk == "high":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "High Export License / Embargo Risk", "impact_pct": penalty * 100
            })

        # KURAL 4: DÖVİZ (FX) POZİSYON AVANTAJI
        # Savunma şirketlerinin Backlog'u (siparişleri) genellikle Yabancı Para (Dolar/Euro) cinsindendir.
        # TL'deki değer kaybı kâr marjlarını kağıt üzerinde muazzam artırır.
        fx_trend = macro_context.get("try_annual_depreciation_forecast", 25.0)
        if fx_trend > 40.0:
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong FX Advantage on Foreign Currency Backlog", "impact_pct": premium * 100
            })

        # CLAMPING: Kümülatif şokun ekstrem sonuçlar doğurmasını engellemek için -%25 ile +%30 arası limit.
        total_adjustment_pct = max(-0.25, min(0.30, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report