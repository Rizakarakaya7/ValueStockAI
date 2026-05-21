import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class CimentoModel(BaseValuationModel):
    """
    ÇİMENTO SEKTÖRÜ İZOLE MODELLİ (Örn: AKCNS, CIMSA, OYAKC)
    İç piyasa inşaat döngülerine duyarlı, yüksek sabit maliyetli (High Operating Leverage) 
    ve enerji yoğun şirketler için Döngüsel DCF modeli.
    """
    
    SECTOR_BETA = 1.05               # İnşaat döngülerine bağlıdır ama BİST ortalamasına yakındır.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] Çimento Döngüsel DCF Modeli çalıştırılıyor.")
        
        # 1. MAKRO FAİZ VE UYUMLU İSKONTO (WACC) HESABI
        risk_free_rate = metadata.get("macro_context", {}).get("tr_risk_free_rate", 0.35)  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. SEKTÖREL EBITDA VE NORMALLEŞTİRİLMİŞ FCF HESABI
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_cents = ttm_ebit + ttm_da

        # 3. NAKİT AKIŞI TESPİTİ VE DÖNGÜSEL KORUMA (CYCLICAL PROTECTION)
        is_normalized_used = False
        if 'CALC_OWNERS_EARNINGS_TTM' in df.index and float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1]) > 0:
            base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        else:
            # Döngünün dibinde veya ağır CapEx yılında Mid-Cycle normalizasyonu (%35'e çekildi - Muhafazakar)
            base_fcf_cents = ttm_ebitda_cents * 0.35
            is_normalized_used = True
            logger.warning(f"[{ticker}] Normal dışı FCF. Mid-Cycle EBITDA Normalizasyonu (%35) uygulandı.")

        if base_fcf_cents <= 0:
            return 0.0, {"warning": "EBITDA negatif veya sıfır. Değerleme bypass edildi."}

        # 4. OPTİMİZE EDİLMİŞ MUHAFAZAKAR NOMİNAL BÜYÜME PROJEKSİYONU
        # Sektörel daralma ve yüksek faiz baskısını simüle etmek için ilk yılların köpüğünü aldık.
        terminal_growth_rate = risk_free_rate * 0.12 # %35 faiz ortamında ~%4.2 sürdürülebilir terminal büyüme
        
        growth_path = [
            risk_free_rate * 0.80,  # 1. Yıl (Faiz baskısı nedeniyle nominal büyüme geride kalır: Örn %28)
            risk_free_rate * 0.60,  # 2. Yıl
            risk_free_rate * 0.40,  # 3. Yıl
            risk_free_rate * 0.20,  # 4. Yıl
            terminal_growth_rate    # 5. Yıl (Terminal istikrar seviyesi)
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

        # 5. UÇ DEĞER (Terminal Value) HESAPLAMA
        if discount_rate <= terminal_growth_rate:
            discount_rate = terminal_growth_rate + 0.05
            
        terminal_value = (projected_cash_flows[-1] * (1 + terminal_growth_rate)) / (discount_rate - terminal_growth_rate)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 6. NET BORÇ DÜZELTMESİ (TL bazında Özkaynak Değeri)
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents
        target_equity_value_tl = max(0.0, target_equity_value_cents / 100.0)

        # 7. HİSSE ADEDİ NORMALİZASYONU (Kritik Düzeltme!)
        # Şirket toplam değerini hisse başına indirgiyoruz.
        # Metadata'da yoksa sistemin çökmemesi için fallback olarak 1.0 (toplam firma değeri) kabul edilir.
        shares_outstanding = metadata.get("market_data", {}).get("shares_outstanding", None)
        
        if shares_outstanding and shares_outstanding > 0:
            final_target_price_tl = target_equity_value_tl / shares_outstanding
            is_per_share = True
        else:
            # Üst katmanlarda (floors_multiples veya orchestrator) bölünme ihtimaline karşı yedek koruma:
            final_target_price_tl = target_equity_value_tl
            is_per_share = False
            logger.warning(f"[{ticker}] 'shares_outstanding' verisi metadata içinde bulunamadı! Toplam Piyasa Değeri döndürülüyor.")

        model_report = {
            "model_used": "Cimento_Cyclical_DCF",
            "is_fcf_normalized": is_normalized_used,
            "is_divided_by_shares": is_per_share,
            "shares_outstanding_applied": shares_outstanding,
            "applied_wacc": discount_rate,
            "enterprise_value_tl": enterprise_value_cents / 100.0,
            "net_debt_tl": net_debt_cents / 100.0,
            "total_equity_value_target_tl": target_equity_value_tl,
            "final_target_price_tl": final_target_price_tl
        }

        return final_target_price_tl, model_report