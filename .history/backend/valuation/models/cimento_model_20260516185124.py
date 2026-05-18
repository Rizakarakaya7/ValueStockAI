import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class CimentoModel(BaseValuationModel):
    """
    ÇİMENTO SEKTÖRÜ İZOLE MODELLİ (Örn: AKCNS, CIMSA, OYAKC)
    İç piyasa inşaat döngülerine duyarlı, yüksek sabit maliyetli (High Operating Leverage) 
    ve enerji yoğun şirketler için Döngüsel DCF modeli.
    """
    
    SECTOR_BETA = 1.05               # İnşaat döngülerine bağlıdır ama BİST ortalamasına yakındır.
    TERMINAL_GROWTH_RATE = 0.015     # Nüfus artışı ve uzun vadeli kentleşme hızına paralel (Muhafazakar).
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Çimento Döngüsel DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Ağır fırın/kapasite yatırımı yılı veya derin kriz. Zemin (Floor) beklenecek."}

        # İskonto Oranı (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. BÜYÜME PROJEKSİYONU (Döngüsel Büyüme)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Çimento büyümesi inşaat döngüsüyle paraleldir. Ortalama bir döngü varsayımı:
        growth_path = [0.15, 0.10, 0.05, 0.02, 0.015] 
        
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

        # 3. NET BORÇ DÜZELTMESİ
        # Çimentocular genellikle yatırımlarını uzun vadeli kredilerle finanse eder.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Cimento_Cyclical_DCF",
            "applied_wacc": discount_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
        }

        return target_equity_value_tl, model_report