import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel

logger = logging.getLogger(__name__)

class DemirCelikModel(BaseValuationModel):
    """
    DEMİR-ÇELİK SEKTÖRÜ İZOLE MODELLİ (Örn: EREGL, KRDMD)
    Emtia döngülerine aşırı duyarlı olduğu için, son çeyrek nakit akışını doğrusal büyütmek intihardır.
    Model, 'Mid-Cycle' (Döngü Ortalaması) Serbest Nakit Akışı varsayımıyla çalışır.
    """
    
    SECTOR_BETA = 1.25               # BİST ortalamasından daha volatil
    TERMINAL_GROWTH_RATE = 0.015     # Uzun vadede küresel büyümenin (GSYH) biraz altı (Muhafazakar)
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Demir-Çelik Döngüsel DCF Modeli çalıştırılıyor.")
        
        # 1. GİRDİ DOĞRULAMASI
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        # Döngüsel şirketlerde son TTM'i almak yerine, şirketin normalize edilmiş marjı
        # üzerinden türetilen "Smoothed EBITDA" bazlı FCF daha güvenlidir.
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF. Model Zemin (Floor) korumasına devredilecek."}

        # 2. İSKONTO ORANI (WACC)
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 3. DÖNGÜSEL PROJEKSİYON (Cyclical Projection)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Çelik sektörü lineer büyümez. Diyelim ki şu an döngünün dibindeyiz (Growth yüksek başlar, sonra normalize olur)
        # Eğer metadata'da "peak_cycle" uyarısı varsa bu oranlar eksiye bile dönebilir (Şimdilik Mid-Cycle varsayımı)
        growth_path = [0.15, 0.10, 0.05, 0.02, 0.015]
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 4. UÇ DEĞER VE FİRMA DEĞERİ
        terminal_value = (projected_cash_flows[-1] * (1 + self.TERMINAL_GROWTH_RATE)) / (discount_rate - self.TERMINAL_GROWTH_RATE)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 5. NET BORÇ DÜZELTMESİ (Equity Value'a geçiş)
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Demir_Celik_Cyclical_DCF",
            "applied_wacc": discount_rate,
            "base_fcf_used_tl": base_fcf_cents / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
        }

        return target_equity_value_tl, model_report