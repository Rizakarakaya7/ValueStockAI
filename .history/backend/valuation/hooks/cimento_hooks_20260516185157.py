import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class CimentoHook:
    """
    ÇİMENTO SEKTÖRÜ PİYASA REJİMİ KANCASI
    Enerji maliyetlerini (Petrokok/Kömür), İnşaat Sektörü Güven Endeksini ve 
    Kentsel Dönüşüm (Yeniden İnşa) primlerini modele entegre eder.
    """

    @staticmethod
    def apply_market_regime(
        base_intrinsic_value_tl: float, 
        metadata: Dict[str, Any], 
        macro_context: Dict[str, Any] 
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Çimento Makro Hook devrede. Enerji Maliyetleri ve İnşaat Güven Endeksi taranıyor.")
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed"}

        adjusted_value = base_intrinsic_value_tl
        hook_report = {
            "applied_adjustments": [],
            "total_discount_or_premium_pct": 0.0
        }
        
        total_adjustment_pct = 0.0

        # KURAL 1: ENERJİ MALİYETLERİ (Kömür / Petrokok / Elektrik Şoku)
        # Çimento fırınları enerji oburudur. Global kömür fiyatlarındaki şoklar marjları anında ezer.
        energy_cost_trend = macro_context.get("industrial_energy_cost_trend", "stable")
        
        if energy_cost_trend == "severe_spike":
            penalty = -0.15 # Maliyet enflasyonu faturası
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Severe Energy Cost Spike (Coal/Electricity)", "impact_pct": penalty * 100
            })
        elif energy_cost_trend == "sharp_decline":
            premium = 0.10 # Düşük enerji maliyeti doğrudan kâr marjına yansır
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Low Energy Cost Advantage", "impact_pct": premium * 100
            })

        # KURAL 2: İNŞAAT SEKTÖRÜ GÜVEN ENDEKSİ VE KONUT KREDİSİ FAİZLERİ
        # Konut kredisi faizleri %40'ların üzerindeyse yeni proje başlamaz, iç pazar daralır.
        mortgage_rate = macro_context.get("tr_mortgage_rate_annual", 40.0)
        construction_confidence = macro_context.get("tr_construction_confidence_index", 80.0)
        
        if mortgage_rate > 45.0 or construction_confidence < 70.0:
            penalty = -0.10 # İç pazar inşaat daralması
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Prohibitive Mortgage Rates & Low Construction Confidence", "impact_pct": penalty * 100
            })

        # KURAL 3: MEGA PROJELER VE KENTSEL DÖNÜŞÜM PRİMİ
        # Devlet destekli devasa altyapı projeleri veya deprem sonrası yeniden inşa süreçleri sektörü yıllarca besler.
        infrastructure_boom_flag = macro_context.get("infrastructure_or_rebuild_boom", False)
        
        if infrastructure_boom_flag:
            premium = 0.15 # Uzun vadeli garantili hacim (Volume) beklentisi
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Mega Infrastructure / Urban Rebuild Premium", "impact_pct": premium * 100
            })

        # NİHAİ UYGULAMA
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)
        
        logger.info(f"[{ticker}] Hook Etkisi: % {total_adjustment_pct*100:.2f} | Eski: {base_intrinsic_value_tl:.2f} -> Yeni: {adjusted_value:.2f}")

        return adjusted_value, hook_report