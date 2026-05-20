import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class PerakendeModel(BaseValuationModel):
    """
    PERAKENDE / FMCG (GIDA PERAKENDESİ) MODELLİ
    Düşük Kâr Marjı, Yüksek Hacim ve Negatif İşletme Sermayesi dinamikleri.
    Yüksek nakit dönüşüm oranlı (Cash Conversion) DCF modeli uygulanır.
    """

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        macro_context = metadata.get("macro_context", {})
        
        logger.info(f"[{ticker}] Perakende Yüksek Nakit Dönüşüm (FCFF) Motoru çalıştırılıyor.")
        
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

        # 2. DÜŞÜK MARJ VE YÜKSEK NAKİT DÖNÜŞÜMÜ (Cash Conversion)
        current_ebit_margin = ttm_ebit_cents / ttm_revenue_cents
        
        # Perakendede normalize edilmiş marj genelde tarihsel marjın kendisine yakındır
        # (Çelik gibi aşırı dalgalanmaz, çok stabildir).
        tax_rate = 0.22
        nopat = ttm_ebit_cents * (1 - tax_rate)

        # Perakende Negatif İşletme Sermayesi ile çalışır.
        # NOPAT'ın büyük kısmı Serbest Nakit Akışına (FCFF) dönüşür çünkü işletme sermayesi ihtiyacı yoktur (hatta nakit yaratır).
        # Reinvestment Rate (Yeniden Yatırım Oranı) sadece yeni mağaza açılışları içindir (Görece düşüktür ~%25-30).
        reinvestment_rate = 0.25 
        fcff = nopat * (1 - reinvestment_rate)

        # 3. AĞIRLIKLI ORTALAMA SERMAYE MALİYETİ (WACC) HESAPLAMASI
        risk_free_rate = macro_context.get("risk_free_rate", 0.35) 
        erp = macro_context.get("equity_risk_premium", 0.08)
        
        # Perakende defansiftir. İnsanlar krizde de yemek yemek zorundadır. Beta düşüktür (Örn: 0.85).
        beta = macro_context.get("sector_beta", 0.85) 
        
        cost_of_equity = risk_free_rate + (beta * erp)
        after_tax_cod = (risk_free_rate + 0.02) * (1 - tax_rate) 
        
        # Sermaye Yapısı: Çoğunluğu IFRS-16 kira yükümlülüklerinden oluşan borç (%40) ve Özkaynak (%60)
        w_debt, w_equity = 0.40, 0.60
        wacc = (w_equity * cost_of_equity) + (w_debt * after_tax_cod)

        # 4. BÜYÜME (Growth) ve FİRMA DEĞERİ (Enterprise Value)
        # Perakendeciler enflasyon kadar doğal olarak büyür + nüfus artışı
        terminal_growth = macro_context.get("long_term_growth_rate", 0.04)
        
        if wacc - terminal_growth < 0.05:
            wacc = terminal_growth + 0.05

        enterprise_value_cents = (fcff * (1 + terminal_growth)) / (wacc - terminal_growth)

        # 5. NET BORÇ DÜŞÜMÜ (Özkaynak Değerine Ulaşma)
        net_debt_cents = metadata.get("net_debt_cents", 0.0) 
        equity_value_cents = enterprise_value_cents - net_debt_cents
        
        if equity_value_cents < 0:
            equity_value_cents = 0.0

        target_equity_value_tl = equity_value_cents / 100.0

        model_report = {
            "model_used": "Retail_Defensive_DCF",
            "ttm_revenue_tl": ttm_revenue_cents / 100,
            "current_ebit_margin": current_ebit_margin,
            "cash_conversion_proxy_reinvestment": reinvestment_rate,
            "estimated_fcff_tl": fcff / 100,
            "wacc_applied": wacc,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "net_debt_deducted_tl": net_debt_cents / 100
        }

        return target_equity_value_tl, model_report