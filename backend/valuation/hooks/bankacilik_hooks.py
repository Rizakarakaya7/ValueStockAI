import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class BankacilikHook:
    """
    BANKACILIK SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Bankacılık sektörü için akıllı veri türetme ve risk motoru.
        """
        # 1. EKSİK VERİ TÜRETME (SMART IMPUTATION)
        if financials.get("net_income") is None:
            op_income = financials.get("operating_income", 0)
            if op_income is not None and op_income > 0:
                financials["net_income"] = op_income * 0.75
                financials["imputed_net_income_flag"] = True

        # 2. SEKTÖREL RİSK HESAPLAMA (Risk Engine)
        risk_score = 5
        risk_flags = []
        
        # Güvenli veri çekme
        equity = financials.get("equity") or financials.get("total_equity")
        total_assets = financials.get("total_assets")

        # HATA DÜZELTME: None kontrolü ekledik
        if equity is not None and total_assets is not None and total_assets > 0:
            equity_to_assets = equity / total_assets
            
            # Artık None > 0 hatası almayacaksın çünkü yukarıda kontrol ettik
            if equity_to_assets < 0.08:
                risk_score = 8
                risk_flags.append(f"Yüksek Kaldıraç Riski (Özkaynak/Varlık: %{equity_to_assets*100:.1f})")
            elif equity_to_assets > 0.12:
                risk_score = 3
                risk_flags.append(f"Güçlü Sermaye Yapısı (Özkaynak/Varlık: %{equity_to_assets*100:.1f})")
            else:
                risk_score = 5
                risk_flags.append(f"Stabil Sermaye Yeterliliği (Özkaynak/Varlık: %{equity_to_assets*100:.1f})")
        else:
            # Veri yoksa panikleme, 5 skorunu koru ve bilgi notu düş
            risk_score = 5
            risk_flags.append("Sermaye Yeterliliği verisi eksik, sektör ortalaması varsayıldı.")

        risk_flags.append("Banka bilançoları regülatif kararlara (TCMB faiz, zorunlu karşılıklar) duyarlıdır.")

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
        logger.info(f"[{ticker}] Bankacılık Makro Hook devrede. Rasyonel stres testleri uygulanıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        model_report = metadata.get("model_report", {})
        book_value_tl = model_report.get("current_book_value_tl", 0)
        
        hook_report = {
            "applied_adjustments": [],
            "total_value_impact_tl": 0.0
        }
        
        total_tl_deduction = 0.0

        npl_trend = macro_context.get("systemic_npl_risk", "stable")
        
        if npl_trend == "deteriorating_sharply":
            npl_wipeout_tl = book_value_tl * 0.15 
            total_tl_deduction -= npl_wipeout_tl
            hook_report["applied_adjustments"].append({
                "factor": "Severe NPL Stress Test Wipeout", 
                "impact_tl": -npl_wipeout_tl,
                "logic": "Defter değerinin %15'i kadar ekstra karşılık (zarar) simülasyonu"
            })

        tcmb_policy_stance = macro_context.get("tcmb_rate_cycle", "neutral")
        
        if tcmb_policy_stance == "aggressive_hiking":
            nim_squeeze_tl = base_intrinsic_value_tl * 0.15
            total_tl_deduction -= nim_squeeze_tl
            hook_report["applied_adjustments"].append({
                "factor": "Aggressive Rate Hikes (NIM Squeeze)", 
                "impact_tl": -nim_squeeze_tl,
                "logic": "Değerlemeden %15 NIM daralma iskontosu"
            })
        elif tcmb_policy_stance == "easing":
            nim_expansion_tl = base_intrinsic_value_tl * 0.10
            total_tl_deduction += nim_expansion_tl
            hook_report["applied_adjustments"].append({
                "factor": "Rate Easing Cycle (NIM Expansion)", 
                "impact_tl": nim_expansion_tl,
                "logic": "Değerlemeye %10 genişleme primi"
            })

        adjusted_value = base_intrinsic_value_tl + total_tl_deduction
        absolute_floor = book_value_tl * 0.50
        
        if adjusted_value < absolute_floor:
            adjusted_value = absolute_floor
            hook_report["applied_adjustments"].append({
                "factor": "Absolute Valuation Floor",
                "logic": "Değer P/B 0.50 zeminine sabitlendi."
            })

        hook_report["total_discount_or_premium_pct"] = round((total_tl_deduction / base_intrinsic_value_tl) * 100, 2) if base_intrinsic_value_tl > 0 else 0
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"
        return adjusted_value, hook_report