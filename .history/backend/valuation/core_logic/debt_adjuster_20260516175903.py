import logging
from typing import Dict, Any, Tuple
import pandas as pd
from valuation.bist_registry import ValuationArchetype, FinancialGroupCode
from valuation.core_logic.taxonomy_registry import FinancialConcept, StatementType, CONCEPT_TYPE_MAP, get_taxonomy_keys

logger = logging.getLogger(__name__)

class NetDebtAdjuster:
    """
    Şirketin son Bilanço fotoğrafına (Snapshot) bakarak Net Borç pozisyonunu hesaplar.
    IFRS-16 (Kiralama Yükümlülükleri) de gerçek borç olarak hesaba katılır.
    """
    
    DEBT_ADJUSTABLE_ARCHETYPES = {
        ValuationArchetype.CYCLICAL_DCF,
        ValuationArchetype.STABLE_COMPOUNDER,
        ValuationArchetype.GROWTH_OPTIONALITY,
        ValuationArchetype.ASSET_NAV
    }

    def _extract_latest_sum(self, df: pd.DataFrame, concept: FinancialConcept, reporting_group: FinancialGroupCode) -> int:
        """
        Bilanço kalemlerini (Stock) son çeyreğe (Latest Snapshot) göre toplar.
        """
        # Type-Level Enforcement: Flow kalemleri snapshot olarak çekilemez!
        if CONCEPT_TYPE_MAP.get(concept) == StatementType.FLOW:
            raise TypeError(f"{concept.value} bir FLOW (Akış) kalemidir. Snapshot olarak çekilemez.")
            
        keys = get_taxonomy_keys(reporting_group, concept)
        existing_keys = [k for k in keys if k in df.index]
        
        if not existing_keys:
            return 0
            
        # df.columns (PeriodIndex) kronolojik sıralı olduğu için son eleman 'Latest Snapshot'tır.
        latest_period_col = df.columns[-1]
        total = df.loc[existing_keys, latest_period_col].sum(skipna=True)
        
        if pd.isna(total):
            return 0
        return int(total)

    def adjust_for_net_debt(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any],
        archetype: ValuationArchetype,
        reporting_group: FinancialGroupCode
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        
        if archetype not in self.DEBT_ADJUSTABLE_ARCHETYPES:
            return df, metadata

        logger.info(f"[{ticker}] IFRS-16 destekli Net Borç Düzeltmesi (Debt Adjustment) yapılıyor.")
        
        # Toplam Kasa (Nakit + Finansal Yatırımlar)
        cash = self._extract_latest_sum(df, FinancialConcept.CASH_EQUIVALENTS, reporting_group)
        investments = self._extract_latest_sum(df, FinancialConcept.ST_FINANCIAL_INVESTMENTS, reporting_group)
        total_cash = cash + investments
                     
        # Standart Finansal Borç (Kısa + Uzun)
        st_debt = self._extract_latest_sum(df, FinancialConcept.ST_DEBT, reporting_group)
        lt_debt = self._extract_latest_sum(df, FinancialConcept.LT_DEBT, reporting_group)
        
        # IFRS-16 Kiralama Yükümlülükleri (Havayolları, Perakende için ölümcül derecede önemli)
        st_lease = self._extract_latest_sum(df, FinancialConcept.ST_LEASE_LIABILITIES, reporting_group)
        lt_lease = self._extract_latest_sum(df, FinancialConcept.LT_LEASE_LIABILITIES, reporting_group)
        
        total_debt = st_debt + lt_debt + st_lease + lt_lease

        # Net Borç = Toplam Borç (Lease dahil) - Toplam Kasa
        net_debt = total_debt - total_cash

        # Snapshot verisini Pydantic Schema veya Dictionary olarak Metadata'ya kaydet
        metadata.setdefault("balance_sheet_snapshot", {})
        metadata["balance_sheet_snapshot"].update({
            "period": str(df.columns[-1]),
            "total_cash_cents": total_cash,
            "total_debt_cents": total_debt,
            "ifrs_16_lease_cents": st_lease + lt_lease,
            "net_debt_cents": net_debt,
            "is_net_cash_position": net_debt < 0
        })
        
        return df, metadata