from enum import Enum
from typing import List, Dict
from valuation.bist_registry import FinancialGroupCode

class FinancialConcept(str, Enum):
    """Sistemin anladığı evrensel finansal kavramlar (Dil ve API bağımsız)."""
    # FLOW (Akış / Gelir Tablosu & Nakit Akışı)
    REVENUE = "revenue"
    EBIT = "ebit"
    DEPRECIATION = "depreciation"
    NET_INCOME = "net_income" # <-- EKLENDİ (Bankacılık modeli için)
    NET_INCOME_PARENT = "net_income_parent"
    ONE_OFF_GAINS = "one_off_gains"
    ONE_OFF_LOSSES = "one_off_losses"
    
    # STOCK (Fotoğraf / Bilanço)
    TOTAL_EQUITY = "total_equity"
    PARENT_EQUITY = "parent_equity"
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
    FinancialConcept.EBIT: StatementType.FLOW,
    FinancialConcept.DEPRECIATION: StatementType.FLOW,
    FinancialConcept.NET_INCOME: StatementType.FLOW, # <-- EKLENDİ
    FinancialConcept.NET_INCOME_PARENT: StatementType.FLOW,
    FinancialConcept.CASH_EQUIVALENTS: StatementType.STOCK,
    FinancialConcept.ST_LEASE_LIABILITIES: StatementType.STOCK,
    FinancialConcept.ST_DEBT: StatementType.STOCK,
    FinancialConcept.LT_DEBT: StatementType.STOCK,
    FinancialConcept.TOTAL_EQUITY: StatementType.STOCK,
    FinancialConcept.PARENT_EQUITY: StatementType.STOCK,
}

# Yahoo Finance Evrensel Terminolojisine Göre Güncellenmiş Dinamik Eşleşme
FINANCIAL_TAXONOMY: Dict[FinancialGroupCode, Dict[FinancialConcept, List[str]]] = {
    FinancialGroupCode.REAL_SECTOR: {
        # Gelir Tablosu
        FinancialConcept.REVENUE: ["Total Revenue", "Operating Revenue"],
        FinancialConcept.EBIT: ["EBIT", "Operating Income"],
        FinancialConcept.DEPRECIATION: ["Reconciled Depreciation", "Depreciation And Amortization", "Depreciation"],
        FinancialConcept.NET_INCOME: ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing And Discontinued Operation"], # <-- BURAYI EKLEDİK
        FinancialConcept.NET_INCOME_PARENT: ["Net Income Common Stockholders", "Net Income"],
        FinancialConcept.ONE_OFF_GAINS: ["Gain On Sale Of Security", "Other Non Operating Income Expenses"],
        FinancialConcept.ONE_OFF_LOSSES: ["Restructuring And Mergern Acquisition", "Impairment Of Capital Assets"],
        
        # Bilanço
        FinancialConcept.TOTAL_EQUITY: ["Stockholders Equity", "Total Equity Gross Minority Interest", "Total Equity"],
        FinancialConcept.PARENT_EQUITY: ["Stockholders Equity"],
        FinancialConcept.CASH_EQUIVALENTS: ["Cash And Cash Equivalents", "Cash", "Cash Cash Equivalents And Short Term Investments"],
        FinancialConcept.ST_FINANCIAL_INVESTMENTS: ["Other Short Term Investments", "Short Term Investments"],
        
        # Borç ve Yükümlülükler
        FinancialConcept.ST_DEBT: ["Current Debt", "Current Debt And Capital Lease Obligation", "Short Long Term Debt"],
        FinancialConcept.LT_DEBT: ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        FinancialConcept.ST_LEASE_LIABILITIES: ["Current Capital Lease Obligation", "Current Lease Liabilities"], 
        FinancialConcept.LT_LEASE_LIABILITIES: ["Long Term Capital Lease Obligation", "Long Term Lease Liabilities"],
    },
    
    # Bankacılık modeli entegre edildiğinde bu alan kullanılacak
    FinancialGroupCode.BANKING: {
        FinancialConcept.REVENUE: ["Total Revenue", "Interest Income", "Net Interest Income"], 
        FinancialConcept.NET_INCOME: ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing And Discontinued Operation"], # <-- EKLENDİ
        FinancialConcept.TOTAL_EQUITY: ["Stockholders Equity", "Total Equity Gross Minority Interest", "Total Equity"], # Bankalar için özkaynak kritiktir, eklendi.
    }
}

def get_taxonomy_keys(group: FinancialGroupCode, concept: FinancialConcept) -> List[str]:
    """Sektöre özel API kodlarını güvenli şekilde döndürür."""
    return FINANCIAL_TAXONOMY.get(group, {}).get(concept, [])