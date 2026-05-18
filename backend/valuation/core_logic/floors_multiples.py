import logging
from typing import Dict, Any, Tuple, Optional
import pandas as pd

# DÜZELTİLDİ: ValuationArchetype yerine CompanyArchetype import edildi.
from valuation.bist_registry import CompanyArchetype, FinancialGroupCode, SectorType
from valuation.core_logic.taxonomy_registry import FinancialConcept, StatementType, CONCEPT_TYPE_MAP, get_taxonomy_keys

logger = logging.getLogger(__name__)

class PipelineContractError(Exception):
    pass

class ValuationSafeguards:
    """
    Şirketlerin değerlemesinde 'Sıfırın Altı' (Negative Enterprise Value) absürtlüklerini
    engellemek için 'Defter Değeri Zemini' (Book Value Floor) oluşturur.
    Ayrıca Sektör ve Şirket çarpanlarını harmanlayarak (Mean Reversion) Hedef Çarpanı belirler.
    """
    
    # DÜZELTİLDİ: Enum değerleri güncellendi
    FLOOR_COMPATIBLE_ARCHETYPES = {
        CompanyArchetype.CYCLICAL,
        CompanyArchetype.COMPOUNDER,
        CompanyArchetype.HYPER_GROWTH,
        CompanyArchetype.CAPACITY_GROWTH,
        CompanyArchetype.J_CURVE,
        CompanyArchetype.SUBSCRIPTION,
        CompanyArchetype.BACKLOG_DRIVEN,
        CompanyArchetype.REGULATED_YIELD,
        CompanyArchetype.DEPLETING_ASSET
    }

    def __init__(self, company_weight: float = 0.60, sector_weight: float = 0.40):
        if round(company_weight + sector_weight, 2) != 1.00:
            raise ValueError("Şirket ve Sektör çarpan ağırlıkları toplamı 1.0 (100%) olmak zorundadır.")
        
        self.company_weight = company_weight
        self.sector_weight = sector_weight

    def _extract_latest_equity(self, df: pd.DataFrame, reporting_group: FinancialGroupCode) -> int:
        """
        Şirketin 'Ana Ortaklığa Ait Özkaynaklar' (Total Equity / Book Value)
        fotoğrafını son çeyrek snapshot'ı üzerinden çeker.
        """
        if CONCEPT_TYPE_MAP.get(FinancialConcept.TOTAL_EQUITY) == StatementType.FLOW:
            raise TypeError("Özkaynaklar bir STOCK (Bilanço) kalemidir. FLOW olarak ayarlanamaz.")
            
        keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        existing_keys = [k for k in keys if k in df.index]
        
        if not existing_keys:
            return 0
            
        latest_period_col = df.columns[-1]
        total_equity = df.loc[existing_keys, latest_period_col].sum(skipna=True)
        
        if pd.isna(total_equity):
            return 0
        return int(total_equity)

    def calculate_blended_multiple(
        self, 
        company_historical_ev_ebitda: Optional[float], 
        sector_median_ev_ebitda: Optional[float]
    ) -> float:
        """
        Kurumsal 'Ortalamaya Dönüş' (Mean Reversion) felsefesiyle çarpanları harmanlar.
        Eksik veri durumunda (Örn: Yeni halka arz veya sektör verisi yokluğu) Graceful Degradation (Zarif Düşüş) uygular.
        """
        if company_historical_ev_ebitda and sector_median_ev_ebitda:
            return (company_historical_ev_ebitda * self.company_weight) + (sector_median_ev_ebitda * self.sector_weight)
        
        elif company_historical_ev_ebitda:
            logger.warning("Sektör medyan çarpanı bulunamadı. %100 Şirket geçmişi kullanılacak.")
            return company_historical_ev_ebitda
            
        elif sector_median_ev_ebitda:
            logger.warning("Şirket geçmiş çarpanı bulunamadı. %100 Sektör medyanı kullanılacak.")
            return sector_median_ev_ebitda
            
        else:
            logger.error("Ne şirket ne de sektör çarpanı mevcut! Fallback mekanizması tetiklendi.")
            return 8.0 # Global gelişmekte olan piyasalar (EM) için muhafazakar Fallback EV/EBITDA çarpanı

    def apply_safeguards(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any],
        archetype: CompanyArchetype, # DÜZELTİLDİ: Tip belirteci güncellendi
        reporting_group: FinancialGroupCode,
        company_hist_multiple: Optional[float] = None,
        sector_med_multiple: Optional[float] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        
        if archetype not in self.FLOOR_COMPATIBLE_ARCHETYPES:
            return df, metadata

        logger.info(f"[{ticker}] Zemin Koruması (Book Value Floor) ve Çarpan Harmanlaması çalıştırılıyor.")
        
        # 1. BOOK VALUE FLOOR (Özkaynak Zemini)
        total_equity_cents = self._extract_latest_equity(df, reporting_group)
        
        # 2. BLENDED MULTIPLE (Hedef Çarpan)
        target_multiple = self.calculate_blended_multiple(company_hist_multiple, sector_med_multiple)

        # 3. METADATA GÜNCELLEMESİ (Audit Trace & Contract Enforcement)
        metadata.setdefault("valuation_safeguards", {})
        metadata["valuation_safeguards"].update({
            "book_value_floor_cents": total_equity_cents,
            "target_blended_multiple": round(target_multiple, 2),
            "blend_weights": {
                "company": self.company_weight,
                "sector": self.sector_weight
            }
        })
        
        return df, metadata