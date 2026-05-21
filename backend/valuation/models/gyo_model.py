import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class GyoModel(BaseValuationModel):
    """
    GAYRİMENKUL YATIRIM ORTAKLIĞI (GYO) İZOLE MODELLİ (Örn: EKGYO, ISGYO)
    'NAV_BASED' (Net Aktif Değer) arketipi.
    GYO'lar nakit akışı (DCF) ile değil, sahip oldukları gayrimenkullerin 
    Net Aktif Değeri (NAD) üzerinden değerlenir. 
    """
    
    # BIST GYO'ları için tarihsel PD/NAD (Fiyat/Net Aktif Değer) çarpanı ortalama 0.65x bandındadır.
    TARGET_P_NAV_MULTIPLE = 0.65 

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] GYO Net Aktif Değer (NAV) Modeli çalıştırılıyor.")
        
        # 1. NET AKTİF DEĞER (NAV) TESPİTİ
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        valid_equity = [k for k in equity_keys if k in df.index]
        
        if not valid_equity:
            logger.error(f"[{ticker}] GYO değerlemesi için Özkaynak (NAV proxy) verisi bulunamadı.")
            return 0.0, {"warning": "Missing Equity Data"}
            
        # En güncel çeyreğin özkaynak değeri (Cents cinsinden)
        current_nav_cents = float(df.loc[valid_equity[0], df.columns[-1]])
        
        if current_nav_cents <= 0:
            logger.warning(f"[{ticker}] Negatif Özkaynak (NAV). Şirket teknik iflas durumunda olabilir.")
            return 0.0, {"warning": "Negative NAV"}

        current_nav_tl = current_nav_cents / 100.0

        # 2. HEDEF TOPLAM ŞİRKET DEĞERİ (P/NAV İskontosu Uygulanmış)
        target_equity_value_tl = current_nav_tl * self.TARGET_P_NAV_MULTIPLE

        model_report = {
            "model_used": "GYO_NAV_Based",
            "current_nav_tl": current_nav_tl,
            "applied_p_nav_multiple": self.TARGET_P_NAV_MULTIPLE,
            "total_equity_value_target_tl": target_equity_value_tl
        }

        # DÜZELTME: Hisse adedine (Shares Outstanding) bölme işlemini burada yapmıyoruz.
        # Toplam Şirket Değerini gönderiyoruz, orchestrator.py kendisi hisse adedine bölecek.
        return target_equity_value_tl, model_report