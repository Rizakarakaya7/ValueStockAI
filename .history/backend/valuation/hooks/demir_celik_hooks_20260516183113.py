import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DemirCelikHook:
    """
    DEMİR-ÇELİK SEKTÖRÜ PİYASA REJİMİ KANCASI
    DCF Modelinden çıkan steril matematiksel fiyatı; Çin Çelik Spread'leri,
    Kapasite Kullanım Oranları ve Global PMI verileriyle yüzleştirir.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] # Orkestratör'den gelecek güncel makro veriler
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Demir-Çelik Makro Hook (Hakikat Tokadı) devrede.")
        
        # Eğer değer zaten eksiye veya sıfıra düşmüşse hook uygulamaya gerek yok
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to negative base value"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: ÇİN HRC (Sıcak Rulo) / HURDA SPREAD'İ (Kâr Marjı Daralması)
        # Çin'de spreadler daralıyorsa (Dumping varsa), BİST çelikçileri kesinlikle zarar görür.
        china_hrc_spread_trend = macro_context.get("china_hrc_spread_trend", "neutral")
        
        if china_hrc_spread_trend == "severe_contraction":
            # Çin piyasayı ucuz çeliğe boğuyor. Kârlılık düşecek. Fiyatı %15 aşağı çek.
            penalty = -0.15
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "China HRC Dumping", "impact_pct": penalty * 100
            })
        elif china_hrc_spread_trend == "expansion":
            # Çelik fiyatları ralli yapıyor. Modele %10 döngü primi ekle.
            premium = 0.10
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Favorable Commodity Cycle", "impact_pct": premium * 100
            })

        # KURAL 2: GLOBAL ÜRETİM (PMI) ENDEKSİ
        # Küresel sanayi yavaşlıyorsa çelik talebi düşer.
        global_manufacturing_pmi = macro_context.get("global_pmi", 50.0)
        
        if global_manufacturing_pmi < 48.0:
            # Resesyon sinyali. Demir-Çelik ilk vurulan sektördür.
            penalty = -0.10
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Global PMI Recession Warning", "impact_pct": penalty * 100
            })

        # NİHAİ UYGULAMA (Final Application)
        # Matematiksel fiyata toplam iskontoyu/primi uygula
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Eski: {base_intrinsic_value_tl:.2f} -> Yeni: {adjusted_value:.2f}")

        return adjusted_value, hook_report