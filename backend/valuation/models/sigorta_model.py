import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class SigortaModel(BaseValuationModel):
    """
    SİGORTACILIK SEKTÖRÜ İZOLE MODELLİ (Örn: ANSGR, AKGRT)
    Tıpkı Bankalar gibi FAVÖK'süzdür. Toplanan prim havuzunun (Float) 
    yatırım getirisi ve Özkaynak Kârlılığı (ROE) üzerinden 'Residual Income' ile değerlenir.
    """
    
    SECTOR_BETA = 0.90               # Bankalara göre daha defansiftir, hasar döngüsüne bağlıdır.
    TERMINAL_ROE_PREMIUM = 0.015     # Pazarın doymuşluğu nedeniyle sonsuzlukta ROE, COE'yi az geçer.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.BANKING
        
        logger.info(f"[{ticker}] Sigortacılık Residual Income Modeli çalıştırılıyor.")
        
        # 1. GİRDİLER VE "DOUBLE COUNTING" KORUMASI
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        net_income_keys = get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME)
        
        valid_equity = [k for k in equity_keys if k in df.index]
        valid_ni = [k for k in net_income_keys if k in df.index]
        
        if not valid_equity or not valid_ni:
            logger.error(f"[{ticker}] Sigorta değerlemesi için gerekli Net Kâr veya Özkaynak verisi bulunamadı.")
            return 0.0, {"warning": "Missing Equity/Income Data for Insurance"}
        
        # Sadece İLK eşleşen etiketi alarak ROE'nin suni patlamasını (katlanmasını) engelliyoruz
        current_book_value_cents = float(df.loc[valid_equity[0], df.columns[-1]])
        net_income_ttm_cents = float(df.loc[valid_ni[0], df.columns[-4:]].sum())
        
        if current_book_value_cents <= 0:
            logger.warning(f"[{ticker}] Negatif Defter Değeri (İflas/Sermaye Yetersizliği Riski).")
            return 0.0, {"warning": "Negative Book Value"}
            
        current_roe = net_income_ttm_cents / current_book_value_cents
        
        # İskonto Oranı (Cost of Equity - COE)
        # Gerçek sistemde risk_free_rate de metadata/makro_context üzerinden çekilmelidir.
        risk_free_rate = 0.35  
        erp = 0.08             
        coe = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. AŞIRI GETİRİ (RESIDUAL INCOME) PROJEKSİYONU
        projected_residual_incomes = []
        projected_book_values = [current_book_value_cents]
        
        # Sigortacılıkta rekabet nedeniyle zamanla ROE tahvil faizi seviyesine (COE'nin biraz üstüne) yakınsar.
        target_roe = coe + self.TERMINAL_ROE_PREMIUM
        roe_path = [current_roe - ((current_roe - target_roe) / self.PROJECTION_YEARS) * i for i in range(1, self.PROJECTION_YEARS + 1)]
        
        dividend_payout_ratio = 0.40 # Sigorta şirketleri nakit temettüde aktiftir
        present_value_of_ri = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            year_roe = roe_path[year - 1]
            prev_bv = projected_book_values[-1]
            
            # Eğer yılın ROE'si negatifse sermaye erir
            net_income = prev_bv * year_roe
            retained_earnings = net_income * (1 - dividend_payout_ratio) if net_income > 0 else net_income
            new_bv = prev_bv + retained_earnings
            projected_book_values.append(new_bv)
            
            # Residual Income (Aşırı Getiri): Hissedardan istenen getiri (COE) üzerinde kazanılan ekstra değer
            residual_income = (year_roe - coe) * prev_bv
            projected_residual_incomes.append(residual_income)
            
            present_value_of_ri += residual_income / ((1 + coe) ** year)

        # 3. UÇ DEĞER (Terminal Value) - Sonsuz Büyüme (g) Varsayımı
        # Sigorta özkaynakları enflasyonla büyür. Sürdürülebilir büyüme oranı (g) = %2 varsayıldı.
        terminal_growth_rate = 0.02
        terminal_ri = (roe_path[-1] - coe) * projected_book_values[-1]
        pv_of_terminal_ri = (terminal_ri / max(0.01, coe - terminal_growth_rate)) / ((1 + coe) ** self.PROJECTION_YEARS)

        # 4. NİHAİ HİSSEDAR DEĞERİ
        target_equity_value_cents = current_book_value_cents + present_value_of_ri + pv_of_terminal_ri
        target_equity_value_tl = max(0, target_equity_value_cents / 100.0) # Eksi çıkmasını engelle

        model_report = {
            "model_used": "Insurance_Residual_Income",
            "current_book_value_tl": current_book_value_cents / 100.0,
            "net_income_ttm_tl": net_income_ttm_cents / 100.0,
            "current_roe": current_roe,
            "cost_of_equity": coe,
            "pv_of_residual_income_tl": present_value_of_ri / 100.0,
            "pv_of_terminal_ri_tl": pv_of_terminal_ri / 100.0
        }

        return target_equity_value_tl, model_report