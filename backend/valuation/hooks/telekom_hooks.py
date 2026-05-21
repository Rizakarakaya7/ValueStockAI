import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class TelekomHook:
    """
    TELEKOMÜNİKASYON PİYASA REJİMİ VE RİSK KANCASI
    ARPU (Abone Başına Ortalama Gelir) esnekliğini ve 5G lisans yatırım baskılarını değerlendirir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Telekom sektörü için akıllı veri türetme ve risk motoru.
        Abonelik bazlı defansif nakit akışı sayesinde borçluluk tolere edilebilirliği yüksektir.
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
            # Telekom sektörü devasa CAPEX gerektirir. Nakit akışı istikrarlı olduğu için 4.0x'e kadar tolere edilebilir.
            if debt_to_ebitda > 4.0:
                risk_score = 8
                risk_flags.append(f"Telekomünikasyon İçin Yüksek Döviz/Borç Yükü ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 2.0:
                risk_score = 3
                risk_flags.append(f"Düzenli Nakit Akışına (ARPU) Kıyasla Çok Düşük Borçluluk ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Standart Altyapı Finansman Seviyesi ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 5
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Telekomünikasyon standart defansif skoru atandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Telekom şirketleri taahhütlü çalıştıkları için yüksek enflasyonist dönemlerde 'fiyatlama gecikmesi' yaşarlar, ancak altyapı yatırımları (döviz borcu) sebebiyle kur şoklarına karşı kırılgandırlar.")

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
        logger.info(f"[{ticker}] Telekom Makro Hook devrede. ARPU Trendi ve Lisans Maliyetleri taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: ARPU / ENFLASYON ETKİSİ (Fiyatlama Gücü)
        arpu_trend = macro_context.get("telekom_arpu_growth_trend", "stable").lower()
        if arpu_trend == "above_inflation":
            premium = 0.12  
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong ARPU Expansion (Pricing Power)", "impact_pct": premium * 100
            })
        elif arpu_trend == "lagging_inflation":
            penalty = -0.10 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "ARPU Lagging Inflation (Margin Squeeze)", "impact_pct": penalty * 100
            })

        # KURAL 2: 5G LİSANS İHALESİ VE YATIRIM BASKISI (CapEx Shock)
        capex_shock_flag = macro_context.get("next_gen_licensing_capex_shock", False)
        if capex_shock_flag:
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Upcoming 5G/Licensing Heavy CapEx Overhang", "impact_pct": penalty * 100
            })

        # KURAL 3: DÖVİZ BAZLI ALTYAPI MALİYETLERİ (Kurların Etkisi)
        fx_trend = macro_context.get("tr_fx_stability", "stable").lower()
        if fx_trend == "volatile":
            penalty = -0.08
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Doviz Volatilitesi (FX-indexed Infrastructure Costs)", "impact_pct": penalty * 100
            })

        total_adjustment_pct = max(-0.25, min(0.15, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report