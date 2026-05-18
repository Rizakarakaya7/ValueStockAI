import logging
from enum import Enum
from typing import Dict
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ==========================================
# 1. TEMEL ENUMLAR (Sistem Sabitleri)
# ==========================================
class CurrencyType(Enum):
    TRY = "TRY"
    USD = "USD"
    EUR = "EUR"

class SectorType(Enum):
    DEMIR_CELIK = "Demir_Celik"
    OTOMOTIV = "Otomotiv"
    PERAKENDE = "Perakende"
    HAVACILIK = "Havacilik"
    TELEKOM = "Telekom"
    CIMENTO = "Cimento"
    SIGORTA = "Sigorta"
    TEKNOLOJI = "Teknoloji"
    SAVUNMA = "Savunma"
    ENERJI = "Enerji"
    MADENCILIK = "Madencilik"
    BANKACILIK = "Bankacilik"
    HOLDING = "Holding"
    PETROKIMYA = "Petrokimya"

class CompanyArchetype(Enum):
    CYCLICAL = "Cyclical"
    J_CURVE = "J_Curve"
    COMPOUNDER = "Compounder"
    CAPACITY_GROWTH = "Capacity_Growth"
    SUBSCRIPTION = "Subscription"
    FINANCIAL = "Financial"
    DEPLETING_ASSET = "Depleting_Asset"
    HOLDING_CO = "Holding_Co"
    REGULATED_YIELD = "Regulated_Yield"
    HYPER_GROWTH = "Hyper_Growth"
    BACKLOG_DRIVEN = "Backlog_Driven"

class ReportingTemplate(Enum):
    SANAYI = "XI_29"
    BANKA = "XI_59" 
    SIGORTA = "XI_29_Sigorta" 

# ==========================================
# 2. ŞİRKET KÜNYESİ (Data Model)
# ==========================================
class TickerConfig(BaseModel):
    ticker: str
    sector: SectorType
    archetype: CompanyArchetype
    reporting_template: ReportingTemplate
    currency: CurrencyType = CurrencyType.TRY # Varsayılan olarak TRY atadık

# ==========================================
# 3. KAYIT SERVİSİ (Registry Service)
# ==========================================
class BistRegistryService:
    """
    Sisteme gelen hissenin hangi sektörde olduğunu ve hangi şablonla 
    verisinin çekileceğini belirleyen statik harita.
    """
    
    _registry: Dict[str, TickerConfig] = {
        # OTOMOTIV
        "FROTO": TickerConfig(ticker="FROTO", sector=SectorType.OTOMOTIV, archetype=CompanyArchetype.J_CURVE, reporting_template=ReportingTemplate.SANAYI),
        "TOASO": TickerConfig(ticker="TOASO", sector=SectorType.OTOMOTIV, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        
        # HAVACILIK (Örn: THYAO bilançosunu USD tutar, buraya eklenebilir)
        "THYAO": TickerConfig(ticker="THYAO", sector=SectorType.HAVACILIK, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        "PGSUS": TickerConfig(ticker="PGSUS", sector=SectorType.HAVACILIK, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.EUR),
        
        # PETROKİMYA & RAFİNERİ
        "TUPRS": TickerConfig(ticker="TUPRS", sector=SectorType.PETROKIMYA, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "PETKM": TickerConfig(ticker="PETKM", sector=SectorType.PETROKIMYA, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        
        # HOLDİNG
        "KCHOL": TickerConfig(ticker="KCHOL", sector=SectorType.HOLDING, archetype=CompanyArchetype.HOLDING_CO, reporting_template=ReportingTemplate.SANAYI),
        "SAHOL": TickerConfig(ticker="SAHOL", sector=SectorType.HOLDING, archetype=CompanyArchetype.HOLDING_CO, reporting_template=ReportingTemplate.SANAYI),
        
        # BANKACILIK
        "AKBNK": TickerConfig(ticker="AKBNK", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "ISCTR": TickerConfig(ticker="ISCTR", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "YKBNK": TickerConfig(ticker="YKBNK", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        
        # SAVUNMA & TEKNOLOJİ
        "ASELS": TickerConfig(ticker="ASELS", sector=SectorType.SAVUNMA, archetype=CompanyArchetype.BACKLOG_DRIVEN, reporting_template=ReportingTemplate.SANAYI),
        "MIATK": TickerConfig(ticker="MIATK", sector=SectorType.TEKNOLOJI, archetype=CompanyArchetype.HYPER_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        
        # MADENCİLİK & DEMİR ÇELİK
        "KOZAL": TickerConfig(ticker="KOZAL", sector=SectorType.MADENCILIK, archetype=CompanyArchetype.DEPLETING_ASSET, reporting_template=ReportingTemplate.SANAYI),
        "EREGL": TickerConfig(ticker="EREGL", sector=SectorType.DEMIR_CELIK, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        
        # PERAKENDE
        "BIMAS": TickerConfig(ticker="BIMAS", sector=SectorType.PERAKENDE, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),
        "MGROS": TickerConfig(ticker="MGROS", sector=SectorType.PERAKENDE, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),
        
        # ENERJİ & TELEKOM & ÇİMENTO & SİGORTA
        "ENJSA": TickerConfig(ticker="ENJSA", sector=SectorType.ENERJI, archetype=CompanyArchetype.REGULATED_YIELD, reporting_template=ReportingTemplate.SANAYI),
        "TCELL": TickerConfig(ticker="TCELL", sector=SectorType.TELEKOM, archetype=CompanyArchetype.SUBSCRIPTION, reporting_template=ReportingTemplate.SANAYI),
        "AKGRT": TickerConfig(ticker="AKGRT", sector=SectorType.SIGORTA, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.SIGORTA),
        "AKCNS": TickerConfig(ticker="AKCNS", sector=SectorType.CIMENTO, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
    }

    @classmethod
    def get_ticker_config(cls, ticker: str) -> TickerConfig:
        """Kullanıcının girdiği hisseyi bulur, yoksa sistemi patlatır."""
        config = cls._registry.get(ticker)
        if not config:
            raise ValueError(f"Sistem Hatası: {ticker} BİST Haritasında (Registry) kayıtlı değil.")
        return config