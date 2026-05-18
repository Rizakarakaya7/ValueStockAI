import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode
import logging

logger = logging.getLogger(__name__)

class SigortaModel(BaseValuationModel):
    """
    SİGORTACILIK SEKTÖRÜ İZOLE MODELLİ (Örn: ANSGR, AKGRT, TURSG)
    Bankacılığa benzer şekilde FAVÖK (EBITDA) ile çalışmaz. 
    Özkaynak Kârlılığı (ROE) ve Aşırı Getiri (Residual Income) modeline tabidir.
    """
    
    SECTOR_BETA = 0.95               # Piyasa riskine paralel, ancak faiz oranlarına aşırı duyarlı
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.INSURANCE
        
        logger.info(f"[{ticker}] Sigortacılık Residual Income Modeli çalıştırılıyor.")
        
        # Sigorta şirketi için Defter Değeri ve Net Kâr aranır
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        net_income_keys = get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME)
        
        if not equity_keys or not net_income_keys:
            return 0.0, {"warning": "Missing Taxonomy for Insurance"}
            
        current_book_value_cents = float(df.loc[equity_keys, df.columns[-1]].sum(skipna=True))
        net_income_ttm_cents = float(df.loc[net_income_keys, df.columns[-4:]].sum().sum())
        
        if current_book_value_cents <= 0:
            return 0.0, {"warning": "Negative Book Value (Teknik İflas Durumu)"}
            
        current_roe = net_income_ttm_cents / current_book_value_cents
        
        # Sermaye Maliyeti
        risk_free_rate = 0.35  
        erp = 0.08             
        coe = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # Sigortacılıkta poliçe primleri enflasyonla artar.
        target_roe = coe + 0.03 # Sigortalar faiz ortamında maliyeti yenme şansına sahiptir
        roe_path = [current_roe - ((current_roe - target_roe) / self.PROJECTION_YEARS) * i for i in range(1, self.PROJECTION_YEARS + 1)]
        
        dividend_payout_ratio = 0.40 # Sigortalar bankalara göre daha çok temettü dağıtır
        
        present_value_of_ri = 0.0
        projected_book_values = [current_book_value_cents]
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            year_roe = roe_path[year - 1]
            prev_bv = projected_book_values[-1]
            
            net_income = prev_bv * year_roe
            retained_earnings = net_income * (1 - dividend_payout_ratio)
            projected_book_values.append(prev_bv + retained_earnings)
            
            residual_income = (year_roe - coe) * prev_bv
            present_value_of_ri += residual_income / ((1 + coe) ** year)

        terminal_ri = (roe_path[-1] - coe) * projected_book_values[-1]
        pv_of_terminal_ri = (terminal_ri / coe) / ((1 + coe) ** self.PROJECTION_YEARS)

        target_equity_value_cents = current_book_value_cents + present_value_of_ri + pv_of_terminal_ri

        return target_equity_value_cents / 100.0, {
            "model_used": "Insurance_Residual_Income",
            "current_roe": current_roe,
            "cost_of_equity": coe
        }