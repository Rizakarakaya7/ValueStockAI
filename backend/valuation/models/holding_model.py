import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class HoldingModel(BaseValuationModel):
    """
    HOLDİNG ŞİRKETLERİ MODELLİ (Örn: KCHOL, SAHOL, AEFES)
    Konsolide Özkaynak Kârlılığı (ROE) ve Net Aktif Değer (NAV) yaklaşımı.
    Holdingler iştiraklerinin toplamıdır, bu nedenle konsolide bilanço büyüklüğü esastır.
    """

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI # BIST'te holdingler sanayi şablonuyla raporlar
        macro_context = metadata.get("macro_context", {})
        
        logger.info(f"[{ticker}] Holding Konsolide NAV/ROE Motoru çalıştırılıyor.")
        
        # 1. BİLANÇODAN GİRDİLERİN ÇEKİLMESİ
        
        # Özkaynak Çekimi (Önce Ana Ortaklık aranır, yoksa Toplam Özkaynak kullanılır)
        try:
            equity_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.PARENT_EQUITY) if k in df.index]
            if not equity_keys:
                equity_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY) if k in df.index]
        except AttributeError:
            equity_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY) if k in df.index]

        # Net Kâr Çekimi (Önce Ana Ortaklık payı aranır, yoksa Toplam Kâr kullanılır)
        try:
            net_income_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME_PARENT) if k in df.index]
            if not net_income_keys:
                net_income_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME) if k in df.index]
        except AttributeError:
            net_income_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME) if k in df.index]
        
        if not equity_keys or not net_income_keys:
            logger.error(f"[{ticker}] Holding değerlemesi için Özkaynak veya Net Kâr kalemi bulunamadı.")
            return 0.0, {"warning": "Missing Core Data"}
            
        current_equity_cents = float(df.loc[equity_keys, df.columns[-1]].sum(skipna=True))
        ttm_net_income_cents = float(df.loc[net_income_keys, df.columns[-4:]].sum().sum())
        
        if current_equity_cents <= 0:
            return 0.0, {"warning": "Negative Equity (Eksi Özkaynak)"}

        # 2. ROE VE SERMAYE MALİYETİ
        current_roe = ttm_net_income_cents / current_equity_cents
        normalized_roe = min(current_roe, 0.40) # Enflasyon kaynaklı uçuk kârları %40'a törpülüyoruz
        
        risk_free_rate = macro_context.get("risk_free_rate", 0.35) 
        erp = macro_context.get("equity_risk_premium", 0.08)
        beta = macro_context.get("sector_beta", 1.10) # Holdingler piyasanın kendisidir, Beta ~1 civarıdır
        
        cost_of_equity = risk_free_rate + (beta * erp)
        
        # 3. JUSTIFIED P/B (HEDEF ÇARPAN) HESAPLAMASI
        growth = macro_context.get("long_term_growth_rate", 0.04)
        
        if cost_of_equity <= growth:
            justified_pb = 1.0
        else:
            justified_pb = (normalized_roe - growth) / (cost_of_equity - growth)
            
        # P/B Sınırlandırması: Holdingler genelde 0.50x ile 1.50x çarpan arasına sıkışır
        target_pb = max(0.30, min(1.20, justified_pb))

        # 4. KONSOLİDE BAZ DEĞER (İskonto öncesi)
        target_equity_value_cents = current_equity_cents * target_pb
        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Holding_Consolidated_NAV",
            "current_book_value_tl": current_equity_cents / 100,
            "trailing_roe": current_roe,
            "normalized_roe": normalized_roe,
            "cost_of_equity_coe": cost_of_equity,
            "target_pb_multiple": target_pb
        }

        return target_equity_value_tl, model_report