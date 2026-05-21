import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class SavunmaModel(BaseValuationModel):
    """
    SAVUNMA SANAYİ SEKTÖRÜ İZOLE MODELLİ (Örn: ASELS, OTKAR)
    Devlet sözleşmelerine dayalı garantili sipariş defteri (Backlog) ve uzun tahsilat 
    süreçleri için 'Debt Cap' ve 'Doğrusal Kâr Düzeltmesi' içeren BIST-Uyumlu DCF arketipi.
    """
    
    SECTOR_BETA = 0.80               
    PROJECTION_YEARS = 7               

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] Savunma Sanayi Backlog-Driven DCF Modeli çalıştırılıyor.")
        
        # 1. MAKRO FAİZ VE İSKONTO (WACC) HESABI
        risk_free_rate = metadata.get("macro_context", {}).get("tr_risk_free_rate", 0.35)  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. TTM EBITDA HESABI
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_cents = ttm_ebit + ttm_da

        # 3. MİD-CYCLE NAKİT AKIŞI NORMALİZASYONU
        # Yüksek kârlılığa rağmen tahsilat/işletme sermayesi FCF'i eksiye itebilir.
        # Savunma devleri için döngü ortası (Mid-Cycle) nakit yaratma gücü %30 bandındadır.
        is_normalized_used = False
        if 'CALC_OWNERS_EARNINGS_TTM' in df.index and float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1]) > 0:
            base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        else:
            base_fcf_cents = ttm_ebitda_cents * 0.30
            is_normalized_used = True

        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif EBITDA."}

        # 4. YÜKSEK WACC'A KARŞI DÖVİZ (FX)/ENFLASYON DUYARLI BÜYÜME PATİKASI
        # %41.4 WACC ile iskonto edilen projelerde ilk yılların büyümesi kur geçişkenliğini yansıtmalıdır.
        terminal_growth_rate = risk_free_rate * 0.20 
        
        growth_path = [
            risk_free_rate * 1.50,  # 1. Yıl: Kur geçişkenliği ve döviz bazlı sipariş faturaya dönüyor (Örn: %52)
            risk_free_rate * 1.20,  # 2. Yıl
            risk_free_rate * 0.90,  # 3. Yıl
            risk_free_rate * 0.70,  # 4. Yıl
            risk_free_rate * 0.50,  # 5. Yıl
            risk_free_rate * 0.35,  # 6. Yıl
            terminal_growth_rate    # 7. Yıl
        ] 
        
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 5. UÇ DEĞER (Terminal Value) HESAPLAMASI
        if discount_rate <= terminal_growth_rate:
            discount_rate = terminal_growth_rate + 0.05
            
        terminal_value = (projected_cash_flows[-1] * (1 + terminal_growth_rate)) / (discount_rate - terminal_growth_rate)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 6. DEBT CAP (BORÇ TAVANI) UYGULAMASI
        # Yatırım ve uzun tahsilat süreçleri kaynaklı banka borçlarının değerlemeyi orantısız 
        # ezmemesi için bir üst sınır (EV'nin maks %15'i) uygulanır.
        raw_net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        max_allowed_debt = enterprise_value_cents * 0.15 
        applied_net_debt_cents = min(max(0, raw_net_debt_cents), max_allowed_debt)
        
        target_equity_value_cents = enterprise_value_cents - applied_net_debt_cents
        base_equity_value_tl = max(0.0, target_equity_value_cents / 100.0)

        # 7. BACKLOG (SİPARİŞ DEFTERİ) İÇİN DOĞRUSAL DÜZELTME
        # Garanti edilmiş siparişlerden elde edilecek kesin kârlar için şirket 
        # toplam değerine doğrudan doğrusal bir prim (Linear Adjustment) eklenir.
        # Savunma sektöründe bu genellikle 3 yıllık mevcut FAVÖK hacmine eşdeğer bir güvenli limandır.
        backlog_guaranteed_profit_tl = (ttm_ebitda_cents / 100.0) * 3.0
        final_total_equity_tl = base_equity_value_tl + backlog_guaranteed_profit_tl

        model_report = {
            "model_used": "Savunma_Backlog_DCF_Optimized",
            "is_fcf_normalized": is_normalized_used,
            "applied_wacc": discount_rate,
            "debt_cap_applied": raw_net_debt_cents > max_allowed_debt,
            "linear_backlog_adjustment_tl": backlog_guaranteed_profit_tl,
            "pv_of_7_year_fcf_tl": present_value_of_fcf / 100.0,
            "enterprise_value_tl": enterprise_value_cents / 100.0,
            "net_debt_deducted_tl": applied_net_debt_cents / 100.0,
            "final_total_equity_tl": final_total_equity_tl
        }

        # Bulunan rasyonel ve primli toplam değer (final_total_equity_tl), orchestrator
        # katmanında Zemin korumasından geçtikten sonra hisse adedine (Shares Outstanding) bölünecektir.
        return final_total_equity_tl, model_report