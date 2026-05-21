import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class OtomotivModel(BaseValuationModel):
    """
    OTOMOTİV SEKTÖRÜ MODELLİ (Kapasite ve İhracat Odaklı)
    Yüksek sermaye harcaması (CAPEX) ve Ar-Ge gerektiren, ihracat garantili DCF modeli.
    """

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        macro_context = metadata.get("macro_context", {})
        
        logger.info(f"[{ticker}] Otomotiv DCF Motoru (Kapasite/İhracat Odaklı) çalıştırılıyor.")
        
        # 1. BİLANÇODAN GİRDİLERİN ÇEKİLMESİ
        rev_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.REVENUE) if k in df.index]
        ebit_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.EBIT) if k in df.index]
        
        if not rev_keys or not ebit_keys:
            logger.error(f"[{ticker}] Değerleme için Ciro veya EBIT kalemi bulunamadı.")
            return 0.0, {"warning": "Missing Core Data"}
            
        ttm_revenue_cents = float(df.loc[rev_keys, df.columns[-4:]].sum().sum())
        ttm_ebit_cents = float(df.loc[ebit_keys, df.columns[-4:]].sum().sum())
        
        if ttm_revenue_cents <= 0 or ttm_ebit_cents <= 0:
            return 0.0, {"warning": "Zero or Negative Revenue/EBIT"}

        current_margin = ttm_ebit_cents / ttm_revenue_cents
        tax_rate = 0.22
        nopat = ttm_ebit_cents * (1 - tax_rate)

        # 2. YÜKSEK YATIRIM (CAPEX) İHTİYACI
        # Otomotiv sektörü yeni model platformları ve Elektrikli Araç (EV) hatları için 
        # kârının devasa bir kısmını fabrikaya gömmek zorundadır.
        reinvestment_rate = 0.50 # NOPAT'ın yarısı serbest nakde dönüşemez, yatırıma gider.
        fcff = nopat * (1 - reinvestment_rate)

        # 3. AĞIRLIKLI ORTALAMA SERMAYE MALİYETİ (WACC) HESAPLAMASI
        risk_free_rate = macro_context.get("risk_free_rate", 0.35) 
        erp = macro_context.get("equity_risk_premium", 0.08)
        
        # Otomotiv hisseleri, ağır sanayiye kıyasla ihracat koruması nedeniyle biraz daha defansiftir.
        beta = macro_context.get("sector_beta", 1.15) 
        
        cost_of_equity = risk_free_rate + (beta * erp)
        after_tax_cod = (risk_free_rate + 0.04) * (1 - tax_rate) 
        
        # Sermaye Yapısı: Fabrika ve bant yatırımları için %40 Borç, %60 Özkaynak varsayımı
        w_debt, w_equity = 0.40, 0.60
        wacc = (w_equity * cost_of_equity) + (w_debt * after_tax_cod)

        # 4. GORDON BÜYÜME MODELİ & FİRMA DEĞERİ
        # İhracat ve Euro enflasyonu nedeniyle stabil büyüme
        terminal_growth = macro_context.get("long_term_growth_rate", 0.03)
        
        if wacc - terminal_growth < 0.05:
            wacc = terminal_growth + 0.05

        enterprise_value_cents = (fcff * (1 + terminal_growth)) / (wacc - terminal_growth)

        # 5. NET BORÇ DÜŞÜMÜ
        net_debt_cents = metadata.get("net_debt_cents", 0.0) 
        equity_value_cents = enterprise_value_cents - net_debt_cents
        
        if equity_value_cents < 0:
            equity_value_cents = 0.0

        target_equity_value_tl = equity_value_cents / 100.0

        model_report = {
            "model_used": "Automotive_Capacity_DCF",
            "current_ebit_margin": current_margin,
            "reinvestment_rate": reinvestment_rate,
            "wacc_applied": wacc,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "net_debt_deducted_tl": net_debt_cents / 100
        }

        return target_equity_value_tl, model_report