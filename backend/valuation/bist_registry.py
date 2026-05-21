import logging
from enum import Enum
from typing import Dict
from pydantic import BaseModel, Field

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
    GYO = "GYO"              
    ICECEK = "Icecek"        

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
    NAV_BASED = "Nav_Based"               
    CONSUMER_STAPLES = "Consumer_Staples" 
    OPERATIONAL_HOLDING = "Operational_Holding" 

class ReportingTemplate(Enum):
    SANAYI = "XI_29"
    REAL_SECTOR = "XI_29"
    BANKA = "XI_59"
    BANKING = "XI_59"
    SIGORTA = "XI_29_Sigorta" 

FinancialGroupCode = ReportingTemplate

# ==========================================
# 2. ŞİRKET KÜNYESİ (Data Model)
# ==========================================
class TickerConfig(BaseModel):
    ticker: str
    sector: SectorType
    archetype: CompanyArchetype
    reporting_template: ReportingTemplate
    currency: CurrencyType = CurrencyType.TRY 
    child_stakes: Dict[str, float] = Field(default_factory=dict)

# ==========================================
# 3. KAYIT SERVİSİ (Registry Service)
# ==========================================
class BistRegistryService:
    """
    Sisteme gelen hissenin hangi sektörde olduğunu ve hangi şablonla 
    verisinin çekileceğini belirleyen statik harita (BIST100 Genişletilmiş).
    """
    
    _registry: Dict[str, TickerConfig] = {
        
        # --- OPERASYONEL HOLDİNGLER (SOTP MOTORU İLE ÇALIŞANLAR) ---
        "AEFES": TickerConfig(
            ticker="AEFES", sector=SectorType.HOLDING, archetype=CompanyArchetype.OPERATIONAL_HOLDING, reporting_template=ReportingTemplate.SANAYI,
            child_stakes={"CCOLA": 0.5026}
        ),
        "KCHOL": TickerConfig(
            ticker="KCHOL", sector=SectorType.HOLDING, archetype=CompanyArchetype.OPERATIONAL_HOLDING, reporting_template=ReportingTemplate.SANAYI,
            # Koç Holding'in halka açık dev iştirakleri ve yaklaşık sahiplik oranları
            child_stakes={"FROTO": 0.388, "TOASO": 0.375, "TUPRS": 0.464, "YKBNK": 0.409}
        ),
        "SAHOL": TickerConfig(
            ticker="SAHOL", sector=SectorType.HOLDING, archetype=CompanyArchetype.OPERATIONAL_HOLDING, reporting_template=ReportingTemplate.SANAYI,
            # Sabancı Holding'in halka açık dev iştirakleri ve yaklaşık sahiplik oranları
            child_stakes={"AKBNK": 0.407, "ENJSA": 0.400, "AKCNS": 0.397, "CIMSA": 0.545}
        ),
        "DOHOL": TickerConfig(
            ticker="DOHOL", sector=SectorType.HOLDING, archetype=CompanyArchetype.OPERATIONAL_HOLDING, reporting_template=ReportingTemplate.SANAYI,
            child_stakes={"GWIND": 0.300, "DOAS": 0.05} # Sadece halka açık ana paylar
        ),

        # --- STANDART HOLDİNGLER ---
        "ENKAI": TickerConfig(ticker="ENKAI", sector=SectorType.HOLDING, archetype=CompanyArchetype.HOLDING_CO, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        "TKFEN": TickerConfig(ticker="TKFEN", sector=SectorType.HOLDING, archetype=CompanyArchetype.HOLDING_CO, reporting_template=ReportingTemplate.SANAYI),
        "AGHOL": TickerConfig(ticker="AGHOL", sector=SectorType.HOLDING, archetype=CompanyArchetype.HOLDING_CO, reporting_template=ReportingTemplate.SANAYI),
        
        # --- BANKACILIK ---
        "AKBNK": TickerConfig(ticker="AKBNK", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "ISCTR": TickerConfig(ticker="ISCTR", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "YKBNK": TickerConfig(ticker="YKBNK", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "GARAN": TickerConfig(ticker="GARAN", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "HALKB": TickerConfig(ticker="HALKB", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "VAKBN": TickerConfig(ticker="VAKBN", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),
        "ALBRK": TickerConfig(ticker="ALBRK", sector=SectorType.BANKACILIK, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.BANKA),

        # --- OTOMOTİV ---
        "FROTO": TickerConfig(ticker="FROTO", sector=SectorType.OTOMOTIV, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),
        "TOASO": TickerConfig(ticker="TOASO", sector=SectorType.OTOMOTIV, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "DOAS": TickerConfig(ticker="DOAS", sector=SectorType.OTOMOTIV, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "TTRAK": TickerConfig(ticker="TTRAK", sector=SectorType.OTOMOTIV, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),

        # --- HAVACILIK ---
        "THYAO": TickerConfig(ticker="THYAO", sector=SectorType.HAVACILIK, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        "PGSUS": TickerConfig(ticker="PGSUS", sector=SectorType.HAVACILIK, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.EUR),
        "TAVHL": TickerConfig(ticker="TAVHL", sector=SectorType.HAVACILIK, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.EUR),

        # --- PERAKENDE & TİCARET ---
        "BIMAS": TickerConfig(ticker="BIMAS", sector=SectorType.PERAKENDE, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),
        "MGROS": TickerConfig(ticker="MGROS", sector=SectorType.PERAKENDE, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),
        "SOKM": TickerConfig(ticker="SOKM", sector=SectorType.PERAKENDE, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),
        "TKNSA": TickerConfig(ticker="TKNSA", sector=SectorType.PERAKENDE, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),

        # --- DEMİR ÇELİK ---
        "EREGL": TickerConfig(ticker="EREGL", sector=SectorType.DEMIR_CELIK, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        "ISDMR": TickerConfig(ticker="ISDMR", sector=SectorType.DEMIR_CELIK, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        "KRDMD": TickerConfig(ticker="KRDMD", sector=SectorType.DEMIR_CELIK, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),

        # --- PETROKİMYA & KİMYA ---
        "TUPRS": TickerConfig(ticker="TUPRS", sector=SectorType.PETROKIMYA, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "PETKM": TickerConfig(ticker="PETKM", sector=SectorType.PETROKIMYA, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI, currency=CurrencyType.USD),
        "SASA": TickerConfig(ticker="SASA", sector=SectorType.PETROKIMYA, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "AKSA": TickerConfig(ticker="AKSA", sector=SectorType.PETROKIMYA, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),

        # --- İÇECEK & GIDA ---
        "CCOLA": TickerConfig(ticker="CCOLA", sector=SectorType.ICECEK, archetype=CompanyArchetype.CONSUMER_STAPLES, reporting_template=ReportingTemplate.SANAYI),
        "ULKER": TickerConfig(ticker="ULKER", sector=SectorType.ICECEK, archetype=CompanyArchetype.CONSUMER_STAPLES, reporting_template=ReportingTemplate.SANAYI),
        "TATGD": TickerConfig(ticker="TATGD", sector=SectorType.ICECEK, archetype=CompanyArchetype.CONSUMER_STAPLES, reporting_template=ReportingTemplate.SANAYI),
        "TUKAS": TickerConfig(ticker="TUKAS", sector=SectorType.ICECEK, archetype=CompanyArchetype.CONSUMER_STAPLES, reporting_template=ReportingTemplate.SANAYI),

        # --- TELEKOMÜNİKASYON ---
        "TCELL": TickerConfig(ticker="TCELL", sector=SectorType.TELEKOM, archetype=CompanyArchetype.SUBSCRIPTION, reporting_template=ReportingTemplate.SANAYI),
        "TTKOM": TickerConfig(ticker="TTKOM", sector=SectorType.TELEKOM, archetype=CompanyArchetype.SUBSCRIPTION, reporting_template=ReportingTemplate.SANAYI),

        # --- ENERJİ ---
        "ENJSA": TickerConfig(ticker="ENJSA", sector=SectorType.ENERJI, archetype=CompanyArchetype.REGULATED_YIELD, reporting_template=ReportingTemplate.SANAYI),
        "ASTOR": TickerConfig(ticker="ASTOR", sector=SectorType.ENERJI, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "GESAN": TickerConfig(ticker="GESAN", sector=SectorType.ENERJI, archetype=CompanyArchetype.HYPER_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "ALFAS": TickerConfig(ticker="ALFAS", sector=SectorType.ENERJI, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "GWIND": TickerConfig(ticker="GWIND", sector=SectorType.ENERJI, archetype=CompanyArchetype.REGULATED_YIELD, reporting_template=ReportingTemplate.SANAYI),
        "ZOREN": TickerConfig(ticker="ZOREN", sector=SectorType.ENERJI, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "AKSEN": TickerConfig(ticker="AKSEN", sector=SectorType.ENERJI, archetype=CompanyArchetype.CAPACITY_GROWTH, reporting_template=ReportingTemplate.SANAYI),

        # --- SAVUNMA & TEKNOLOJİ ---
        "ASELS": TickerConfig(ticker="ASELS", sector=SectorType.SAVUNMA, archetype=CompanyArchetype.BACKLOG_DRIVEN, reporting_template=ReportingTemplate.SANAYI),
        "OTKAR": TickerConfig(ticker="OTKAR", sector=SectorType.SAVUNMA, archetype=CompanyArchetype.BACKLOG_DRIVEN, reporting_template=ReportingTemplate.SANAYI),
        "MIATK": TickerConfig(ticker="MIATK", sector=SectorType.TEKNOLOJI, archetype=CompanyArchetype.HYPER_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "KONTK": TickerConfig(ticker="KONTK", sector=SectorType.TEKNOLOJI, archetype=CompanyArchetype.HYPER_GROWTH, reporting_template=ReportingTemplate.SANAYI),
        "LOGO": TickerConfig(ticker="LOGO", sector=SectorType.TEKNOLOJI, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI),

        # --- MADENCİLİK ---
        "KOZAL": TickerConfig(ticker="KOZAL", sector=SectorType.MADENCILIK, archetype=CompanyArchetype.DEPLETING_ASSET, reporting_template=ReportingTemplate.SANAYI),
        "KOZAA": TickerConfig(ticker="KOZAA", sector=SectorType.MADENCILIK, archetype=CompanyArchetype.DEPLETING_ASSET, reporting_template=ReportingTemplate.SANAYI),
        "IPEKE": TickerConfig(ticker="IPEKE", sector=SectorType.MADENCILIK, archetype=CompanyArchetype.DEPLETING_ASSET, reporting_template=ReportingTemplate.SANAYI),
        "SARKY": TickerConfig(ticker="SARKY", sector=SectorType.MADENCILIK, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),

        # --- ÇİMENTO & CAM ---
        "AKCNS": TickerConfig(ticker="AKCNS", sector=SectorType.CIMENTO, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "CIMSA": TickerConfig(ticker="CIMSA", sector=SectorType.CIMENTO, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "OYAKC": TickerConfig(ticker="OYAKC", sector=SectorType.CIMENTO, archetype=CompanyArchetype.CYCLICAL, reporting_template=ReportingTemplate.SANAYI),
        "SISE": TickerConfig(ticker="SISE", sector=SectorType.CIMENTO, archetype=CompanyArchetype.COMPOUNDER, reporting_template=ReportingTemplate.SANAYI), # Cam/Kimya kompleksi

        # --- SİGORTA ---
        "AKGRT": TickerConfig(ticker="AKGRT", sector=SectorType.SIGORTA, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.SIGORTA),
        "ANSGR": TickerConfig(ticker="ANSGR", sector=SectorType.SIGORTA, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.SIGORTA),
        "TURSG": TickerConfig(ticker="TURSG", sector=SectorType.SIGORTA, archetype=CompanyArchetype.FINANCIAL, reporting_template=ReportingTemplate.SIGORTA),

        # --- GYO (GAYRİMENKUL) ---
        "EKGYO": TickerConfig(ticker="EKGYO", sector=SectorType.GYO, archetype=CompanyArchetype.NAV_BASED, reporting_template=ReportingTemplate.SANAYI),
        "ISGYO": TickerConfig(ticker="ISGYO", sector=SectorType.GYO, archetype=CompanyArchetype.NAV_BASED, reporting_template=ReportingTemplate.SANAYI),
        "TRGYO": TickerConfig(ticker="TRGYO", sector=SectorType.GYO, archetype=CompanyArchetype.NAV_BASED, reporting_template=ReportingTemplate.SANAYI),
        "ZRGYO": TickerConfig(ticker="ZRGYO", sector=SectorType.GYO, archetype=CompanyArchetype.NAV_BASED, reporting_template=ReportingTemplate.SANAYI),
    }  

    @classmethod
    def get_ticker_config(cls, ticker: str) -> TickerConfig:
        config = cls._registry.get(ticker)
        if not config:
            raise ValueError(f"Sistem Hatası: {ticker} BİST Haritasında (Registry) kayıtlı değil.")
        return config