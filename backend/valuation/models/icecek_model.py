import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class IcecekModel(BaseValuationModel):
    """
    İÇECEK VE HIZLI TÜKETİM SEKTÖRÜ İZOLE MODELLİ (Örn: CCOLA, AEFES)
    'Consumer Staples' arketipi. 
    """
    
    SECTOR_BETA = 0.85               
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] İçecek (Consumer Staples) DCF Modeli çalıştırılıyor.")
        
        risk_free_rate = metadata.get("macro_context", {}).get("tr_risk_free_rate", 0.35)  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_cents = ttm_ebit + ttm_da

        is_normalized_used = False
        if 'CALC_OWNERS_EARNINGS_TTM' in df.index and float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1]) > 0:
            base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        else:
            base_fcf_cents = ttm_ebitda_cents * 0.45
            is_normalized_used = True

        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif EBITDA."}

        terminal_growth_rate = risk_free_rate * 0.15 
        
        # BÜYÜME REVİZYONU: Çift sayım hatası bitince baz etki düzelecek ama 
        # enflasyon patikasını da bir tık daha muhafazakar hale getirdik.
        growth_path = [
            risk_free_rate * 0.85,  # 1. Yıl
            risk_free_rate * 0.65,  # 2. Yıl
            risk_free_rate * 0.45,  # 3. Yıl
            risk_free_rate * 0.30,  # 4. Yıl
            terminal_growth_rate    # 5. Yıl
        ] 
        
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        if discount_rate <= terminal_growth_rate:
            discount_rate = terminal_growth_rate + 0.05
            
        terminal_value = (projected_cash_flows[-1] * (1 + terminal_growth_rate)) / (discount_rate - terminal_growth_rate)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        raw_net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - raw_net_debt_cents
        
        target_equity_value_tl = max(0.0, target_equity_value_cents / 100.0)

        model_report = {
            "model_used": "Consumer_Staples_DCF",
            "is_fcf_normalized": is_normalized_used,
            "applied_wacc": discount_rate,
            "pricing_power_premium_applied": True,
            "pv_of_5_year_fcf_tl": present_value_of_fcf / 100.0,
            "enterprise_value_tl": enterprise_value_cents / 100.0,
            "net_debt_tl": raw_net_debt_cents / 100.0,
            "total_equity_value_target_tl": target_equity_value_tl
        }

        return target_equity_value_tl, model_report