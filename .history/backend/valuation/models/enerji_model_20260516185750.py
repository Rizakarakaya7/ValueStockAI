import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class EnerjiModel(BaseValuationModel):
    """
    ENERJİ SEKTÖRÜ İZOLE MODELLİ (Örn: ENJSA, GWIND)
    'Regulated Yield' (Regüle Verim) arketipi. Elektrik üretim/dağıtım şirketleri
    yüksek borçla kurulur ama nakit akışları uzun vadeli (YEKDEM vb.) garanti altındadır.
    Model düşük beta ve stabil büyüme varsayar.
    """
    
    SECTOR_BETA = 0.85               # Defansif bir sektördür. Ekonomi dursa da elektrik faturası ödenir.
    TERMINAL_GROWTH_RATE = 0.02      # Global enerji tüketimi büyümesine paralel.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Enerji Regulated Yield DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        # Yenilenebilir enerji şirketleri ilk kurulum yıllarında milyarlarca lira eksi FCF yazar.
        # Bu durumda model çalışmaz, zemin korumasına ihtiyaç duyulur.
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF tespit edildi. Ağır yatırım/kurulum yılı. Zemin (Floor) beklenecek."}

        # İskonto Oranı (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. REGÜLE BÜYÜME PROJEKSİYONU
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Büyüme oranları, enflasyon düzeltmeleri ve yeni eklenecek kapasitelere (Megawatt) bağlıdır.
        # Otomotivdeki J-Curve yoktur, düz ve istikrarlıdır.
        growth_path = [0.25, 0.15, 0.10, 0.08, 0.05] 
        
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

        # 3. PROJE FİNANSMANI VE NET BORÇ DÜZELTMESİ
        # Enerji şirketleri borç yığınıdır. FCF'in bugünkü değerinden bu devasa banka kredileri düşülür.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Enerji_Regulated_Yield_DCF",
            "applied_wacc": discount_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100,
            "infrastructure_debt_deducted": True, 
            "enterprise_value_tl": enterprise_value_cents / 100,
        }

        return target_equity_value_tl, model_report