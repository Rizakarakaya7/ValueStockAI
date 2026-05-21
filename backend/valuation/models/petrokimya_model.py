import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode
import logging

logger = logging.getLogger(__name__)

class PetrokimyaModel(BaseValuationModel):
    """
    PETROKİMYA SEKTÖRÜ İZOLE MODELLİ (Örn: TUPRS, PETKM)
    Ağır döngüsel (Cyclical), yüksek CapEx gerektiren, Crack Spread (Rafineri Marjı)
    dinamiklerine tabi şirketler için özelleştirilmiş, Mid-Cycle korumalı DCF Modeli.
    """
    
    SECTOR_BETA = 1.15               # Emtia dalgalanmalarından dolayı BIST'e göre hareketlidir.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] Petrokimya İzole DCF Modeli çalıştırılıyor (BIST Optimize).")
        
        # 1. MAKRO FAİZ VE UYUMLU İSKONTO (WACC) HESABI
        risk_free_rate = metadata.get("macro_context", {}).get("tr_risk_free_rate", 0.35)
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. TTM EBITDA HESABI (Normalizasyon ve Fallback İçin)
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_cents = ttm_ebit + ttm_da

        # 3. NAKİT AKIŞI TESPİTİ VE DÖNGÜ ORTASI (MID-CYCLE) KORUMASI
        is_normalized_used = False
        if 'CALC_OWNERS_EARNINGS_TTM' in df.index and float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1]) > 0:
            base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        else:
            # Döngünün dibinde (crack spread çöküşü) veya ağır rafineri bakımı yılında FCF eksiye düşer.
            # Şirketi 0 TL yapmamak için, EBITDA'nın tarihsel nakde dönüşüm oranını (%35) baz alırız.
            base_fcf_cents = ttm_ebitda_cents * 0.35
            is_normalized_used = True
            logger.warning(f"[{ticker}] Negatif/Eksik FCF saptandı. Mid-Cycle EBITDA Normalizasyonu (%35) devreye alındı.")

        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Şirket operasyonel kâr (EBITDA) da üretemiyor. Değerleme bypass edildi."}

        # 4. ENFLASYON DUYARLI DÖNGÜSEL BÜYÜME PROJEKSİYONU
        # Petrokimya yüksek emtia fiyatlarında ciroyu enflasyonun çok üzerinde katlar.
        terminal_growth_rate = risk_free_rate * 0.12 # %35 faiz için ~%4.2 terminal büyüme
        
        # Büyüme patikası: Makro faiz ortamıyla harmonize edilmiş oranlar
        growth_path = [
            risk_free_rate * 0.80,  # 1. Yıl
            risk_free_rate * 0.50,  # 2. Yıl
            risk_free_rate * 0.30,  # 3. Yıl
            risk_free_rate * 0.15,  # 4. Yıl
            terminal_growth_rate    # 5. Yıl
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

        # 6. FİRMA DEĞERİ (Enterprise Value) VE ÖZKAYNAK GEÇİŞİ
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents
        target_equity_value_tl = max(0.0, target_equity_value_cents / 100.0)

        # 7. HİSSE ADEDİ NORMALİZASYONU (Double Division Koruması)
        shares_outstanding = metadata.get("market_data", {}).get("shares_outstanding", None)
        
        if shares_outstanding and shares_outstanding > 0:
            final_target_price_tl = target_equity_value_tl / shares_outstanding
            is_per_share = True
        else:
            final_target_price_tl = target_equity_value_tl
            is_per_share = False
            logger.warning(f"[{ticker}] 'shares_outstanding' eksik. Toplam Piyasa Değeri dönüyor.")

        model_report = {
            "model_used": "Petrokimya_DCF_Optimized",
            "is_fcf_normalized": is_normalized_used,
            "is_divided_by_shares": is_per_share,
            "applied_wacc": discount_rate,
            "terminal_growth_rate_nominal": terminal_growth_rate,
            "pv_of_5_year_fcf_tl": present_value_of_fcf / 100.0,
            "enterprise_value_tl": enterprise_value_cents / 100.0,
            "net_debt_tl": net_debt_cents / 100.0,
            "final_target_price_tl": final_target_price_tl
        }

        return final_target_price_tl, model_report