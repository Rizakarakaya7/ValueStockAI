import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class EnerjiHook:
    """
    ENERJİ SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    EPDK regülasyonları, YEKDEM ve PTF hassasiyetlerini içerir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Enerji sektörü için akıllı veri türetme ve risk motoru.
        Nakit akışları görece tahmin edilebilir olduğu için borçluluk eşikleri daha toleranslıdır.
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
            # Enerji yatırımları devasa kaldıraç kullanır. Garantili satışlar sebebiyle 4.5x'e kadar tolere edilebilir.
            if debt_to_ebitda > 4.5:
                risk_score = 8
                risk_flags.append(f"Enerji Sektörü İçin Aşırı Borçlanma (Finansman Riski: {debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 2.5:
                risk_score = 3
                risk_flags.append(f"Düşük Kaldıraçlı, Nakit Üretkenliği Yüksek Bilanço ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Kabul Edilebilir Sektörel Borçluluk ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 5
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Sektörel regülasyon varsayımı korundu.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Enerji şirketleri EPDK tavan fiyat (AUF) regülasyonlarına, kur dalgalanmalarına (YEKDEM) ve yağış/iklim risklerine duyarlıdır.")

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
        logger.info(f"[{ticker}] Enerji Makro Hook devrede. PTF, AUF ve YEKDEM riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        epdk_auf_pressure = macro_context.get("epdk_price_cap_pressure", "low").lower()
        if epdk_auf_pressure == "high":
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe EPDK Price Cap (AUF) Intervention", "impact_pct": penalty * 100
            })

        spot_electricity_trend = macro_context.get("tr_spot_electricity_trend", "stable").lower()
        if spot_electricity_trend == "surge" and epdk_auf_pressure != "high":
            premium = 0.12 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Surging Spot Electricity Prices (PTF)", "impact_pct": premium * 100
            })
        elif spot_electricity_trend == "collapse":
            penalty = -0.10 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Collapsing Spot Electricity Prices", "impact_pct": penalty * 100
            })

        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        is_renewable_yekdem = metadata.get("esg_metrics", {}).get("renewable_yekdem_heavy", False)
        
        if try_depreciation_forecast > 45.0 and is_renewable_yekdem:
            premium = 0.10 
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "FX Depreciation Advantage (USD Guaranteed YEKDEM Sales)", "impact_pct": premium * 100
            })

        climate_drought_risk = macro_context.get("climate_drought_risk", "low").lower()
        if climate_drought_risk == "high" and is_renewable_yekdem:
             penalty = -0.08
             total_adjustment_pct += penalty
             hook_report["applied_adjustments"].append({
                "factor": "Severe Drought Risk (Hydroelectric Production Drop)", "impact_pct": penalty * 100
            })

        total_adjustment_pct = max(-0.25, min(0.20, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report