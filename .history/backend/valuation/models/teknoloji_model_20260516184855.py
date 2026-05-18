import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class TeknolojiModel(BaseValuationModel):
    """
    TEKNOLOJİ VE YAZILIM İZOLE MODELLİ
    Yüksek Brüt Marj, Düşük CapEx, Yüksek Büyüme (Growth Optionality).
    İki aşamalı (Hiper Büyüme -> Olgunlaşma) DCF Modeli.
    """
    SECTOR_BETA = 1.15
    TERMINAL_GROWTH_RATE = 0.04 # Entelektüel sermaye, genel ekonomiden hep daha hızlı büyür.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, df: pd.DataFrame, metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Owner's Earnings eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Growth hisselerinde normal olabilir (P/S katmanı devreye girmeli)."}

        risk_free_rate = 0.35
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, 0.08)

        # Yazılımda "Hiper Büyüme" varsayımı (Yıldan yıla sert düşen ama yüksek başlayan büyüme)
        growth_path = [0.45, 0.35, 0.25, 0.15, 0.08]
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            current_fcf *= (1 + growth_path[year - 1])
            present_value_of_fcf += current_fcf / ((1 + discount_rate) ** year)

        terminal_value = (current_fcf * (1 + self.TERMINAL_GROWTH_RATE)) / (discount_rate - self.TERMINAL_GROWTH_RATE)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)

        # Net Nakit/Borç düzeltmesi (Yazılım şirketleri genelde net nakit pozisyonundadır)
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = (present_value_of_fcf + pv_of_terminal_value) - net_debt_cents

        return target_equity_value_cents / 100.0, {"model_used": "Tech_High_Growth_DCF"}