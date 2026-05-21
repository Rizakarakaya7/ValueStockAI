import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HavacilikHook:
    """
    HAVACILIK SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    Jet yakıtı maliyetlerini, turizm eğilimlerini ve döviz dengesini (EUR/USD paritesi) uygular.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Havacılık sektörü için akıllı veri türetme ve risk motoru.
        Operasyonel kiralama ve yoğun CAPEX sebebiyle borç eşikleri oldukça geniştir.
        """
        # 1. EKSİK VERİ TÜRETME (SMART IMPUTATION)
        if financials.get("ebitda") is None:
            op_income = financials.get("operating_income", 0)
            depreciation = financials.get("depreciation", 0)
            if op_income is not None and op_income > 0:
                financials["ebitda"] = op_income + depreciation
                financials["imputed_ebitda_flag"] = True

        if financials.get("net_debt") is None:
            total_debt = financials.get("totalDebt", financials.get("total_debt", 0))
            cash = financials.get("totalCash", financials.get("total_cash", 0))
            if total_debt is not None and total_debt > 0:
                financials["net_debt"] = total_debt - cash

        # 2. SEKTÖREL RİSK HESAPLAMA (Risk Engine)
        risk_score = 5
        risk_flags = []
        
        net_debt = financials.get("net_debt")
        ebitda = financials.get("ebitda")

        if net_debt is not None and ebitda is not None and ebitda > 0:
            debt_to_ebitda = net_debt / ebitda
            # Havacılık sektörü yüksek CAPEX ve uçak finansmanı taşır. 5.0x'e kadar tolere edilebilir.
            if debt_to_ebitda > 5.0:
                risk_score = 8
                risk_flags.append(f"Ağır Borç Yükü ve Operasyonel Kaldıraç Riski ({debt_to_ebitda:.1f}x)")
            elif debt_to_ebitda < 2.5:
                risk_score = 3
                risk_flags.append(f"Havacılık Sektörüne Göre Güçlü Bilanço ({debt_to_ebitda:.1f}x)")
            else:
                risk_score = 5
                risk_flags.append(f"Kabul Edilebilir Sektörel Finansman Yükü ({debt_to_ebitda:.1f}x)")
        else:
            risk_score = 6
            risk_flags.append("Net Borç / FAVÖK verisine ulaşılamadı. Havacılık makro şok riski uygulandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Sektör jeopolitik krizlere, jet yakıtı (Brent) fiyatlarına ve döviz kuru çaprazlarına (EUR/USD) son derece duyarlıdır.")

        financials["sector_risk_score"] = risk_score
        financials["sector_risk_flags"] = risk_flags

        return financials

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to non-positive base value"}

        # Havayolu sektörü yüksek volatiliteye sahip olduğu için ana koruma %20 MoS (Margin of Safety)
        safety_margin = 0.20
        adjusted_value = base_intrinsic_value_tl * (1 - safety_margin)
        
        hook_report = {
            "original_value": base_intrinsic_value_tl,
            "applied_adjustments": []
        }

        # 1. PETROL (JET YAKITI) KANCASI
        oil_trend = macro_context.get("brent_oil_trend", "stable").lower()
        if oil_trend == "spike":
            adjusted_value *= 0.90  
            hook_report["applied_adjustments"].append({"factor": "Oil Spike", "impact_pct": -10.0})
        elif oil_trend == "drop":
            adjusted_value *= 1.07  
            hook_report["applied_adjustments"].append({"factor": "Oil Drop", "impact_pct": 7.0})

        # 2. TURİZM / YOLCU TRAFİĞİ KANCASI
        passenger_growth = macro_context.get("aviation_passenger_trend", "normal").lower()
        if passenger_growth == "boom":
            adjusted_value *= 1.10  
            hook_report["applied_adjustments"].append({"factor": "Passenger Boom", "impact_pct": 10.0})
        elif passenger_growth == "recession":
            adjusted_value *= 0.85  
            hook_report["applied_adjustments"].append({"factor": "Passenger Recession", "impact_pct": -15.0})

        # 3. PARİTE (EUR/USD) KANCASI
        ticker = metadata.get("ticker", "UNKNOWN")
        if ticker == "PGSUS":
            eur_usd_regime = macro_context.get("eur_usd_trend", "stable").lower()
            if eur_usd_regime == "strong_eur":
                adjusted_value *= 1.05  
                hook_report["applied_adjustments"].append({"factor": "Strong EUR for PGSUS", "impact_pct": 5.0})
            elif eur_usd_regime == "weak_eur":
                adjusted_value *= 0.95  
                hook_report["applied_adjustments"].append({"factor": "Weak EUR for PGSUS", "impact_pct": -5.0})
                
        # ORCHESTRATOR UYUMLULUK
        hook_report["hook_status"] = "OK"
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report