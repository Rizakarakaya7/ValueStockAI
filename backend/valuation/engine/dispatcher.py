import logging
from typing import Dict, Type, Any

# Sistemin ana Enum'u (Bu Enum'un bist_registry.py içinde tanımlı olduğu varsayılır)
from valuation.bist_registry import SectorType

# 1. TÜM MODELLERİN İÇERİ AKTARILMASI (Models)
from valuation.models.base_model import BaseValuationModel
from valuation.models.demir_celik_model import DemirCelikModel
from valuation.models.otomotiv_model import OtomotivModel
from valuation.models.perakende_model import PerakendeModel
from valuation.models.havacilik_model import HavacilikModel
from valuation.models.telekom_model import TelekomModel
from valuation.models.cimento_model import CimentoModel
from valuation.models.sigorta_model import SigortaModel
from valuation.models.teknoloji_model import TeknolojiModel
from valuation.models.savunma_model import SavunmaModel
from valuation.models.enerji_model import EnerjiModel
from valuation.models.madencilik_model import MadencilikModel
from valuation.models.bankacilik_model import BankacilikModel
from valuation.models.holding_model import HoldingModel
from valuation.models.petrokimya_model import PetrokimyaModel

# 2. TÜM KANCALARIN İÇERİ AKTARILMASI (Hooks)
from valuation.hooks.demir_celik_hooks import DemirCelikHook
from valuation.hooks.otomotiv_hooks import OtomotivHook
from valuation.hooks.perakende_hooks import PerakendeHook
from valuation.hooks.havacilik_hooks import HavacilikHook
from valuation.hooks.telekom_hooks import TelekomHook
from valuation.hooks.cimento_hooks import CimentoHook
from valuation.hooks.sigorta_hooks import SigortaHook
from valuation.hooks.teknoloji_hooks import TeknolojiHook
from valuation.hooks.savunma_hooks import SavunmaHook
from valuation.hooks.enerji_hooks import EnerjiHook
from valuation.hooks.madencilik_hooks import MadencilikHook
from valuation.hooks.bankacilik_hooks import BankacilikHook
from valuation.hooks.holding_hooks import HoldingHook
from valuation.hooks.petrokimya_hooks import PetrokimyaHook

logger = logging.getLogger(__name__)

class DispatcherError(Exception):
    """Bilinmeyen bir sektör geldiğinde sistemi durduracak güvenlik istisnası."""
    pass

class ModelDispatcher:
    """
    Orkestratörün talebi üzerine, hissenin sektörüne uygun Matematiksel Modeli (DCF/NAV/RI)
    üreten ve teslim eden Fabrika (Factory) sınıfı.
    """
    
    def __init__(self):
        # Modeller statik (stateless) yapıya yakın olduğu için belleği yormamak adına 
        # sadece bir kez (Singleton mantığıyla) ayağa kaldırılır.
        self._model_registry: Dict[SectorType, BaseValuationModel] = {
            SectorType.DEMIR_CELIK: DemirCelikModel(),
            SectorType.OTOMOTIV: OtomotivModel(),
            SectorType.PERAKENDE: PerakendeModel(),
            SectorType.HAVACILIK: HavacilikModel(),
            SectorType.TELEKOM: TelekomModel(),
            SectorType.CIMENTO: CimentoModel(),
            SectorType.SIGORTA: SigortaModel(),
            SectorType.TEKNOLOJI: TeknolojiModel(),
            SectorType.SAVUNMA: SavunmaModel(),
            SectorType.ENERJI: EnerjiModel(),
            SectorType.MADENCILIK: MadencilikModel(),
            SectorType.BANKACILIK: BankacilikModel(),
            SectorType.HOLDING: HoldingModel(),
            SectorType.PETROKIMYA: PetrokimyaModel(),
        }

    def get_model(self, sector: SectorType) -> BaseValuationModel:
        """İstenilen sektöre ait Değerleme Modelini güvenli şekilde döndürür."""
        model = self._model_registry.get(sector)
        if not model:
            logger.error(f"Kritik Hata: {sector.value} sektörü için kayıtlı bir Matematiksel Model bulunamadı!")
            raise DispatcherError(f"Tanımsız Sektör Modeli: {sector.value}")
        
        logger.debug(f"Dispatcher: {sector.value} için {model.__class__.__name__} tahsis edildi.")
        return model


class HookDispatcher:
    """
    Orkestratörün talebi üzerine, hissenin sektörüne uygun Piyasa Rejimi Kancasını (Hook)
    teslim eden Fabrika sınıfı.
    """
    
    def __init__(self):
        # Hook'ların içindeki fonksiyonlar @staticmethod olduğu için nesne oluşturmaya (instance)
        # gerek yoktur. Doğrudan Sınıfın (Class) kendisi referans olarak tutulur.
        self._hook_registry: Dict[SectorType, Type] = {
            SectorType.DEMIR_CELIK: DemirCelikHook,
            SectorType.OTOMOTIV: OtomotivHook,
            SectorType.PERAKENDE: PerakendeHook,
            SectorType.HAVACILIK: HavacilikHook,
            SectorType.TELEKOM: TelekomHook,
            SectorType.CIMENTO: CimentoHook,
            SectorType.SIGORTA: SigortaHook,
            SectorType.TEKNOLOJI: TeknolojiHook,
            SectorType.SAVUNMA: SavunmaHook,
            SectorType.ENERJI: EnerjiHook,
            SectorType.MADENCILIK: MadencilikHook,
            SectorType.BANKACILIK: BankacilikHook,
            SectorType.HOLDING: HoldingHook,
            SectorType.PETROKIMYA: PetrokimyaHook,
        }

    def get_hook(self, sector: SectorType) -> Type:
        """İstenilen sektöre ait Piyasa Kancasını (Hook Sınıfını) döndürür."""
        hook_class = self._hook_registry.get(sector)
        if not hook_class:
            logger.error(f"Kritik Hata: {sector.value} sektörü için kayıtlı bir Piyasa Kancası (Hook) bulunamadı!")
            raise DispatcherError(f"Tanımsız Sektör Kancası: {sector.value}")
        
        logger.debug(f"Dispatcher: {sector.value} için {hook_class.__name__} tahsis edildi.")
        return hook_class