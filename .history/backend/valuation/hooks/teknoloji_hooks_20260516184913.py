class TeknolojiHook:
    """
    TEKNOLOJİ SEKTÖRÜ PİYASA REJİMİ KANCASI
    Global teknoloji risk iştahı (Nasdaq) ve Yurtiçi Bilişim Personeli Maliyetleri.
    """
    @staticmethod
    def apply_market_regime(base_intrinsic_value_tl: float, metadata: dict, macro_context: dict) -> tuple:
        adjusted_value = base_intrinsic_value_tl
        total_adjustment_pct = 0.0
        hook_report = {"applied_adjustments": []}

        # 1. GLOBAL TEKNOLOJİ İŞTAHI (Nasdaq Çarpan Dalgalanması)
        global_tech_sentiment = macro_context.get("nasdaq_sentiment_index", "neutral")
        if global_tech_sentiment == "bear_market":
            penalty = -0.20 # Global teknoloji balonu sönüyorsa BİST yazılımı da nasibini alır
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Global Tech Multiple Contraction", "impact_pct": -20})

        # 2. BEYİN GÖÇÜ / YAZILIMCI MALİYET ENFLASYONU
        tech_talent_inflation = macro_context.get("tr_tech_talent_cost_inflation", 40.0)
        if tech_talent_inflation > 70.0:
            penalty = -0.10 # Giderlerin %80'i maaştır. Maaşlar fırlarsa kâr marjı erir.
            total_adjustment_pct += penalty
            hook_report["applied_adjustments"].append({"factor": "Talent Cost Margin Squeeze", "impact_pct": -10})

        adjusted_value *= (1 + total_adjustment_pct)
        return adjusted_value, hook_report