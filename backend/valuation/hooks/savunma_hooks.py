import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SavunmaHook:
    """
    SAVUNMA SANAYİ PİYASA REJİMİ VE RİSK KANCASI
    Devlet bütçe açıklarını (Tahsilat Gecikmesi), Jeopolitik Gerilimleri ve FX (Kur) Avantajını fiyatlar.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Savunma sektörü için akıllı veri türetme ve risk motoru.
        Müşteri genellikle devlet (SSB) olduğu için tahsilat süreleri çok uzundur, borçluluk toleransı geniştir.
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
            # Savunma şirketleri devasa Ar-Ge ve işletme sermayesi (alacak) taşır. 4.0x'e kadar makul görülür.
            if debt_to_ebitda > 4.5:
                risk_score = 8
                risk_flags.append(f"Ağır İşletme Sermayesi ve Finansman Yükü ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 2.0:
                risk_score = 3
                risk_flags.append(f"Devlet Taahhütlerine Rağmen Çok Güçlü Likidite ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Sektör Dinamiklerine Uygun Borçluluk ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Savunma sektörü bütçe riski uygulandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Savunma sanayi şirketleri uzun tahsilat vadeleri nedeniyle 'İşletme Sermayesi' baskısı yaşayabilir, ancak yabancı para cinsi (FX) bakiye siparişleri kur krizlerinde kalkan görevi görür.")

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
        fx_trend = macro_context.get("try_annual_depreciation_forecast", 25.0)
        if fx_trend > 40.0:
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong FX Advantage on Foreign Currency Backlog", "impact_pct": premium * 100
            })

        total_adjustment_pct = max(-0.25, min(0.30, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report