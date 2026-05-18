from enum import Enum
from typing import List, Dict
from valuation.bist_registry import FinancialGroupCode

class FinancialConcept(str, Enum):
    """Sistemin anladığı evrensel finansal kavramlar (Dil ve API bağımsız)."""
    # FLOW (Akış / Gelir Tablosu)
    REVENUE = "revenue"
    EBIT = "ebit"
    DEPRECIATION = "depreciation"
    ONE_OFF_GAINS = "one_off_gains"
    ONE_OFF_LOSSES = "one_off_losses"
    
    # STOCK (Fotoğraf / Bilanço)
    CASH_EQUIVALENTS = "cash_equivalents"
    ST_FINANCIAL_INVESTMENTS = "st_financial_investments"
    ST_DEBT = "st_debt"
    LT_DEBT = "lt_debt"
    ST_LEASE_LIABILITIES = "st_lease_liabilities" # IFRS 16
    LT_LEASE_LIABILITIES = "lt_lease_liabilities" # IFRS 16

class StatementType(str, Enum):
    """Type-level validation için Bilanço (Stock) vs Gelir Tablosu (Flow) ayrımı."""
    FLOW = "flow"
    STOCK = "stock"

# Hangi kavramın Stock mu yoksa Flow mu olduğunu belirten Type-Contract
CONCEPT_TYPE_MAP: Dict[FinancialConcept, StatementType] = {
    FinancialConcept.REVENUE: StatementType.FLOW,
    FinancialConcept.DEPRECIATION: StatementType.FLOW,
    FinancialConcept.CASH_EQUIVALENTS: StatementType.STOCK,
    FinancialConcept.ST_LEASE_LIABILITIES: StatementType.STOCK,
    FinancialConcept.ST_DEBT: StatementType.STOCK,
    FinancialConcept.LT_DEBT: StatementType.STOCK,
}

# API Sağlayıcıya ve Sektöre (GroupCode) Göre Dinamik Eşleşme
FINANCIAL_TAXONOMY: Dict[FinancialGroupCode, Dict[FinancialConcept, List[str]]] = {
    FinancialGroupCode.REAL_SECTOR: {
        FinancialConcept.REVENUE: ["SKEY_111"],
        FinancialConcept.EBIT: ["SKEY_120"],
        FinancialConcept.DEPRECIATION: ["SKEY_150"],
        FinancialConcept.CASH_EQUIVALENTS: ["SKEY_11"],
        FinancialConcept.ST_FINANCIAL_INVESTMENTS: ["SKEY_12"],
        FinancialConcept.ST_DEBT: ["SKEY_31", "SKEY_32"],
        FinancialConcept.LT_DEBT: ["SKEY_41"],
        # IFRS-16 Kiralama Yükümlülükleri (Gerçek borçtur)
        FinancialConcept.ST_LEASE_LIABILITIES: ["SKEY_33"], 
        FinancialConcept.LT_LEASE_LIABILITIES: ["SKEY_42"],
    },
    # Bankacılık için İş Yatırım kodları ileride buraya eklenecek
    FinancialGroupCode.BANKING: {
        FinancialConcept.REVENUE: ["BANK_SKEY_XYZ"], 
    }
}

def get_taxonomy_keys(group: FinancialGroupCode, concept: FinancialConcept) -> List[str]:
    """Sektöre özel API kodlarını güvenli şekilde döndürür."""
    return FINANCIAL_TAXONOMY.get(group, {}).get(concept, [])