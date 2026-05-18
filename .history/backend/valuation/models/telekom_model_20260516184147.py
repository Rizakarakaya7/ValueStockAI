import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class TelekomModel(BaseValuationModel):
    """
    TELEKOMÜNİKASYON SEKTÖRÜ İZOLE MODELLİ (Örn: TCELL, TTKOM)
    'Abonelik ve Altyapı' (Subscription & Infrastructure) bazlı model.
    Nakit akışları çok öngörülebilirdir, betası düşüktür ancak ağır CapEx (Fiber/5G) gerektirir.
    """
    
    SECTOR_BETA = 0.85               # Defansif sektör, piyasa dalgalanmalarından daha az etkilenir.
    TERMINAL_GROWTH_RATE = 0.025     # Nüfus artışı ve veri tüketimi büyümesine (Data usage) paralel.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Telekom Altyapı ve Abonelik DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        # Telekom şirketleri devasa FAVÖK üretir ama fiber yatırımı yılıysa FCF eksiye düşebilir.
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. 5G veya altyapı ihalesi yılı olabilir. Floor mekanizmasına devredilecek."}

        # İskonto Oranı (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. ABONELİK BÜYÜME PROJEKSİYONU (Subscription Compounding)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Telekomda büyüme = (Enflasyonist ARPU artışı) + (Yeni Abone/Fiber Hanehalkı)
        # Ağır enflasyonist ortamdan tek haneli enflasyona geçiş patikası varsayımı.
        growth_path = [0.30, 0.20, 0.12, 0.08, 0.05] 
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 2. UÇ DEĞER (Terminal Value)
        terminal_value = (projected_cash_flows[-1] * (1 + self.TERMINAL_GROWTH_RATE)) / (discount_rate - self.TERMINAL_GROWTH_RATE)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 3. KREDİ VE LİSANS BORÇLARI (Net Borç Düzeltmesi)
        # Telekom şirketlerinin devasa FX (Döviz) borçları ve lisans taksitleri vardır.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Telekom_Subscription_DCF",
            "applied_wacc": discount_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100,
            "infrastructure_debt_deducted": True, 
            "enterprise_value_tl": enterprise_value_cents / 100,
        }

        return target_equity_value_tl, model_report