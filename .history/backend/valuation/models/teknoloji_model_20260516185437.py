import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class TeknolojiModel(BaseValuationModel):
    """
    TEKNOLOJİ/YAZILIM SEKTÖRÜ İZOLE MODELLİ (Örn: LOGO, MIATK)
    'Growth Optionality' (Büyüme Opsiyonalitesi). Varlık (Asset) hafif, CapEx düşük,
    ancak başlangıç büyümesi çok hızlı olup sonrasında normalleşen bir DCF modelidir.
    """
    
    SECTOR_BETA = 1.35               # Teknoloji hisseleri beta olarak yüksektir (Volatildir).
    TERMINAL_GROWTH_RATE = 0.04      # Yazılım şirketleri ekonomiden daha hızlı büyür (Terminal %4).
    PROJECTION_YEARS = 7               # Teknoloji için 5 yıl kısa kalır, ufku 7 yıla açıyoruz.

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Teknoloji Hypergrowth DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        # Startup / Zarar eden teknoloji şirketi koruması (Zemin mekanizmasına yollar)
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Teknoloji şirketi nakit yakıyor."}

        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. HYPER-GROWTH PROJEKSİYONU (Yüksekten düşen büyüme hızı)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # İlk 3 yıl agresif büyüme (Sektör kapma), sonrasında pazar doyumuna doğru (Decay rate)
        growth_path = [0.45, 0.35, 0.25, 0.18, 0.12, 0.08, 0.05]
        
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

        # 3. NET BORÇ DÜZELTMESİ (Yazılım şirketleri genelde net nakittedir)
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Teknoloji_Hypergrowth_DCF",
            "applied_wacc": discount_rate,
            "pv_of_7_year_fcf_tl": present_value_of_fcf / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "has_net_cash_premium": net_debt_cents < 0 # Eğer net borç eksiyse (nakit fazlası) primlidir.
        }

        return target_equity_value_tl, model_report