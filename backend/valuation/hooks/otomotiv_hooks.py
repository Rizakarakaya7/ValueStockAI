import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class OtomotivHook:
    """
    OTOMOTİV SEKTÖRÜ PİYASA REJİMİ KANCASI
    Şirketin DCF fiyatını; Avrupa Birliği (ACEA) yeni araç kayıtları, 
    Yurt içi taşıt kredisi faizleri ve EUR/USD paritesiyle yüzleştirir.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Otomotiv Makro Hook devrede. İhracat ve İç Pazar taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to floor limits"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # Şirketin Metadata'sından ihracat ağırlığını çekiyoruz.
        # FROTO ihracatçıdır (Avrupa verisi ağır basar), DOAS ithalatçı/iç pazarcıdır (Faiz ağır basar).
        is_export_heavy = metadata.get("export_heavy", False)

        # KURAL 1: AVRUPA ARAÇ PAZARI (ACEA Registration Data)
        # BİST Otomotivinin can damarı Avrupa ticari araç pazarıdır.
        eu_auto_market_trend = macro_context.get("eu_auto_market", "stable")
        
        if is_export_heavy:
            if eu_auto_market_trend == "contraction":
                penalty = -0.12 # Avrupa daralıyorsa ihracatçı firmayı sert cezalandır
                total_adjustment_pct += penalty
                hook_report["applied_adjustments"].append({
                    "factor": "EU Auto Market Contraction", "impact_pct": penalty * 100
                })
            elif eu_auto_market_trend == "expansion":
                premium = 0.08
                total_adjustment_pct += premium
                hook_report["applied_adjustments"].append({
                    "factor": "Strong EU Export Demand", "impact_pct": premium * 100
                })

        # KURAL 2: İÇ PİYASA TAŞIT KREDİSİ FAİZLERİ (TCMB)
        # İç pazarda araç satışının %70'i krediyle yapılır. Kredi faizi yüksekse pazar donar.
        domestic_auto_loan_rate = macro_context.get("tr_auto_loan_rate_annual", 40.0)
        
        if domestic_auto_loan_rate > 55.0:
            # Faizler ulaşılamaz seviyede. İç pazar şirketi için ölümcül, ihracatçı için can sıkıcı.
            penalty = -0.05 if is_export_heavy else -0.15
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Prohibitive Domestic Loan Rates", "impact_pct": penalty * 100
            })
            
        # KURAL 3: EUR/USD PARİTESİ (Kur Makası)
        # Şirketler maliyeti TL/USD, satışı EUR ile yapar. Euro zayıflarsa (Parite düşerse) kâr marjı erir.
        eur_usd_parity = macro_context.get("eur_usd_parity", 1.08)
        
        if is_export_heavy and eur_usd_parity < 1.03:
            penalty = -0.05
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Weak EUR/USD Parity Margin Squeeze", "impact_pct": penalty * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Eski: {base_intrinsic_value_tl:.2f} -> Yeni: {adjusted_value:.2f}")

        return adjusted_value, hook_report