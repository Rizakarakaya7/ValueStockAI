import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class MadencilikModel(BaseValuationModel):
    """
    MADENCİLİK SEKTÖRÜ İZOLE MODELLİ (Örn: KOZAL, KOZAA)
    'Depleting Asset' (Tükenen Varlık) arketipi. Ürün fiyatı tamamen küresel 
    piyasalara (Altın/Emtia) bağlıdır. Rezerv ömrü kısıtı nedeniyle Uç Değer (Terminal Value) 
    büyümesi son derece muhafazakar veya sıfır alınır.
    """
    
    SECTOR_BETA = 0.70               # Altın madencileri piyasa krizlerinde 'Güvenli Liman' (Safe Haven) oldukları için betaları düşüktür.
    TERMINAL_GROWTH_RATE = 0.00      # Maden tükenir. Yeni rezerv bulunamazsa büyüme sıfırdır.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Madencilik/Emtia DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Ağır arama (Exploration) yılı veya düşük ons fiyatı. Floor beklenecek."}

        # İskonto Oranı (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. NAKİT AKIŞI PROJEKSİYONU (Emtia Döngüsü)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Maden şirketleri döngüseldir. Sabit büyümezler. Mevcut üretimin devamı varsayımı:
        growth_path = [0.10, 0.08, 0.05, 0.02, 0.00] 
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 2. UÇ DEĞER (Terminal Value)
        # Büyüme 0 olduğu için formül = FCF / İskonto Oranı şekline sadeleşir.
        terminal_value = projected_cash_flows[-1] / discount_rate
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 3. KASA / NET NAKİT DÜZELTMESİ (Madenciler Nakit Zengindir)
        # Eğer net borç eksiyse (Şirketin kasasında banka borcundan daha fazla nakit varsa), 
        # bu formülde eksi ile eksinin çarpımından (+) olur ve Firma Değerine eklenir.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Madencilik_Depleting_Asset_DCF",
            "applied_wacc": discount_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100,
            "zero_terminal_growth_applied": True, # Ajanların (LLM) bunu bilmesi kritik
            "enterprise_value_tl": enterprise_value_cents / 100,
            "net_cash_premium_applied": net_debt_cents < 0 
        }

        return target_equity_value_tl, model_report