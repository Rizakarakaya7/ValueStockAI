import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class TelekomHook:
    """
    TELEKOMÜNİKASYON SEKTÖRÜ PİYASA REJİMİ KANCASI
    Regülasyon (Tavan Fiyat) baskısını, Kur (FX) Şoklarını ve devasa 
    altyapı ihalelerini (5G) modele Hakikat Tokadı olarak uygular.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Telekom Makro Hook devrede. Regülasyon ve Kur Riski taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: REEL ARPU ERİMESİ (TÜFE vs Fiyat Artış İzni)
        # Eğer beklenen enflasyon, şirketlerin yapabileceği fiyat artışının çok üzerindeyse gelirler reel olarak erir.
        expected_inflation = macro_context.get("expected_cpi_inflation", 45.0)
        max_allowed_tariff_hike = macro_context.get("telecom_tariff_hike_cap", 30.0) # Regülatör tavanı
        
        if expected_inflation - max_allowed_tariff_hike > 10.0:
            # Şirketler enflasyonun en az 10 puan altında eziliyor. Reel gelir kaybı.
            penalty = -0.12
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Real ARPU Contraction (Regulation Cap)", "impact_pct": penalty * 100
            })
        elif max_allowed_tariff_hike >= expected_inflation:
            # Serbest piyasa işliyor, operatörler fiyatlama gücünü kullanabiliyor.
            premium = 0.05
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong Pricing Power (ARPU > CPI)", "impact_pct": premium * 100
            })

        # KURAL 2: KUR ŞOKU (FX Depreciation) VE YATIRIM MALİYETLERİ
        # Baz istasyonları (Ericsson, Huawei) ve lisans bedelleri dövizledir. TL'de ani çöküş nakdi yakar.
        try_depreciation_forecast = macro_context.get("try_annual_depreciation_forecast", 25.0)
        
        if try_depreciation_forecast > 45.0:
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "FX Shock on Infrastructure CapEx", "impact_pct": penalty * 100
            })

        # KURAL 3: 5G VEYA BÜYÜK LİSANS İHALESİ DÖNGÜSÜ
        # İhale yılı geldiğinde şirketler milyarlarca doları devlete nakit ödemek zorunda kalır. Serbest Nakit Akışı çöker.
        upcoming_license_auction = macro_context.get("upcoming_major_telecom_auction", False)
        
        if upcoming_license_auction:
            penalty = -0.15 # Piyasada "CapEx overstretch" korkusu oluşur.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Upcoming 5G/License Auction Cash Drain", "impact_pct": penalty * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Yeni Değer: {adjusted_value:.2f}")

        return adjusted_value, hook_report