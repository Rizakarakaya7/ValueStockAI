import logging
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np

from valuation.bist_registry import CompanyArchetype, FinancialGroupCode
from valuation.core_logic.taxonomy_registry import (
    get_taxonomy_keys, 
    FinancialConcept, 
    CONCEPT_TYPE_MAP, 
    StatementType
)

logger = logging.getLogger(__name__)

class NormalizationLogicError(Exception):
    pass

class IncompatibleArchetypeError(NormalizationLogicError):
    pass

class EarningsNormalizer:
    """
    Şirketlerin 'Kümülatif' bilançolarını 'Yalın Çeyreklik' (Discrete) hale getiren,
    TTM (Son 12 Ay) üreten ve sürdürülebilir FAVÖK hesaplayan kuantitatif motor.
    """
    
    # FAVÖK (EBITDA) matematiğinin anlamlı olduğu değerleme şablonları
    EBITDA_COMPATIBLE_ARCHETYPES = {
        CompanyArchetype.CYCLICAL,
        CompanyArchetype.COMPOUNDER,
        CompanyArchetype.HYPER_GROWTH,
        CompanyArchetype.CAPACITY_GROWTH,
        CompanyArchetype.J_CURVE,
        CompanyArchetype.REGULATED_YIELD,
        CompanyArchetype.BACKLOG_DRIVEN,
        CompanyArchetype.SUBSCRIPTION,
        CompanyArchetype.DEPLETING_ASSET,
        CompanyArchetype.CONSUMER_STAPLES
    }

    def __init__(self, median_lookback_years: int = 5):
        self.lookback_years = median_lookback_years

    def _extract_sum(self, df: pd.DataFrame, keys: List[str], required: bool = False) -> pd.Series:
        """Belirtilen metin/API kodlarını GÜVENLİ (Double-Count olmadan) şekilde çeker."""
        existing_keys = [k for k in keys if k in df.index]
        
        if not existing_keys:
            if required:
                raise NormalizationLogicError(f"Kritik finansal kalemler eksik: {keys}")
            return pd.Series(0, index=df.columns, dtype="Int64")
            
        # KRİTİK DÜZELTME: Veri katlanmasını (Double Counting) engellemek için 
        # sum() KULLANMIYORUZ! Sadece eşleşen İLK geçerli anahtarı alıyoruz.
        primary_key = existing_keys[0]
        return df.loc[primary_key].astype("Int64")

    def _convert_cumulative_to_discrete(self, df: pd.DataFrame, flow_keys: List[str]) -> pd.DataFrame:
        discrete_df = df.copy()
        
        existing_flow_keys = [k for k in flow_keys if k in discrete_df.index]
        if not existing_flow_keys:
            return discrete_df
            
        periods = sorted(discrete_df.columns)
        
        for i in range(len(periods) - 1, 0, -1):
            current_p = periods[i]
            prev_p = periods[i-1]
            
            if current_p.year == prev_p.year:
                discrete_df.loc[existing_flow_keys, current_p] = \
                    df.loc[existing_flow_keys, current_p] - df.loc[existing_flow_keys, prev_p]
                    
        return discrete_df

    def _calculate_ttm(self, series: pd.Series) -> pd.Series:
        return series.astype(float).rolling(window=4, min_periods=4).sum().round(0).astype("Int64")

    def normalize_earnings(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any],
        archetype: CompanyArchetype
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Earnings Normalization başlatıldı.")
        
        if archetype not in self.EBITDA_COMPATIBLE_ARCHETYPES:
            logger.info(f"[{ticker}] Archetype {archetype} EBITDA uyumlu değil. Normalizasyon pas geçiliyor.")
            return df, metadata
            
        new_metadata = metadata.copy()
        new_metadata["audit_trace"] = {}

        all_flow_keys = []
        for concept, stmt_type in CONCEPT_TYPE_MAP.items():
            if stmt_type == StatementType.FLOW:
                all_flow_keys.extend(get_taxonomy_keys(FinancialGroupCode.REAL_SECTOR, concept))
            
        discrete_df = self._convert_cumulative_to_discrete(df, all_flow_keys)

        revenue_keys = get_taxonomy_keys(FinancialGroupCode.REAL_SECTOR, FinancialConcept.REVENUE)
        ebit_keys = get_taxonomy_keys(FinancialGroupCode.REAL_SECTOR, FinancialConcept.EBIT)
        depreciation_keys = get_taxonomy_keys(FinancialGroupCode.REAL_SECTOR, FinancialConcept.DEPRECIATION)
        one_off_gains_keys = get_taxonomy_keys(FinancialGroupCode.REAL_SECTOR, FinancialConcept.ONE_OFF_GAINS)
        one_off_losses_keys = get_taxonomy_keys(FinancialGroupCode.REAL_SECTOR, FinancialConcept.ONE_OFF_LOSSES)

        revenue = self._extract_sum(discrete_df, revenue_keys, required=True)
        ebit = self._extract_sum(discrete_df, ebit_keys)
        depreciation = self._extract_sum(discrete_df, depreciation_keys)
        
        one_off_gains = self._extract_sum(discrete_df, one_off_gains_keys)
        one_off_losses = self._extract_sum(discrete_df, one_off_losses_keys)

        raw_ebitda_q = ebit + depreciation
        normalized_ebitda_q = raw_ebitda_q - one_off_gains + one_off_losses
        
        discrete_df.loc['CALC_RAW_EBITDA_Q'] = raw_ebitda_q
        discrete_df.loc['CALC_NORMALIZED_EBITDA_Q'] = normalized_ebitda_q

        revenue_ttm = self._calculate_ttm(revenue)
        normalized_ebitda_ttm = self._calculate_ttm(normalized_ebitda_q)
        
        discrete_df.loc['CALC_REVENUE_TTM'] = revenue_ttm
        discrete_df.loc['CALC_NORMALIZED_EBITDA_TTM'] = normalized_ebitda_ttm

        safe_revenue_ttm = revenue_ttm.replace(0, pd.NA).astype(float)
        ttm_margins = (normalized_ebitda_ttm.astype(float) / safe_revenue_ttm).astype(float)
        
        median_ttm_margin = ttm_margins.iloc[-self.lookback_years * 4:].median()
        if pd.isna(median_ttm_margin):
            median_ttm_margin = 0.0

        smoothed_ebitda_ttm = revenue_ttm * median_ttm_margin
        discrete_df.loc['CALC_SMOOTHED_EBITDA_TTM'] = smoothed_ebitda_ttm.round(0).astype("Int64")
        
        new_metadata["audit_trace"]["one_off_gains_deducted"] = one_off_gains.to_dict()
        new_metadata["audit_trace"]["one_off_losses_added"] = one_off_losses.to_dict()
        new_metadata["audit_trace"]["applied_median_ttm_margin"] = float(median_ttm_margin)

        return discrete_df, new_metadata