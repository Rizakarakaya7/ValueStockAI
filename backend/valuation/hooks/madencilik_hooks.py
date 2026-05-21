import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class MadencilikHook:
    """
    MADENCİLİK SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    Küresel Emtia (XAU/USD) Trendlerini, Peak Cycle Değer Tuzaklarını ve Çevresel riskleri yönetir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Madencilik sektörü için akıllı veri türetme ve risk motoru.
        Sert emtia döngülerine maruz kaldığı için bilançoda nakit tamponu aranır.
        """
        # 1. EKSİK VERİ TÜRETME (SMART IMPUTATION)
        if financials.get("ebitda") is None:
            op_income = financials.get("operating_income", 0)
            depreciation = financials.get("depreciation", 0)
            if op_income > 0:
                financials["ebitda"] = op_income + depreciation
                financials["imputed_ebitda_flag"] = True

        if financials.get("net_debt") is None:
            total_debt = financials.get("totalDebt", financials.get("total_debt", 0))
            cash = financials.get("totalCash", financials.get("total_cash", 0))
            if total_debt > 0:
                financials["net_debt"] = total_debt - cash

        # 2. SEKTÖREL RİSK HESAPLAMA (Risk Engine)
        risk_score = 5
        risk_flags = []
        
        net_debt = financials.get("net_debt")
        ebitda = financials.get("ebitda")

        if net_debt is not None and ebitda is not None and ebitda > 0:
            debt_to_ebitda = net_debt / ebitda
            # Madencilikte maden arama (exploration) aşaması borçludur, ancak üretim aşamasında nakit basmalıdır.
            if debt_to_ebitda > 3.5:
                risk_score = 8
                risk_flags.append(f"Emtia Şoklarına Karşı Kırılgan (Yüksek Borçluluk: {debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 1.5:
                risk_score = 3
                risk_flags.append(f"Güçlü Nakit Tamponu ve Düşük Finansman Yükü ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Sektör Ortalamasında Borçluluk ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Emtia piyasası varsayılan volatilite riski eklendi.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Madencilik şirketleri küresel emtia döngülerine (Boom/Bust) ve çevresel ruhsat (regülasyon) iptal risklerine aşırı duyarlıdır.")

        financials["sector_risk_score"] = risk_score
        financials["sector_risk_flags"] = risk_flags

        return financials

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Madencilik Makro Hook devrede. Emtia Döngüsü ve Ruhsat Riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: KÜRESEL ALTIN / EMTİA DÖNGÜSÜ VE DEĞER TUZAĞI KORUMASI (Peak Cycle)
        gold_price_trend = macro_context.get("global_gold_price_trend", "stable").lower()
        
        if gold_price_trend == "peak_cycle_bubble":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Peak Cycle Value Trap Protection (Commodity Bubble)", "impact_pct": penalty * 100
            })
        elif gold_price_trend == "bull_market":
            premium = 0.15 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Global Gold/Commodity Bull Market", "impact_pct": premium * 100
            })
        elif gold_price_trend == "bear_market":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Commodity Bear Market Margin Squeeze", "impact_pct": penalty * 100
            })

        # KURAL 2: MALİYET VE GELİR KUR MAKASI (Kur Avantajı)
        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        if try_depreciation_forecast > 40.0:
            premium = 0.10 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Favorable USD Revenue / TRY Cost Mismatch", "impact_pct": premium * 100
            })

        # KURAL 3: ÇEVRESEL RİSKLER VE RUHSAT İPTALİ
        environmental_regulatory_risk = macro_context.get("mining_regulatory_risk", "low").lower()
        if environmental_regulatory_risk == "high":
            penalty = -0.30 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Environmental / License Revocation Risk", "impact_pct": penalty * 100
            })

        total_adjustment_pct = max(-0.40, min(0.25, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report