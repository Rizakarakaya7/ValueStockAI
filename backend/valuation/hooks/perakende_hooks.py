import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class PerakendeHook:
    """
    PERAKENDE PİYASA REJİMİ VE RİSK KANCASI
    Asgari ücret şoklarını, Tüketici Güvenini ve Defansif Nakit Akışını değerlendirir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Perakende sektörü için akıllı veri türetme ve risk motoru.
        Düşük kâr marjı ancak yüksek ve sürekli nakit akışı dinamiklerine göre borç eşikleri belirlenmiştir.
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
            # Perakende defansiftir, her gün nakit kasa girişi vardır. Borçluluk toleransı görece rahattır.
            if debt_to_ebitda > 3.5:
                risk_score = 7
                risk_flags.append(f"Düşük Kâr Marjlarına Kıyasla Yüksek Borçlanma ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 1.5:
                risk_score = 3
                risk_flags.append(f"Defansif Sektörde Çok Güçlü Nakit ve Sıfıra Yakın Finansman Riski ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 4
                risk_flags.append(f"Sağlıklı FMCG / Perakende Borç Profili ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 5
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Perakende sektörü defansif varsayımı uygulandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Perakende sektörü nakit zenginidir ancak kâr marjları çok incedir; asgari ücret artışlarına ve regülatif tavan fiyat baskılarına duyarlıdır.")

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
        logger.info(f"[{ticker}] Perakende Makro Hook devrede. Asgari ücret şokları ve Tüketici Güveni taranıyor.")
        
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

        # KURAL 1: ASGARİ ÜCRET ŞOKU (Labor Cost Squeeze)
        wage_inflation_trend = macro_context.get("wage_inflation", "aggressive")
        
        if wage_inflation_trend == "aggressive":
            labor_shock_tl = enterprise_value_tl * 0.10 
            total_tl_adjustment -= labor_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Minimum Wage Hikes (Margin Squeeze)", 
                "impact_tl": -labor_shock_tl,
                "logic": "Sert asgari ücret artışlarının düşük kâr marjlarını ezme riski (-%10 EV iskontosu)."
            })

        # KURAL 2: TÜKETİCİ GÜVENİ VE DEFANSİF PRİM (Defensive Premium in Contraction)
        consumer_confidence = macro_context.get("consumer_confidence", "contraction")
        
        if consumer_confidence == "contraction":
            defensive_premium_tl = enterprise_value_tl * 0.15
            total_tl_adjustment += defensive_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Recession Defensive Premium (Trade-down Effect)", 
                "impact_tl": defensive_premium_tl,
                "logic": "Tüketici güvenindeki düşüş, indirimli marketlere pazar payı kazandırır (+%15 EV primi)."
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