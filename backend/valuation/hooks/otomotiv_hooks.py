import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class OtomotivHook:
    """
    OTOMOTİV PİYASA REJİMİ VE RİSK KANCASI
    Avrupa İhracat Pazarı (Eurozone PMI) ve Elektrikli Araç (EV) CAPEX risklerini değerlendirir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Otomotiv sektörü için akıllı veri türetme ve risk motoru.
        Döngüsel şoklara karşı işletme sermayesi ve net borç eşikleri oldukça dardır.
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
            # Otomotiv resesyonda aniden nakit yakmaya başlar. Borçluluk tolere edilemez. Eşik: 3.0x
            if debt_to_ebitda > 3.0:
                risk_score = 8
                risk_flags.append(f"Döngüsel Daralmalara Karşı Yüksek Borç Riski ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 1.0:
                risk_score = 3
                risk_flags.append(f"Resesyon Şoklarına Dayanıklı Çok Güçlü Bilanço ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Otomotiv Sektörü İçin Ortalama Borç Yükü ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Global resesyon riski eklendi.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Otomotiv sektörü Avrupa (ihracat) pazarındaki daralmalara (PMI) ve Elektrikli Araç (EV) geçişinin yarattığı devasa yatırım yüküne duyarlıdır.")

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
        logger.info(f"[{ticker}] Otomotiv Makro Hook devrede. Avrupa İhracat Pazarı ve EV Şokları taranıyor.")
        
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

        # KURAL 1: AVRUPA İHRACAT PAZARI (Eurozone PMI)
        eurozone_demand = macro_context.get("eurozone_pmi", "contraction")
        
        if eurozone_demand == "contraction":
            export_shock_tl = enterprise_value_tl * 0.15 
            total_tl_adjustment -= export_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Eurozone Recession (Export Demand Shock)", 
                "impact_tl": -export_shock_tl,
                "logic": "Ana ihracat pazarı olan Avrupa'daki daralma nedeniyle EV'den %15 iskonto."
            })
        elif eurozone_demand == "expansion":
            export_premium_tl = enterprise_value_tl * 0.10
            total_tl_adjustment += export_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Eurozone Expansion (Export Boom)", 
                "impact_tl": export_premium_tl,
                "logic": "Avrupa pazarındaki güçlü talep nedeniyle EV'ye %10 kapasite artış primi."
            })

        # KURAL 2: ELEKTRİKLİ ARAÇ (EV) DÖNÜŞÜM RİSKİ
        ev_transition_risk = macro_context.get("ev_capex_risk", "high")
        
        if ev_transition_risk == "high":
            ev_capex_shock_tl = enterprise_value_tl * 0.10
            total_tl_adjustment -= ev_capex_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "EV Transition Heavy CAPEX Shock", 
                "impact_tl": -ev_capex_shock_tl,
                "logic": "Elektrikli araca geçiş sürecinin yaratacağı NAKİT YAKIMI (-%10 EV iskontosu)."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        book_value_cents = metadata.get("valuation_safeguards", {}).get("book_value_floor_cents", 0)
        absolute_floor_tl = (book_value_cents / 100.0) * 0.80
        
        if adjusted_value < absolute_floor_tl and absolute_floor_tl > 0:
            adjusted_value = absolute_floor_tl
            hook_report["applied_adjustments"].append({
                "factor": "Asset Value Floor (P/B 0.80)",
                "logic": "Şoklar şirketi aşırı ucuzlattı, değerleme fabrika/makine asgari değerine (0.80x P/B) sabitlendi."
            })

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report