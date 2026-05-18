import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
import logging

logger = logging.getLogger(__name__)

class PetrokimyaModel(BaseValuationModel):
    """
    PETROKİMYA SEKTÖRÜ İZLE MODELLİ (Örn: TUPRS, PETKM)
    Ağır döngüsel (Cyclical) ve yüksek CapEx gerektiren, Crack Spread (Rafineri Marjı)
    dinamiklerine tabi şirketler için özelleştirilmiş 5 Yıllık İndirgenmiş Nakit Akışı (DCF).
    """
    
    # Sektöre Özel Sabitler (İleride dışarıdan makro API ile beslenebilir)
    SECTOR_BETA = 1.15               # Petrokimya piyasaya göre %15 daha hareketlidir
    TERMINAL_GROWTH_RATE = 0.02      # Sonsuz büyüme (Uç Değer) muhafazakar tutulur (%2)
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Petrokimya İzole DCF Modeli çalıştırılıyor.")
        
        # 1. GİRDİLERİN (INPUTS) KONTROLÜ
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik. CapEx katmanı çalışmamış.")
            
        # Son çeyreğin yıllıklanmış Serbest Nakit Akışını alıyoruz (Cents cinsinden Int64 gelir, floata çevir)
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        # Eğer şirket o yıl zarar etmişse (eksi nakit), DCF formülü çöker. 
        # Zemin (Floor) mekanizmasının devreye girebilmesi için burada muhafazakar bir taban atanır.
        if base_fcf_cents <= 0:
            logger.warning(f"[{ticker}] Negatif nakit akışı tespit edildi. Model sıfır değer üretecek, Zemin Koruması (Floor) tetiklenecek.")
            return 0.0, {"warning": "Negative FCF"}

        # Makro parametreler (Normalde veri pipeline'ından gelir, şimdilik simüle ediyoruz)
        risk_free_rate = 0.35  # %35 (TR koşullarında TL bazlı risksiz getiri proxy'si)
        erp = 0.08             # %8 Hisse Senedi Risk Primi
        
        # Sermaye Maliyeti (İskonto Oranı)
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. PROJEKSİYON (Gelecek 5 Yılı Tahmin Etme)
        # Petrokimya döngüseldir. İlk yıllarda büyüme yüksek olabilir, ama sonra ortalamaya döner.
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        
        # Yıllara göre azalan büyüme hızı (Sektöre özel varsayım)
        growth_rates = [0.20, 0.15, 0.10, 0.05, 0.02] 
        
        present_value_of_fcf = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_rates[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            # Bugüne İndirgeme Formülü: FCF / (1 + r)^n
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 3. UÇ DEĞER (Terminal Value) HESAPLAMASI
        # 5. yıldan sonra şirket sonsuza kadar %2 büyüyecek varsayımı (Gordon Growth Model)
        terminal_value = (projected_cash_flows[-1] * (1 + self.TERMINAL_GROWTH_RATE)) / (discount_rate - self.TERMINAL_GROWTH_RATE)
        
        # Uç değeri bugüne indirge (5. yılın iskonto faktörüne böl)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)

        # 4. FİRMA DEĞERİ (Enterprise Value)
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 5. ÖZKAYNAK/HİSSE DEĞERİNE GEÇİŞ (Equity Value)
        # Firma Değerinden -> Net Borcu Düşüyoruz
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        # Değerin TL'ye çevrilmesi (/100)
        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Petrokimya_DCF",
            "applied_wacc": discount_rate,
            "applied_beta": self.SECTOR_BETA,
            "pv_of_5_year_fcf_tl": present_value_of_fcf / 100,
            "pv_of_terminal_value_tl": pv_of_terminal_value / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "net_debt_deducted_tl": net_debt_cents / 100
        }

        return target_equity_value_tl, model_report