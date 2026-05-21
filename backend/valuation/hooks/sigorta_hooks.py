import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class SigortaHook:
    """
    SİGORTA SEKTÖRÜ PİYASA REJİMİ VE RİSK KANCASI
    Tahvil Faiz getirilerini (Float kârı), Hasar Enflasyonunu ve Regülatif tavan fiyat baskılarını yönetir.
    """

    @staticmethod
    def apply_sector_adjustments(financials: dict) -> dict:
        """
        Sigorta sektörü için akıllı veri türetme ve risk motoru.
        FAVÖK ve Net Borç anlamsızdır. Tıpkı bankalar gibi "Sermaye Yeterliliği" (Özkaynak / Varlık) esastır.
        """
        # 1. EKSİK VERİ TÜRETME (SMART IMPUTATION)
        if financials.get("net_income") is None:
            op_income = financials.get("operating_income", 0)
            if op_income > 0:
                financials["net_income"] = op_income * 0.75  # Ortalama vergi düşümü ile
                financials["imputed_net_income_flag"] = True

        # 2. SEKTÖREL RİSK HESAPLAMA (Risk Engine)
        risk_score = 5
        risk_flags = []
        
        equity = financials.get("equity", financials.get("total_equity"))
        total_assets = financials.get("total_assets")

        if equity is not None and total_assets is not None and total_assets > 0:
            equity_to_assets = equity / total_assets
            
            # Sigortacılıkta poliçe yükümlülüklerine karşılık güçlü bir özkaynak kalkanı olmalıdır.
            if equity_to_assets < 0.10:
                risk_score = 8
                risk_flags.append(f"Yetersiz Özkaynak Kalkanı ve Yüksek Hasar Karşılama Riski (Özkaynak/Varlık: %{equity_to_assets*100:.1f})")
            elif equity_to_assets > 0.18:
                risk_score = 3
                risk_flags.append(f"Çok Güçlü Sermaye Yapısı ve Yüksek Ödeme Kapasitesi (Özkaynak/Varlık: %{equity_to_assets*100:.1f})")
            else:
                risk_score = 5
                risk_flags.append(f"Stabil Sigorta Sermaye Yeterliliği (Özkaynak/Varlık: %{equity_to_assets*100:.1f})")
        else:
            risk_score = 6
            risk_flags.append("Sermaye Yeterliliği verisine ulaşılamadı. Sektörel ortalama risk atandı.")

        # Sektöre özel genel uyarılar
        risk_flags.append("Sigorta şirketleri, topladıkları primleri (Float) faizde değerlendirdikleri için yüksek faiz ortamından pozitif etkilenirken, oto/sağlık enflasyonundan negatif etkilenirler.")

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
        logger.info(f"[{ticker}] Sigorta Hook: Regülasyon, Faiz getirisi ve Hasar enflasyonu taranıyor.")
        
        if base_intrinsic_value_tl <= 0: 
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to base value <= 0"}

        total_adjustment_pct = 0.0
        hook_report = {"applied_adjustments": []}

        # KURAL 1: TAHVİL/MEVDUAT FAİZLERİ (FLOAT GETİRİSİ)
        interest_rate_trend = macro_context.get("tr_interest_rate_trend", "stable").lower()
        if interest_rate_trend == "sharp_increase":
            premium = 0.15
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({"factor": "High Yield on Float Portfolio", "impact_pct": premium * 100})
        elif interest_rate_trend == "sharp_decrease":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Low Yield on Float Portfolio", "impact_pct": penalty * 100})

        # KURAL 2: OTO/SAĞLIK YEDEK PARÇA ENFLASYONU (Hasar/Prim Oranı Baskısı)
        claims_inflation_pressure = macro_context.get("auto_health_claims_inflation", "normal").lower()
        if claims_inflation_pressure == "severe":
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Severe Claims/Severity Inflation", "impact_pct": penalty * 100})

        # KURAL 3: REGÜLASYON VE TAVAN FİYAT BASKISI (Türkiye Gerçekliği)
        regulatory_environment = macro_context.get("regulatory_price_caps", "neutral").lower()
        if regulatory_environment == "strict":
            penalty = -0.15
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Strict Regulatory Price Caps on Premiums", "impact_pct": penalty * 100})

        # KURAL 4: SİSTEMİK FELAKET RİSKİ (Catastrophe Risk)
        catastrophe_environment = macro_context.get("catastrophe_risk_environment", "normal").lower()
        if catastrophe_environment == "elevated":
            penalty = -0.12
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Elevated Reinsurance & Catastrophe Costs", "impact_pct": penalty * 100})

        total_adjustment_pct = max(-0.40, min(0.30, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        hook_report["final_adjusted"] = adjusted_value
        hook_report["total_adjustment_multiplier"] = 1 + total_adjustment_pct
        
        hook_report["hook_status"] = "OK"  # <--- BÜTÜN DOSYALARA EKLE
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        return adjusted_value, hook_report