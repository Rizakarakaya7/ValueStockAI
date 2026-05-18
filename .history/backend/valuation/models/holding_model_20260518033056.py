import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode
import logging

logger = logging.getLogger(__name__)

class HoldingModel(BaseValuationModel):
    """
    HOLDING VE YATIRIM ŞİRKETLERİ İZOLE MODELLİ (Örn: KCHOL, SAHOL)
    Parçaların Toplamı (Sum of the Parts - SOTP) ve Net Aktif Değer (NAV) tabanlıdır.
    Klasik DCF işlemez çünkü gelirler temettü ve iştirak değer artışından gelir.
    """
    
    # BİST Tarihsel Ortalama Holding İskontosu (Genelde %25-35 arasıdır)
    HISTORICAL_HOLDING_DISCOUNT = 0.30 

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.REAL_SECTOR
        
        logger.info(f"[{ticker}] Holding SOTP / NAV İskonto Modeli çalıştırılıyor.")
        
        # Gerçek bir kurumsal yapıda Holding'in "Net Aktif Değeri" (NAV), borsaya açık olan 
        # iştiraklerinin (TUPRS, FROTO) piyasa değerleri çekilerek anlık hesaplanır. 
        # Bu basitleştirilmiş yapıda, Konsolide Özkaynakları bir NAV proxy'si olarak alıyoruz.
        
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        
        # DÜZELTME: Sadece bilançoda gerçekten var olan anahtarları filtrele!
        existing_equity_keys = [k for k in equity_keys if k in df.index]
        
        if not existing_equity_keys:
            logger.error(f"[{ticker}] Holding değerlemesi için gerekli Özkaynak verisi bilançoda bulunamadı.")
            return 0.0, {"warning": "Missing Equity Data in DataFrame for Holding"}
            
        # Güvenli filtrelenmiş anahtarlarla son çeyrek snapshot değerini çek
        nav_proxy_cents = float(df.loc[existing_equity_keys, df.columns[-1]].sum(skipna=True))
        
        # İştiraklerin iştiraki olma durumu, yönetim hantallığı ve holdingin kendi idari 
        # giderleri nedeniyle piyasa bu değere peşinen iskonto uygular.
        discounted_equity_value_cents = nav_proxy_cents * (1 - self.HISTORICAL_HOLDING_DISCOUNT)
        
        target_equity_value_tl = discounted_equity_value_cents / 100.0

        model_report = {
            "model_used": "Holding_NAV_Discount",
            "proxy_nav_tl": nav_proxy_cents / 100,
            "applied_holding_discount": self.HISTORICAL_HOLDING_DISCOUNT,
            "discount_impact_tl": (nav_proxy_cents - discounted_equity_value_cents) / 100
        }

        return target_equity_value_tl, model_report