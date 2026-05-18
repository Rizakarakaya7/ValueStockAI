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
        
        # DÜZELTME 1: Sigorta şirketleri bilanço mantığı olarak Bankacılık (Financials) taksonomisini kullanır.
        reporting_group = FinancialGroupCode.BANKING
        
        logger.info(f"[{ticker}] Sigortacılık Residual Income Modeli çalıştırılıyor.")
        
        # 1. GİRDİLER (Stock vs Flow)
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        net_income_keys = get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME)
        
        # DÜZELTME 2: Sadece bilançoda gerçekten var olan anahtarları filtrele (Pandas KeyError Koruması)
        existing_equity_keys = [k for k in equity_keys if k in df.index]
        existing_ni_keys = [k for k in net_income_keys if k in df.index]
        
        if not existing_equity_keys or not existing_ni_keys:
            logger.error(f"[{ticker}] Sigorta değerlemesi için gerekli veriler bilançoda bulunamadı.")
            return 0.0, {"warning": "Missing Equity/Income Data for Insurance"}
        
        # Filtrelenmiş güvenli anahtarlarla veriyi çek
        current_book_value_cents = float(df.loc[existing_equity_keys, df.columns[-1]].sum(skipna=True))
        net_income_ttm_cents = float(df.loc[existing_ni_keys, df.columns[-4:]].sum().sum())
        
        if current_book_value_cents <= 0:
            return 0.0, {"warning": "Negatif Defter Değeri (İflas Riski)"}
            
        current_roe = net_income_ttm_cents / current_book_value_cents
        
        # İskonto Oranı (Cost of Equity - COE)
        risk_free_rate = 0.35  
        erp = 0.08             
        coe = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. AŞIRI GETİRİ (RESIDUAL INCOME) PROJEKSİYONU
        projected_residual_incomes = []
        projected_book_values = [current_book_value_cents]
        
        # Sigortacılıkta ROE tahvil faizlerine paralel seyreder.
        target_roe = coe + 0.02
        roe_path = [current_roe - ((current_roe - target_roe) / self.PROJECTION_YEARS) * i for i in range(1, self.PROJECTION_YEARS + 1)]
        
        dividend_payout_ratio = 0.40 # Sigorta şirketleri kâr dağıtımında bankalardan daha cömerttir
        present_value_of_ri = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            year_roe = roe_path[year - 1]
            prev_bv = projected_book_values[-1]
            
            net_income = prev_bv * year_roe
            retained_earnings = net_income * (1 - dividend_payout_ratio)
            new_bv = prev_bv + retained_earnings
            projected_book_values.append(new_bv)
            
            residual_income = (year_roe - coe) * prev_bv
            projected_residual_incomes.append(residual_income)
            
            present_value_of_ri += residual_income / ((1 + coe) ** year)

        # 3. UÇ DEĞER (Terminal Value)
        terminal_ri = (roe_path[-1] - coe) * projected_book_values[-1]
        pv_of_terminal_ri = (terminal_ri / coe) / ((1 + coe) ** self.PROJECTION_YEARS)

        # 4. NİHAİ DEĞER
        target_equity_value_cents = current_book_value_cents + present_value_of_ri + pv_of_terminal_ri
        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Insurance_Residual_Income",
            "current_roe": current_roe,
            "cost_of_equity": coe,
            "pv_of_residual_income_tl": present_value_of_ri / 100,
        }

        return target_equity_value_tl, model_report