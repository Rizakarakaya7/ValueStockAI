import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class CimentoHook:
    """
    ÇİMENTO SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    Enerji maliyetlerini, İnşaat Sektörü Güven Endeksini, Kentsel Dönüşüm primlerini yönetir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Çimento sektörü için akıllı veri türetme ve risk motoru.
        """
        # 1. EKSİK VERİ TÜRETME (SMART IMPUTATION)
        # Eğer EBITDA eksikse (Faaliyet Karı + Amortisman)
        if financials.get("ebitda") is None:
            op_income = financials.get("operating_income", 0)
            depreciation = financials.get("depreciation", 0)
            if op_income > 0:
                financials["ebitda"] = op_income + depreciation
                financials["imputed_ebitda_flag"] = True

        # Eğer Net Borç eksikse (Toplam Borç - Nakit)
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
            # Çimento yüksek yatırım gerektiren bir alandır, borçluluk eşiklerini buna göre esnetiyoruz.
            if debt_to_ebitda > 4.0:
                risk_score = 8
                risk_flags.append(f"Yüksek Borçluluk ve Finansman Yükü Riski ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 2.0:
                risk_score = 3
                risk_flags.append(f"Güçlü Bilanço ve Yüksek Nakit Yaratma Kapasitesi ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Döngüsel inşaat sektörü varsayılan riski uygulandı.")

        # Çimentoya özel genel uyarı
        risk_flags.append("Sektör kar marjları, enerji maliyetleri (kömür/petrokok) ve CBAM (Karbon Vergisi) gibi dış şoklara yüksek duyarlılık taşır.")

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
        logger.info(f"[{ticker}] Çimento Makro Hook devrede. Sürdürülebilirlik ve Enerji riskleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: ENERJİ MALİYETLERİ (Kömür / Petrokok Şoku)
        energy_cost_trend = macro_context.get("industrial_energy_cost_trend", "stable").lower()
        if energy_cost_trend == "severe_spike":
            penalty = -0.15
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Energy Cost Spike (Coal/Electricity)", "impact_pct": penalty * 100
            })
        elif energy_cost_trend == "sharp_decline":
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Low Energy Cost Advantage", "impact_pct": premium * 100
            })

        # KURAL 2: İNŞAAT SEKTÖRÜ GÜVEN ENDEKSİ VE FAİZ SIKIŞMASI
        mortgage_rate = macro_context.get("tr_mortgage_rate_annual", 40.0)
        construction_confidence = macro_context.get("tr_construction_confidence_index", 80.0)
        if mortgage_rate > 45.0 or construction_confidence < 70.0:
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Prohibitive Mortgage Rates & Low Construction Confidence", "impact_pct": penalty * 100
            })

        # KURAL 3: MEGA PROJELER VE KENTSEL DÖNÜŞÜM PRİMİ
        infrastructure_boom_flag = macro_context.get("infrastructure_or_rebuild_boom", False)
        if infrastructure_boom_flag:
            premium = 0.15
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Mega Infrastructure / Urban Rebuild Premium", "impact_pct": premium * 100
            })

        # KURAL 4: AB SINIRDA KAR बुन्देलMASI (CBAM) VE YEŞİL TRANSİSYON
        green_transition_status = metadata.get("esg_metrics", {}).get("cement_green_fuel_ratio", "low").lower()
        cbam_risk_active = macro_context.get("eu_cbam_pressure_active", True)
        
        if cbam_risk_active:
            if green_transition_status == "high":
                premium = 0.08  
                total_adjustment_pct += premium
                hook_report["applied_adjustments"].append({
                    "factor": "EU CBAM Readiness & High Alternative Fuel Usage", "impact_pct": premium * 100
                })
            elif green_transition_status == "low":
                penalty = -0.12 
                total_adjustment_pct += penalty
                hook_report["applied_adjustments"].append({
                    "factor": "High Carbon Emission Exposure (EU Export Risk)", "impact_pct": penalty * 100
                })

        total_adjustment_pct = max(-0.35, min(0.25, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report