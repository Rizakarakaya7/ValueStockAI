import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class SavunmaModel(BaseValuationModel):
    """
    SAVUNMA SANAYİ SEKTÖRÜ İZOLE MODELLİ (Örn: ASELS, OTKAR)
    Uzun vadeli devlet sözleşmelerine (Backlog) dayalı, tahsilat vadeleri uzun ancak 
    batık riski (Default Risk) olmayan 'Defansif/Öngörülebilir' DCF arketipi.
    """
    
    SECTOR_BETA = 0.80               # Müşteri devlet olduğu için ekonomik krizlerden en az etkilenen sektördür.
    TERMINAL_GROWTH_RATE = 0.025     # Uzun vadede Savunma Bütçesi büyümesi GSYH'ye paralel veya bir tık üstüdür.
    PROJECTION_YEARS = 7               # Savunma projeleri uzun solukludur (Örn: Altay Tankı, MİLGEM), ufuk 7 yıl.

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Savunma Sanayi Backlog-Driven DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        # Tahsilat (Alacak) gün sayısının uzaması savunmada FCF'i eksiye düşürebilir.
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Devlet ödemelerinde gecikme veya ağır Ar-Ge yılı. Floor beklenecek."}

        # İskonto Oranı (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. SİPARİŞ/BACKLOG BÜYÜME PROJEKSİYONU
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Savunma projeleri genellikle ilk yıllarda yoğun Ar-Ge ve prototip (Düşük nakit),
        # seri üretime geçildiğinde ise devasa nakit şelalesi (Hasat) yaratır.
        growth_path = [0.15, 0.20, 0.25, 0.15, 0.10, 0.08, 0.05] 
        
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
        # Savunma şirketleri işletme sermayesi ihtiyacını (tahsilat beklerken) banka borcuyla çevirir.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Savunma_Backlog_DCF",
            "applied_wacc": discount_rate,
            "pv_of_7_year_fcf_tl": present_value_of_fcf / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "visibility_premium": True # Backlog'un verdiği öngörülebilirlik primi
        }

        return target_equity_value_tl, model_report