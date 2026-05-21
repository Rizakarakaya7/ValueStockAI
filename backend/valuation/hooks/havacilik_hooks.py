import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class HavacilikHook:
    @staticmethod
    def apply_market_regime(base_intrinsic_value_tl: float, metadata: Dict[str, Any], macro_context: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        
        if base_intrinsic_value_tl <= 0:
            return base_intrinsic_value_tl, {"hook_status": "Bypassed due to non-positive base value"}

        # Havayolu sektörü yüksek volatiliteye sahip olduğu için ana koruma %20 MoS (Margin of Safety)
        safety_margin = 0.20
        adjusted_value = base_intrinsic_value_tl * (1 - safety_margin)
        
        hook_details = {"original_value": base_intrinsic_value_tl}

        # 1. PETROL (JET YAKITI) KANCASI (Çift Yönlü)
        # Maliyetlerin %30-40'ı yakıt olduğu için çift yönlü senaryo işlenmeli.
        oil_trend = macro_context.get("brent_oil_trend", "stable").lower()
        if oil_trend == "spike":
            adjusted_value *= 0.90  # %10 ek iskonto (Maliyet şoku)
            hook_details["oil_effect"] = "-10% (Oil Spike)"
        elif oil_trend == "drop":
            adjusted_value *= 1.07  # %7 prim (Marj genişlemesi)
            hook_details["oil_effect"] = "+7% (Oil Drop)"

        # 2. TURİZM / YOLCU TRAFİĞİ KANCASI
        # Yolcu doluluk oranları veya ülkeye giren turist trendi değerlemeyi destekler.
        passenger_growth = macro_context.get("aviation_passenger_trend", "normal").lower()
        if passenger_growth == "boom":
            adjusted_value *= 1.10  # %10 pozitif prim (Güçlü talep ve yüksek bilet fiyatlaması)
            hook_details["passenger_effect"] = "+10% (Passenger Boom)"
        elif passenger_growth == "recession":
            adjusted_value *= 0.85  # %15 derin iskonto (Koltukların boş kalması riskine karşı)
            hook_details["passenger_effect"] = "-15% (Passenger Recession)"

        # 3. PARİTE (EUR/USD) KANCASI (Özellikle Pegasus için hayati)
        # Gelirlerin Euro, giderlerin/borçların USD olması durumunda güçlü Euro çarpanı büyütür.
        ticker = metadata.get("ticker", "UNKNOWN")
        if ticker == "PGSUS":
            eur_usd_regime = macro_context.get("eur_usd_trend", "stable").lower()
            if eur_usd_regime == "strong_eur":
                adjusted_value *= 1.05  # %5 olumlu katkı
                hook_details["fx_parity_effect"] = "+5% (Strong EUR for PGSUS)"
            elif eur_usd_regime == "weak_eur":
                adjusted_value *= 0.95  # %5 olumsuz etki
                hook_details["fx_parity_effect"] = "-5% (Weak EUR for PGSUS)"
                
        hook_details["final_adjusted"] = adjusted_value
        return adjusted_value, hook_details