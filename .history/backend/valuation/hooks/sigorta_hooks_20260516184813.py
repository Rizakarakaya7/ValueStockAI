class SigortaHook:
    """
    SİGORTA SEKTÖRÜ PİYASA REJİMİ KANCASI
    Yüksek faiz sigortacı için iyidir (Float geliri artar). Tavan fiyat regülasyonları kötüdür.
    """
    @staticmethod
    def apply_market_regime(base_intrinsic_value_tl: float, metadata: dict, macro_context: dict) -> tuple:
        adjusted_value = base_intrinsic_value_tl
        total_adjustment_pct = 0.0
        hook_report = {"applied_adjustments": []}

        # 1. TAHVİL FAİZLERİ (Yatırım Gelirleri Şoku)
        bond_yield_trend = macro_context.get("tr_10y_bond_yield_trend", "stable")
        if bond_yield_trend == "sharp_increase":
            premium = 0.15 # Topladığı primleri yüksek faize yatıracak, devasa kâr yazacak
            total_adjustment_pct += premium
            hook_report["applied_adjustments"].append({"factor": "High Yield Float Advantage", "impact_pct": 15})

        # 2. TRAFİK SİGORTASI TAVAN FİYAT REGÜLASYONU
        traffic_regulation_cap = macro_context.get("traffic_insurance_cap_pressure", "low")
        if traffic_regulation_cap == "high":
            penalty = -0.10 # Hasar maliyeti artarken, poliçe fiyatını artıramama sorunu
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Regulatory Margin Squeeze", "impact_pct": -10})

        adjusted_value *= (1 + total_adjustment_pct)
        return adjusted_value, hook_report