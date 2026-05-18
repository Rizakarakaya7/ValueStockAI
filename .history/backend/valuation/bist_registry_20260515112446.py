import logging
from enum import Enum
from types import MappingProxyType
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class RegistryError(Exception):
    pass

class UnsupportedTickerError(RegistryError):
    pass

# ==========================================
# 1. DOMAIN ENUMS (Institutional Grade Abstractions)
# ==========================================
class SectorType(str, Enum):
    """
    İşletme Gerçekliği (Business Reality).
    Faktör modellemesi (Factor Modeling) ve döngüsel risk (Cyclical Risk) için kilit roldedir.
    """
    # Sanayi / Üretim
    PETROKIMYA = "petrokimya"
    DEMIR_CELIK = "demir_celik"
    OTOMOTIV = "otomotiv"
    CIMENTO = "cimento"
    SAVUNMA = "savunma"
    ENERJI = "enerji"
    GIDA_TARIM = "gida_tarim"
    
    # Hizmet / Büyüme
    HAVACILIK = "havacilik"
    PERAKENDE = "perakende"
    TELEKOM = "telekom"
    YAZILIM = "yazilim"
    
    # Finans / Varlık
    BANKACILIK = "bankacilik"
    SIGORTA = "sigorta"
    HOLDING = "holding"
    GYO = "gyo"

class ValuationArchetype(str, Enum):
    """
    Finansal Matematik Şablonu (Valuation Math Template).
    Hisse senedine uygulanacak temel iskonto mantığını belirler.
    """
    CYCLICAL_DCF = "cyclical_dcf"                # Yüksek CapEx, Emtia Döngüsü (Ereğli, Tüpraş)
    STABLE_COMPOUNDER = "stable_compounder"      # Düşük CapEx, Sürekli Büyüme (BİM, Yazılım)
    FINANCIAL_BALANCE_SHEET = "financial_bs"     # Bilançosu kendisi olanlar (Banka, Sigorta: DDM, ROE/COE)
    ASSET_NAV = "asset_nav"                      # Varlık toplamı ve iskonto (Holding, GYO)
    GROWTH_OPTIONALITY = "growth_optionality"    # Değeri uzak gelecekteki büyüme opsiyonlarında olanlar

class FinancialGroupCode(str, Enum):
    """API Veri Şablonları (Reporting Templates)."""
    REAL_SECTOR = "XI_29"
    BANKING = "XI_59"
    INSURANCE = "XI_63"
    BROKERAGE = "XI_64"

class HookType(str, Enum):
    """
    Piyasa Rejimi (Market Regime & Adjustments).
    String (dynamic import) tuzağını önlemek için güvenli Type Identifier.
    """
    PETROKIMYA_HOOK = "PetrokimyaHook"
    DEMIR_CELIK_HOOK = "DemirCelikHook"
    OTOMOTIV_HOOK = "OtomotivHook"
    CIMENTO_HOOK = "CimentoHook"
    SAVUNMA_HOOK = "SavunmaHook"
    HAVACILIK_HOOK = "HavacilikHook"
    PERAKENDE_HOOK = "PerakendeHook"
    TELEKOM_HOOK = "TelekomHook"
    YAZILIM_HOOK = "YazilimHook"
    BANKACILIK_HOOK = "BankacilikHook"
    SIGORTA_HOOK = "SigortaHook"
    HOLDING_HOOK = "HoldingHook"
    GYO_HOOK = "GyoHook"

class CurrencyType(str, Enum):
    """Para Birimi Semantikleri (Currency Semantics)."""
    TRY = "TRY"
    USD = "USD"
    EUR = "EUR"


# ==========================================
# 2. TICKER METADATA SCHEMAS (Factor Scoring Ready)
# ==========================================
class TickerMetadata(BaseModel):
    """
    Kurumsal Faktör Puanlama (Factor Scoring) ve Risk Ayarlamaları için
    sıkı tipli (Strict Typed) özel durumlar listesi.
    """
    export_heavy: bool = Field(default=False, description="İhracat oranı yüksek mi? (Kur/Global talep riski)")
    commodity_sensitive: bool = Field(default=False, description="Emtia döngüsüne duyarlı mı?")
    regulated_business: bool = Field(default=False, description="Fiyatlama kamu regülasyonuna mı bağlı? (Örn: Telekom/Enerji)")
    reporting_currency: CurrencyType = Field(default=CurrencyType.TRY, description="Tablo hangi kurladır?")
    functional_currency: CurrencyType = Field(default=CurrencyType.TRY, description="Gelirin asıl döviz cinsi nedir?")
    min_required_history_years: int = Field(default=5, description="Kurumsal güvenilirlik için gereken asgari bilanço yılı")
    liquidity_tier: str = Field(default="BIST30", description="Likidite iskontosu için (BIST30, BIST100, SUB100)")
    coverage_active: bool = Field(default=True, description="Sistem şu an bu hisseye analiz desteği veriyor mu?")


class TickerConfig(BaseModel):
    """Bir BİST hissesinin Değerleme Motorundaki tam (ve değişmez) rotası."""
    ticker: str
    sector: SectorType
    archetype: ValuationArchetype
    hook: HookType
    reporting_template: FinancialGroupCode
    metadata: TickerMetadata


# ==========================================
# 3. IMMUTABLE REGISTRY (Değiştirilemez Fon Haritası)
# ==========================================
# Geliştiricinin veya ajanın çalışma zamanında (runtime) bozmasını engellemek için MappingProxyType ile sarılır.

_TICKER_MAP_INTERNAL: Dict[str, TickerConfig] = {
    # --- CYCLICAL DCF (Ağır Sanayi ve Emtia Döngüsü) ---
    "TUPRS": TickerConfig(
        ticker="TUPRS", sector=SectorType.PETROKIMYA,
        archetype=ValuationArchetype.CYCLICAL_DCF, hook=HookType.PETROKIMYA_HOOK,
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata(commodity_sensitive=True, export_heavy=True, functional_currency=CurrencyType.USD)
    ),
    "EREGL": TickerConfig(
        ticker="EREGL", sector=SectorType.DEMIR_CELIK,
        archetype=ValuationArchetype.CYCLICAL_DCF, hook=HookType.DEMIR_CELIK_HOOK,
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata(commodity_sensitive=True, export_heavy=True, functional_currency=CurrencyType.USD)
    ),
    "FROTO": TickerConfig(
        ticker="FROTO", sector=SectorType.OTOMOTIV,
        archetype=ValuationArchetype.CYCLICAL_DCF, hook=HookType.OTOMOTIV_HOOK,
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata(export_heavy=True, functional_currency=CurrencyType.EUR)
    ),
    
    # --- STABLE COMPOUNDER (Sürekli Büyüme ve Hizmet) ---
    "BIMAS": TickerConfig(
        ticker="BIMAS", sector=SectorType.PERAKENDE,
        archetype=ValuationArchetype.STABLE_COMPOUNDER, hook=HookType.PERAKENDE_HOOK,
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata(regulated_business=False)
    ),
    "THYAO": TickerConfig(
        ticker="THYAO", sector=SectorType.HAVACILIK,
        archetype=ValuationArchetype.CYCLICAL_DCF, hook=HookType.HAVACILIK_HOOK, # Havacılık CAPEX ağırlıklı olduğu için DCF
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata(functional_currency=CurrencyType.USD, export_heavy=True)
    ),
    "TCELL": TickerConfig(
        ticker="TCELL", sector=SectorType.TELEKOM,
        archetype=ValuationArchetype.STABLE_COMPOUNDER, hook=HookType.TELEKOM_HOOK,
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata(regulated_business=True) # İletişim vergileri ve tarifeleri regülasyona tabidir
    ),

    # --- FINANCIAL BALANCE SHEET (Banka ve Sigorta) ---
    "AKBNK": TickerConfig(
        ticker="AKBNK", sector=SectorType.BANKACILIK,
        archetype=ValuationArchetype.FINANCIAL_BALANCE_SHEET, hook=HookType.BANKACILIK_HOOK,
        reporting_template=FinancialGroupCode.BANKING,
        metadata=TickerMetadata(regulated_business=True, min_required_history_years=3)
    ),
    
    # --- ASSET NAV (Parçaların Toplamı ve NAD) ---
    "KCHOL": TickerConfig(
        ticker="KCHOL", sector=SectorType.HOLDING,
        archetype=ValuationArchetype.ASSET_NAV, hook=HookType.HOLDING_HOOK,
        reporting_template=FinancialGroupCode.REAL_SECTOR,
        metadata=TickerMetadata()
    ),
}

# Immutable Registry (Değiştirilemez Harita)
BIST_TICKER_MAP = MappingProxyType(_TICKER_MAP_INTERNAL)

# ==========================================
# 4. REGISTRY SERVICE (Stateless Lookup Engine)
# ==========================================
class BistRegistryService:
    """Sistem genelinde hisse haritasına güvenli erişim sağlayan servis."""
    
    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        """Kullanıcı girişlerini standardize eder."""
        return ticker.strip().upper()

    @classmethod
    def get_ticker_config(cls, ticker: str) -> TickerConfig:
        """
        Güvenli yapılandırma objesini döndürür. Kapsam dışıysa veya coverage kapalıysa hata fırlatır.
        """
        clean_ticker = cls._normalize_ticker(ticker)
        
        if clean_ticker not in BIST_TICKER_MAP:
            logger.error(f"[{clean_ticker}] Sistem destek kapsaminda değil.")
            raise UnsupportedTickerError(f"{clean_ticker} henüz sistemin coverage'ında değildir.")
            
        config = BIST_TICKER_MAP[clean_ticker]
        
        if not config.metadata.coverage_active:
            raise UnsupportedTickerError(f"{clean_ticker} şu an veri kalitesi nedeniyle askıya alınmıştır.")
            
        return config
    
    @classmethod
    def is_supported(cls, ticker: str) -> bool:
        """Hissenin sistemde olup olmadığını boolean döner."""
        clean_ticker = cls._normalize_ticker(ticker)
        return clean_ticker in BIST_TICKER_MAP and BIST_TICKER_MAP[clean_ticker].metadata.coverage_active
    
    @classmethod
    def get_all_supported_tickers(cls) -> List[str]:
        """UI Dropdown'ları ve toplu analizler için alfabetik sıralı (sorted) desteklenen hisse listesi."""
        active_tickers = [
            ticker for ticker, config in BIST_TICKER_MAP.items() 
            if config.metadata.coverage_active
        ]
        return sorted(active_tickers)