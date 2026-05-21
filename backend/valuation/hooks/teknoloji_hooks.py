import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class TeknolojiHook:
    """
    TEKNOLOJİ PİYASA REJİMİ VE RİSK KANCASI
    Yapay Zeka (AI) trendlerini ve büyüme hisselerinin faiz (Duration) hassasiyetini fiyatlar.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Teknoloji sektörü için akıllı veri türetme ve risk motoru.
        Büyüme (Growth) odaklı oldukları için yüksek borç tolere edilmez.
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
            # Teknoloji şirketlerinde yatırımlar entelektüel sermayedir. Aşırı borçlanma iflas riskini artırır.
            if debt_to_ebitda > 3.0:
                risk_score = 8
                risk_flags.append(f"Teknoloji (Büyüme) Hissesi İçin Yüksek Finansman Riski ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 1.0:
                risk_score = 3
                risk_flags.append(f"Net Nakit Pozisyonu veya Ar-Ge İçin Çok Güçlü Likidite ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Yönetilebilir Bilanço Profili ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Teknoloji hisselerinin yüksek 'Duration' (Faiz) hassasiyeti riski atandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Teknoloji ve yazılım sektörü şirketleri uzak vadeli nakit akışlarına sahip oldukları için faiz artış döngülerinden en sert negatif darbeyi alırlar (Duration Risk).")

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
        logger.info(f"[{ticker}] Teknoloji Makro Hook devrede. Faiz hassasiyeti (Duration) ve Mega Trendler taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_adjustment = 0.0

        # KURAL 1: FAİZ VE SÜRE RİSKİ (Interest Rate & Duration Shock)
        tcmb_policy_stance = macro_context.get("tcmb_rate_cycle", "neutral")
        
        if tcmb_policy_stance == "aggressive_hiking":
            duration_shock_tl = base_intrinsic_value_tl * 0.25 
            total_tl_adjustment -= duration_shock_tl
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Rate Hikes (Duration Risk Shock)", 
                "impact_tl": -duration_shock_tl,
                "logic": "Yüksek faizler, uzaktaki kârların bugünkü değerini sert şekilde eritir (-%25 EV iskontosu)."
            })
        elif tcmb_policy_stance == "easing":
            duration_premium_tl = base_intrinsic_value_tl * 0.15
            total_tl_adjustment += duration_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "Rate Easing Cycle (Duration Premium)", 
                "impact_tl": duration_premium_tl,
                "logic": "Faiz indirim döngüsü, büyüme hisselerinin çarpanlarını doğrudan genişletir (+%15 EV primi)."
            })

        # KURAL 2: YAPAY ZEKA VE DİJİTALLEŞME TRENDİ (AI Megatrend)
        global_tech_sentiment = macro_context.get("global_tech_sentiment", "bullish")
        
        if global_tech_sentiment == "bullish":
            ai_premium_tl = base_intrinsic_value_tl * 0.10
            total_tl_adjustment += ai_premium_tl
            hook_report["applied_adjustments"].append({
                "factor": "AI & Digitalization Megatrend Premium", 
                "impact_tl": ai_premium_tl,
                "logic": "Yapay zeka devrimi sektöre ciddi bir hikaye (Narrative) primi sağlıyor (+%10 EV primi)."
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