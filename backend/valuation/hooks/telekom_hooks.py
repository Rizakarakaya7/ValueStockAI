import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class TelekomHook:
    """
    TELEKOMÜNİKASYON PİYASA REJİMİ KANCASI
    ARPU (Abone Başına Ortalama Gelir) esnekliğini, taahhüt yenileme dönemlerindeki 
    enflasyonist gecikmeyi ve 5G gibi devasa lisans/spektrum yatırımlarını yönetir.
    """

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
        # Telekom şirketleri taahhütlü çalıştığı için yüksek enflasyonun ilk döneminde zarar eder (fiyatları güncelleyemez).
        # Ancak taahhüt yenileme döngüsü başladığında (ARPU Boom), enflasyonun üzerinde zam yaparak marj patlaması yaşarlar.
        arpu_trend = macro_context.get("telekom_arpu_growth_trend", "stable").lower()
        if arpu_trend == "above_inflation":
            premium = 0.12  # Enflasyon üstü ARPU büyümesi çarpanı büyütür
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({
                "factor": "Strong ARPU Expansion (Pricing Power)", "impact_pct": premium * 100
            })
        elif arpu_trend == "lagging_inflation":
            penalty = -0.10 # Enflasyonun gerisinde kalan taahhüt yenilemeleri
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "ARPU Lagging Inflation (Margin Squeeze)", "impact_pct": penalty * 100
            })

        # KURAL 2: 5G LİSANS İHALESİ VE YATIRIM BASKISI (CapEx Shock)
        # Yakın vadede bir 5G spektrum ihalesi veya lisans yenileme şoku varsa, şirketin kasasından milyarlarca dolar çıkacaktır.
        capex_shock_flag = macro_context.get("next_gen_licensing_capex_shock", False)
        if capex_shock_flag:
            penalty = -0.15 # Büyük nakit çıkışı riski nedeniyle iskonto
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Upcoming 5G/Licensing Heavy CapEx Overhang", "impact_pct": penalty * 100
            })

        # KURAL 3: DÖVİZ BAZLI ALTYAPI MALİYETLERİ (Kurların Etkisi)
        # Network donanımları (Cisco, Huawei, Ericsson vb.) döviz bazlıdır. Kur sıçramaları CapEx'i fırlatır.
        fx_trend = macro_context.get("tr_fx_stability", "stable").lower()
        if fx_trend == "volatile":
            penalty = -0.08
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({
                "factor": "Doviz Volatilitesi (FX-indexed Infrastructure Costs)", "impact_pct": penalty * 100
            })

        # Clamping (Sınırlandırma): Defansif/Düzenli nakit üreten sektörlerde kanca oynaklığı maks -%25, +%15 olmalı.
        total_adjustment_pct = max(-0.25, min(0.15, total_adjustment_pct))
        
        adjusted_value = base_intrinsic_value_tl * (1 + total_adjustment_pct)
        
        hook_report["total_discount_or_premium_pct"] = round(total_adjustment_pct * 100, 2)
        hook_report["original_model_value_tl"] = round(base_intrinsic_value_tl, 2)
        hook_report["hook_adjusted_value_tl"] = round(adjusted_value, 2)

        return adjusted_value, hook_report