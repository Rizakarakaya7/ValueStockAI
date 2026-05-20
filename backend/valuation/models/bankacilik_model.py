import pandas as pd
from typing import Dict, Any, Tuple
from decimal import Decimal
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class BankacilikModel(BaseValuationModel):
    """
    BANKACILIK SEKTÖRÜ İZOLE MODELLİ
    Sürekli Fonksiyonlar ve Gordon Güvenlik Tamponu ile Stabilize Edilmiş 
    Justified P/B Modeli.
    """

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.BANKING
        macro_context = metadata.get("macro_context", {})
        
        logger.info(f"[{ticker}] Sürekli Bankacılık Motoru (Justified P/B) çalıştırılıyor.")
        
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        net_income_keys = get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME)
        
        existing_equity_keys = [k for k in equity_keys if k in df.index]
        existing_ni_keys = [k for k in net_income_keys if k in df.index]
        
        if not existing_equity_keys or not existing_ni_keys:
            logger.error(f"[{ticker}] Banka değerlemesi için gerekli veriler bulunamadı.")
            return 0.0, {"warning": "Missing Data"}
            
        current_equity_cents = float(df.loc[existing_equity_keys, df.columns[-1]].sum(skipna=True))
        net_income_ttm_cents = float(df.loc[existing_ni_keys, df.columns[-4:]].sum().sum())
        
        if current_equity_cents <= 0:
            return 0.0, {"warning": "Negative Equity (İflas Riski)"}

        trailing_roe = net_income_ttm_cents / current_equity_cents
        normalized_roe = min(trailing_roe, 0.35) 
        
        base_risk_free_rate = macro_context.get("risk_free_rate", 0.35) 
        base_erp = macro_context.get("equity_risk_premium", 0.08)
        beta = macro_context.get("sector_beta", 1.30)
        
        base_coe = base_risk_free_rate + (beta * base_erp) 
        quality_discount = normalized_roe * 0.25
        raw_coe = base_coe - quality_discount
        cost_of_equity = max(0.15, min(0.50, raw_coe))

        base_growth = macro_context.get("long_term_growth_rate", 0.04)
        growth_premium = normalized_roe * 0.15
        raw_growth = base_growth + growth_premium
        growth = max(0.04, min(0.12, raw_growth))
        
        spread_floor = 0.08
        if (cost_of_equity - growth) < spread_floor:
            growth = cost_of_equity - spread_floor

        if cost_of_equity <= growth:
            justified_pb = 1.0 
        else:
            justified_pb = (normalized_roe - growth) / (cost_of_equity - growth)
            
        target_pb = max(0.40, min(1.80, justified_pb))

        target_equity_value_cents = current_equity_cents * target_pb
        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Banking_Justified_PB",
            "current_book_value_tl": current_equity_cents / 100,
            "trailing_roe": trailing_roe,
            "normalized_roe": normalized_roe,
            "cost_of_equity_coe": cost_of_equity,
            "long_term_growth_g": growth,
            "target_justified_pb": target_pb
        }

        return target_equity_value_tl, model_report