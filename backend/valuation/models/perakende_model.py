import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class PerakendeModel(BaseValuationModel):
    """
    PERAKENDE SEKTÖRÜ İZOLE MODELLİ (Örn: BIMAS, MGROS, SOKM)
    'Stable Compounder' (Düzenli Büyüyen) arketipidir. Nakit döngüsü negatiftir 
    (Tedarikçi finansmanı), bu yüzden FCF üretimi çok güçlüdür.
    """
    
    SECTOR_BETA = 0.85               # Defansif sektör. Endeksten daha az düşer/çıkar.
    TERMINAL_GROWTH_RATE = 0.03      # Gıda enflasyonu ve nüfus artışı nedeniyle uzun vade büyümesi nispeten yüksektir.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Perakende Stable Compounder DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        # Gıda perakendesinde negatif FCF çok nadirdir (Sıfırdan devasa yatırım yılı değilse)
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Model Zemin (Floor) korumasına devredilecek."}

        # İskonto Oranı (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. DÜZENLİ BÜYÜME PROJEKSİYONU (Stable Compounding)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Perakendede büyüme = (Beklenen Gıda Enflasyonu) + (Yeni Mağaza Açılış Hızı)
        # Ağır sanayi gibi J-Curve yapmaz, düzenli bileşik getiri üretir.
        growth_path = [0.35, 0.25, 0.15, 0.10, 0.08] # Yüksek enflasyondan normale dönüş senaryosu
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 2. UÇ DEĞER VE FİRMA DEĞERİ
        terminal_value = (projected_cash_flows[-1] * (1 + self.TERMINAL_GROWTH_RATE)) / (discount_rate - self.TERMINAL_GROWTH_RATE)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 3. IFRS-16 KİRA YÜKÜMLÜLÜKLERİ İLE NET BORÇ DÜZELTMESİ
        # Perakende şirketlerinin banka borcu azdır ama milyarlarca lira "Lease" borcu vardır. 
        # debt_adjuster.py bunu zaten hesaplayıp snapshot içine koydu.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Perakende_Stable_Compounder_DCF",
            "applied_wacc": discount_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100,
            "ifrs_16_lease_debt_deducted": True, # Ajanların (LLM) bunu bilmesi çok kritik
            "enterprise_value_tl": enterprise_value_cents / 100,
        }

        return target_equity_value_tl, model_report