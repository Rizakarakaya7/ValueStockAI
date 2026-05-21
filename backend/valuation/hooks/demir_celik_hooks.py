import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DemirCelikHook:
    """
    DEMİR-ÇELİK (AĞIR SANAYİ) PİYASA REJİMİ VE RİSK KANCASI
    PMI Daralmaları, CBAM Riskleri ve 'Stok Erimesi' (Inventory Write-down) cezaları içerir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Demir-Çelik sektörü için akıllı veri türetme ve risk motoru.
        Döngüsel, ağır sanayi kurallarına göre risk eşikleri belirlenmiştir.
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
            # Demir-çelik yüksek döngüseldir. Kriz anında yüksek borç iflasa sürükler. Eşikler dardır.
            if debt_to_ebitda > 3.5:
                risk_score = 8
                risk_flags.append(f"Ağır Sanayide Yüksek Borçluluk Riski ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 1.5:
                risk_score = 3
                risk_flags.append(f"Döngüsel Şoklara Karşı Güçlü Bilanço ve Düşük Borç ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Yönetilebilir Borç Profili ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Küresel döngüsellik varsayımı uygulandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Sektör, Küresel İmalat PMI verilerine, cevher/hurda fiyatlarına ve CBAM (Karbon) regülasyonlarına aşırı duyarlıdır.")

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
        logger.info(f"[{ticker}] Demir-Çelik Makro Hook devrede. PMI, CBAM ve Stok riskleri taranıyor.")
        
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
        global_pmi_trend = macro_context.get("global_pmi_trend", "contraction")

        if global_pmi_trend == "contraction" or global_pmi_trend == "severe_contraction":
            demand_shock_tl = enterprise_value_tl * 0.15 
            total_tl_adjustment -= demand_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Global PMI Contraction (Trough Cycle)", 
                "impact_tl": -demand_shock_tl,
                "logic": "Küresel resesyon nedeniyle Firma Değerinden %15 talep daralması iskontosu."
            })
            
            net_debt_tl = model_report.get("net_debt_deducted_tl", 0)
            if net_debt_tl > (enterprise_value_tl * 0.20): 
                inventory_penalty_tl = enterprise_value_tl * 0.10
                total_tl_adjustment -= inventory_penalty_tl
                hook_report["applied_adjustments"].append({
                    "factor": "Trough Cycle Inventory & Working Capital Burden", 
                    "impact_tl": -inventory_penalty_tl,
                    "logic": "Krize yüksek borç/stok yüküyle yakalanma (Write-down) cezası: -%10 EV iskontosu."
                })

        elif global_pmi_trend == "expansion":
            demand_boom_tl = enterprise_value_tl * 0.10
            total_tl_adjustment += demand_boom_tl
            hook_report["applied_adjustments"].append({
                "factor": "Global Expansion (PMI > 52)", 
                "impact_tl": demand_boom_tl,
                "logic": "Küresel büyüme döngüsü nedeniyle Firma Değerine %10 prim."
            })

        cbam_risk = macro_context.get("cbam_capex_risk", "high")
        if cbam_risk == "high":
            green_capex_shock_tl = enterprise_value_tl * 0.10
            total_tl_adjustment -= green_capex_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "CBAM & Green Steel CAPEX Shock", 
                "impact_tl": -green_capex_shock_tl,
                "logic": "AB Karbon Vergisi uyum maliyeti (Negative NPV) iskonto edildi."
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_adjustment
        
        if adjusted_value < 0:
            adjusted_value = 0.0

        hook_report["total_discount_or_premium_pct"] = round((total_tl_adjustment / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        return adjusted_value, hook_report