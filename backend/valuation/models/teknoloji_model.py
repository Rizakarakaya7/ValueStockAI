import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class TeknolojiModel(BaseValuationModel):
    """
    TEKNOLOJİ VE YAZILIM MODELLİ (Hiper Büyüme)
    İki Aşamalı (Two-Stage) İndirgenmiş Nakit Akışı Modeli.
    Yüksek marjlar, düşük sermaye harcaması (Asset-Light) ve agresif büyüme varsayımları içerir.
    """

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        macro_context = metadata.get("macro_context", {})
        
        logger.info(f"[{ticker}] Teknoloji/Yazılım İki Aşamalı (Two-Stage) Büyüme Motoru çalıştırılıyor.")
        
        # --- TRUVA ATI: DEFTER DEĞERİ ZEMİNİNİ İPTAL ETME ---
        # Yazılım şirketleri P/B 10x-20x ile işlem görür. 1.0x P/B zemini bu sektörde mantıksızdır ve sistemi bozar.
        if "valuation_safeguards" in metadata and "book_value_floor_cents" in metadata["valuation_safeguards"]:
            metadata["valuation_safeguards"]["book_value_floor_cents"] = 0
            logger.info(f"[{ticker}] Hyper-Growth İstisnası: Teknoloji şirketlerinde Defter Değeri Zemini (Floor) tamamen iptal edildi.")
        # ---------------------------------------------------

        # 1. GİRDİLER (Ciro ve Kâr)
        rev_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.REVENUE) if k in df.index]
        ebit_keys = [k for k in get_taxonomy_keys(reporting_group, FinancialConcept.EBIT) if k in df.index]
        
        if not rev_keys or not ebit_keys:
            return 0.0, {"warning": "Missing Core Data"}
            
        ttm_revenue_cents = float(df.loc[rev_keys, df.columns[-4:]].sum().sum())
        ttm_ebit_cents = float(df.loc[ebit_keys, df.columns[-4:]].sum().sum())
        
        if ttm_revenue_cents <= 0 or ttm_ebit_cents <= 0:
            return 0.0, {"warning": "Negatif kâr ile DCF çalıştırılamaz (Zarar eden Tech şirketi)."}

        current_margin = ttm_ebit_cents / ttm_revenue_cents
        
        # Teknoloji şirketleri ölçeklendikçe marjları devasa seviyelere (SaaS için >%25) ulaşır.
        target_margin = max(current_margin, 0.25)
        tax_rate = 0.22

        # 2. SERMAYE MALİYETİ (WACC)
        # Teknoloji hisseleri çok daha volatildir, Beta yüksektir (Örn: 1.40)
        risk_free_rate = macro_context.get("risk_free_rate", 0.35) 
        erp = macro_context.get("equity_risk_premium", 0.08)
        beta = macro_context.get("sector_beta", 1.40) 
        
        wacc = risk_free_rate + (beta * erp) # Teknolojide borç (Debt) varsayılmaz, hepsi Özkaynaktır.

        # 3. İKİ AŞAMALI BÜYÜME (Two-Stage Growth)
        high_growth_rate = 0.30  # İlk 5 yıl boyunca her yıl %30 devasa büyüme
        high_growth_years = 5
        reinvestment_rate = 0.15 # Yazılımın AR-GE'si vardır ama ağır sanayi kadar CAPEX gerektirmez.

        pv_of_fcff = 0.0
        projected_rev = ttm_revenue_cents

        # Aşama 1: Hiper Büyüme Dönemi
        for year in range(1, high_growth_years + 1):
            projected_rev *= (1 + high_growth_rate)
            nopat = projected_rev * target_margin * (1 - tax_rate)
            fcff = nopat * (1 - reinvestment_rate)
            pv_of_fcff += fcff / ((1 + wacc) ** year)

        # Aşama 2: Terminal Değer (Sonsuzluk)
        terminal_growth = macro_context.get("long_term_growth_rate", 0.04)
        if wacc - terminal_growth < 0.05:
            wacc = terminal_growth + 0.05

        terminal_rev = projected_rev * (1 + terminal_growth)
        terminal_nopat = terminal_rev * target_margin * (1 - tax_rate)
        terminal_fcff = terminal_nopat * (1 - reinvestment_rate)

        terminal_value = terminal_fcff / (wacc - terminal_growth)
        pv_of_terminal_value = terminal_value / ((1 + wacc) ** high_growth_years)

        enterprise_value_cents = pv_of_fcff + pv_of_terminal_value

        # 4. NET BORÇ DÜŞÜMÜ (Teknolojide genelde kasada nakit vardır, bu değere eklenir)
        net_debt_cents = metadata.get("net_debt_cents", 0.0) 
        equity_value_cents = enterprise_value_cents - net_debt_cents
        
        if equity_value_cents < 0:
            equity_value_cents = 0.0

        target_equity_value_tl = equity_value_cents / 100.0

        model_report = {
            "model_used": "Tech_TwoStage_HyperGrowth",
            "current_ebit_margin": current_margin,
            "target_scale_margin": target_margin,
            "applied_high_growth_rate": high_growth_rate,
            "wacc_applied": wacc,
            "pv_of_high_growth_stage_tl": pv_of_fcff / 100,
            "pv_of_terminal_value_tl": pv_of_terminal_value / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
            "net_debt_deducted_tl": net_debt_cents / 100
        }

        return target_equity_value_tl, model_report