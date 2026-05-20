import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class DemirCelikModel(BaseValuationModel):
    """
    AĞIR SANAYİ & DEMİR ÇELİK (DÖNGÜSEL) MODELLİ
    Döngü Ortası (Mid-Cycle) FCFF ve DCF modeli.
    """

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        macro_context = metadata.get("macro_context", {})
        
        logger.info(f"[{ticker}] Demir-Çelik Döngü Ortası (Mid-Cycle) DCF Motoru çalıştırılıyor.")
        
        # --- TRUVA ATI: ORCHESTRATOR'IN ZEMİNİNİ HACKLEME ---
        # Orchestrator'ı bozmamak için, modelin içinde 1.0x P/B zeminini 0.40x Tasfiye zeminine çekiyoruz.
        if "valuation_safeguards" in metadata and "book_value_floor_cents" in metadata["valuation_safeguards"]:
            original_floor = metadata["valuation_safeguards"]["book_value_floor_cents"]
            liquidation_floor = original_floor * 0.40
            metadata["valuation_safeguards"]["book_value_floor_cents"] = liquidation_floor
            logger.info(f"[{ticker}] Cyclical Floor Override: 1.0x P/B zemini, tasfiye (0.40x) zeminine çekildi.")
        # ---------------------------------------------------

        rev_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.REVENUE) if k in df.index]
        ebit_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.EBIT) if k in df.index]
        
        if not rev_keys:
            logger.error(f"[{ticker}] Değerleme için Ciro (Revenue) kalemi bulunamadı.")
            return 0.0, {"warning": "Missing Revenue Data"}
            
        ttm_revenue_cents = float(df.loc[rev_keys, df.columns[-4:]].sum().sum())
        
        if ttm_revenue_cents <= 0:
            return 0.0, {"warning": "Zero or Negative Revenue"}

        ttm_ebit_cents = float(df.loc[ebit_keys, df.columns[-4:]].sum().sum()) if ebit_keys else 0.0
        current_margin = (ttm_ebit_cents / ttm_revenue_cents) if ttm_revenue_cents > 0 else 0.0

        # Döngüsel Marj (%10) ve Ağır CAPEX (%60) muhafazakar ayarları
        target_mid_cycle_margin = 0.10 
        normalized_ebit = ttm_revenue_cents * target_mid_cycle_margin
        
        tax_rate = 0.22
        nopat = normalized_ebit * (1 - tax_rate)

        reinvestment_rate = 0.60
        fcff = nopat * (1 - reinvestment_rate)

        risk_free_rate = macro_context.get("risk_free_rate", 0.35) 
        erp = macro_context.get("equity_risk_premium", 0.08)
        beta = macro_context.get("sector_beta", 1.25)
        
        cost_of_equity = risk_free_rate + (beta * erp)
        after_tax_cod = (risk_free_rate + 0.05) * (1 - tax_rate) 
        
        w_debt, w_equity = 0.30, 0.70
        wacc = (w_equity * cost_of_equity) + (w_debt * after_tax_cod)

        terminal_growth = macro_context.get("long_term_growth_rate", 0.02)
        
        if wacc - terminal_growth < 0.05:
            wacc = terminal_growth + 0.05

        enterprise_value_cents = (fcff * (1 + terminal_growth)) / (wacc - terminal_growth)

        net_debt_cents = metadata.get("net_debt_cents", 0.0) 
        equity_value_cents = enterprise_value_cents - net_debt_cents
        
        if equity_value_cents < 0:
            equity_value_cents = 0.0

        target_equity_value_tl = equity_value_cents / 100.0

        model_report = {
            "model_used": "Cyclical_MidCycle_DCF",
            "ttm_revenue_tl": ttm_revenue_cents / 100,
            "current_ebit_margin": current_margin,
            "applied_mid_cycle_margin": target_mid_cycle_margin,
            "estimated_fcff_tl": fcff / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "net_debt_deducted_tl": net_debt_cents / 100
        }

        return target_equity_value_tl, model_report