import logging
from typing import Dict, Any, Tuple
import pandas as pd
from valuation.bist_registry import ValuationArchetype, FinancialGroupCode
from valuation.core_logic.taxonomy_registry import FinancialConcept, StatementType, CONCEPT_TYPE_MAP, get_taxonomy_keys

logger = logging.getLogger(__name__)

class PipelineContractError(Exception):
    pass

class CapexDeductor:
    """
    Sürdürülebilir FAVÖK'ten (EBITDA), operasyonu hayatta tutmak için gereken 
    zorunlu bakım yatırımlarını (Maintenance CapEx) düşerek 
    Serbest Nakit Akışı zeminini (Owner's Earnings) hazırlar.
    """
    
    CAPEX_COMPATIBLE_ARCHETYPES = {
        ValuationArchetype.CYCLICAL_DCF,
        ValuationArchetype.STABLE_COMPOUNDER
    }

    REQUIRED_ROWS = ['CALC_SMOOTHED_EBITDA_TTM']
    EXPECTED_FREQ = 'Q'

    def apply_capex_deduction(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any],
        archetype: ValuationArchetype,
        reporting_group: FinancialGroupCode
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        
        # 1. ARCHETYPE GATE (Banka ve Holdingleri Korumak)
        if archetype not in self.CAPEX_COMPATIBLE_ARCHETYPES:
            return df, metadata

        # 2. PIPELINE DATA CONTRACT VALIDATION
        if not hasattr(df.columns, 'freqstr') or df.columns.freqstr != self.EXPECTED_FREQ:
            raise PipelineContractError(f"[{ticker}] DataFrame columns PeriodIndex(freq='Q') formatında değil.")
            
        missing_rows = [row for row in self.REQUIRED_ROWS if row not in df.index]
        if missing_rows:
            raise PipelineContractError(f"[{ticker}] Normalization katmanından gelmesi gereken satırlar eksik: {missing_rows}")

        logger.info(f"[{ticker}] Maintenance CapEx Tırpanı uygulanıyor.")
        
        # In-place (Mutable) pipeline mantığı (Memory explosion'ı önlemek için df.copy() kaldırıldı)
        
        # 3. DYNAMIC TAXONOMY LOOKUP (Hardcode SKEY kaldırıldı)
        depreciation_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        existing_keys = [k for k in depreciation_keys if k in df.index]
        
        if not existing_keys:
            logger.warning(f"[{ticker}] Amortisman verisi ({depreciation_keys}) bulunamadı. CapEx kesintisi 0 kabul edilecek.")
            maintenance_capex = pd.Series(0, index=df.columns, dtype="Int64")
        else:
            # Type-Level Stock/Flow Validation (Yanlışlıkla Bilanço kaleminin rolling'e girmesini önler)
            if CONCEPT_TYPE_MAP.get(FinancialConcept.DEPRECIATION) != StatementType.FLOW:
                raise TypeError("Amortisman bir FLOW kalemi olmalıdır. Yanlış haritalama (Taxonomy Mapping Error).")
                
            # Int64 tabanlı toplama ve mutlak değer alımı
            maintenance_capex = df.loc[existing_keys].sum(skipna=True).astype(float).abs().astype("Int64")
            
        # 4. TTM (Trailing Twelve Months) GÜVENLİ HESAPLAMASI
        # Float64 Extension kullanarak precision drift'i önlüyoruz
        smoothed_ebitda_ttm = df.loc['CALC_SMOOTHED_EBITDA_TTM']
        
        # Güvenli TTM: Eğer ilk halka arzlarda 4 çeyrek yoksa NaN döner (silent aggregation engellendi)
        maintenance_capex_ttm = maintenance_capex.astype("Float64").rolling(window=4, min_periods=4).sum().round(0).astype("Int64")
        
        # 5. OWNER'S EARNINGS HESAPLAMASI (Simplified Proxy Method)
        owners_earnings_ttm = smoothed_ebitda_ttm - maintenance_capex_ttm
        
        # DataFrame Mutation
        df.loc['CALC_MAINTENANCE_CAPEX_TTM'] = maintenance_capex_ttm
        df.loc['CALC_OWNERS_EARNINGS_TTM'] = owners_earnings_ttm

        # 6. METADATA VE AUDIT TRACE
        metadata.setdefault("audit_trace", {})
        metadata["audit_trace"]["capex_deduction_applied"] = True
        metadata["methodology"] = metadata.get("methodology", {})
        metadata["methodology"]["owners_earnings_method"] = "proxy_da_based" # Gerçek metod olmadığını vurgular

        return df, metadata