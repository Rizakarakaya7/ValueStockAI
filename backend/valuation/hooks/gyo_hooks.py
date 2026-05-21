import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class GyoHook:
    """
    GYO SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    Konut Kredisi Faiz Oranlarını, Konut Fiyat Endeksini ve Kentsel Dönüşüm beklentilerini uygular.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        GYO sektörü için akıllı veri türetme ve risk motoru.
        GYO'larda FAVÖK anlamsız olabilir. Ana risk göstergesi Borç/Toplam Varlık (LTV) oranıdır.
        """
        # 1. EKSİK VERİ TÜRETME (SMART IMPUTATION)
        if financials.get("net_debt") is None:
            total_debt = financials.get("totalDebt", financials.get("total_debt", 0))
            cash = financials.get("totalCash", financials.get("total_cash", 0))
            if total_debt > 0:
                financials["net_debt"] = total_debt - cash

        # 2. SEKTÖREL RİSK HESAPLAMA (Risk Engine)
        risk_score = 5
        risk_flags = []
        
        total_debt = financials.get("totalDebt", financials.get("total_debt"))
        total_assets = financials.get("total_assets")

        if total_debt is not None and total_assets is not None and total_assets > 0:
            debt_to_assets = total_debt / total_assets
            
            # GYO'larda Varlıkların %60'ından fazla borçlanma (LTV > 0.6) büyük risktir
            if debt_to_assets > 0.60:
                risk_score = 8
                risk_flags.append(f"Yüksek Kaldıraçlı GYO Portföyü (Borç/Varlık: %{debt_to_assets*100:.1f})")
            elif debt_to_assets < 0.30:
                risk_score = 3
                risk_flags.append(f"Güçlü Portföy Finansmanı ve Düşük Borçluluk (Borç/Varlık: %{debt_to_assets*100:.1f})")
            else:
                risk_score = 5
                risk_flags.append(f"Dengeli Gayrimenkul Finansman Yapısı (Borç/Varlık: %{debt_to_assets*100:.1f})")
        else:
            risk_score = 6
            risk_flags.append("Borç / Toplam Varlık verisine ulaşılamadı. Sektör ortalama iskontosu uygulandı.")

        # GYO'lara özel genel uyarı
        risk_flags.append("GYO'lar faiz oranlarına yüksek duyarlılık gösterir ve genellikle Net Aktif Değerlerine (NAD) göre iskontolu işlem görürler.")

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
        logger.info(f"[{ticker}] GYO Makro Hook devrede. Faiz Oranları ve Konut Talebi taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        hook_report = {"applied_adjustments": []}
        total_adjustment_pct = 0.0

        # KURAL 1: KONUT KREDİSİ FAİZ ORANLARI (Mortgage Rates)
        mortgage_rate = macro_context.get("tr_mortgage_rate_annual", 40.0)
        if mortgage_rate > 35.0:
            penalty = -0.15 
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "High Mortgage Rates (Demand Destruction)", "impact_pct": penalty * 100
            })
        elif mortgage_rate < 15.0:
            premium = 0.20
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Low Mortgage Rates (Housing Boom)", "impact_pct": premium * 100
            })

        # KURAL 2: KONUT FİYAT ENDEKSİ / REEL GETİRİ (Housing Price Trend)
        housing_trend = macro_context.get("housing_price_trend", "stable").lower()
        if housing_trend == "boom":
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Real Estate Valuation Boom", "impact_pct": premium * 100
            })
        elif housing_trend == "stagnation":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Housing Market Stagnation", "impact_pct": penalty * 100
            })

        # KURAL 3: KENTSEL DÖNÜŞÜM / MEGA PROJELER (Örn: EKGYO)
        urban_regeneration = macro_context.get("urban_regeneration_boom", False)
        if urban_regeneration:
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Urban Regeneration / Mega Project Tailwinds", "impact_pct": premium * 100
            })

        total_adjustment_pct = max(-0.25, min(0.30, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report