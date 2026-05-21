import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HoldingHook:
    """
    HOLDİNG PİYASA REJİMİ VE RİSK KANCASI
    Holding İskontosunu (Conglomerate Discount), Yabancı Sermaye İştahını ve Konsolide Borçluluğu fiyatlar.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Holding sektörü için akıllı veri türetme ve risk motoru.
        Konsolide bilanço okunduğu için holding yapısına uygun risk toleransları belirlenmiştir.
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
            # Holdingler alt şirketlerinin borçlarını konsolide eder. Nakit akışı çeşitliliği riski azaltır.
            if debt_to_ebitda > 4.0:
                risk_score = 8
                risk_flags.append(f"Konsolide Bilançoda Yüksek Finansman Yükü Riski ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 1.5:
                risk_score = 3
                risk_flags.append(f"Holding Seviyesinde Çok Güçlü Likidite ve Nakit Pozisyonu ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Dengeli Konsolide Borç Profili ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 5
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Holding ortalama piyasa riski uygulandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Holdingler genellikle 'Net Aktif Değerlerine' (NAV) göre iskontolu işlem görür ve yabancı takas oranlarına yüksek duyarlılık taşır.")

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
        archetype = metadata.get("archetype", "UNKNOWN")
        
        logger.info(f"[{ticker}] Holding Makro Hook devrede. Holding İskontosu ve Yabancı Takası taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_adjustment = 0.0

        # KURAL 1: YAPISAL HOLDİNG İSKONTOSU VEYA MUAFİYETİ
        if archetype == "Operational_Holding":
            hook_report["applied_adjustments"].append({
                "factor": "Operational Holding Exemption", 
                "impact_tl": 0.0,
                "logic": "Şirket 'Operasyonel Holding' statüsünde olduğu için %35 yapısal iskonto uygulanmamıştır."
            })
        else:
            base_discount_pct = 0.35
            holding_discount_tl = base_intrinsic_value_tl * base_discount_pct
            total_tl_adjustment -= holding_discount_tl
            
            hook_report["applied_adjustments"].append({
                "factor": "Structural Conglomerate Discount", 
                "impact_tl": -holding_discount_tl,
                "logic": "Yapısal Holding İskontosu (Yönetim maliyetleri ve hantallık) nedeniyle EV'den %35 kesinti."
            })

        # KURAL 2: YABANCI YATIRIMCI İŞTAHI
        foreign_flow = macro_context.get("foreign_investor_flow", "neutral")
        
        if foreign_flow == "strong_inflow":
            foreign_premium_tl = base_intrinsic_value_tl * 0.15 
            total_tl_adjustment += foreign_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Strong Foreign Inflow (Discount Narrowing)", 
                "impact_tl": foreign_premium_tl,
                "logic": "Güçlü yabancı sermaye girişi Holding İskontosunu daraltarak hisseye %15 likidite primi sağladı."
            })
        elif foreign_flow == "strong_outflow":
            foreign_penalty_tl = base_intrinsic_value_tl * 0.10
            total_tl_adjustment -= foreign_penalty_tl
            hook_report["applied_adjustments"].append({
                "factor": "Foreign Outflow (Discount Widening)", 
                "impact_tl": -foreign_penalty_tl,
                "logic": "Yabancı sermaye çıkışı nedeniyle Holding İskontosu genişledi (-%10 ilave iskonto)."
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