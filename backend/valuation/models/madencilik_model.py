import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class MadencilikModel(BaseValuationModel):
    """
    MADENCİLİK SEKTÖRÜ İZOLE MODELLİ (Örn: KOZAL, KOZAA)
    'Depleting Asset' (Tükenen Varlık) arketipi. 
    Perpetuity Illusion (Sonsuzluk İllüzyonu) kısıtı nedeniyle Terminal Büyüme 0'dır.
    Cash Destruction (Nakit İmhası) hatasını engellemek için operasyonel değer ile 
    net nakit kesin hatlarla ayrılır.
    """
    
    SECTOR_BETA = 0.70               
    TERMINAL_GROWTH_RATE = 0.00      # Maden tükenir. Büyüme sıfırdır.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] Madencilik/Emtia DCF Modeli çalıştırılıyor (BIST Optimize).")
        
        # 1. MAKRO FAİZ VE İSKONTO (WACC) HESABI
        risk_free_rate = metadata.get("macro_context", {}).get("tr_risk_free_rate", 0.35)  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. TTM EBITDA HESABI (Normalizasyon İçin)
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_cents = ttm_ebit + ttm_da

        # 3. NAKİT AKIŞI TESPİTİ VE MİD-CYCLE KORUMASI
        is_normalized_used = False
        if 'CALC_OWNERS_EARNINGS_TTM' in df.index and float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1]) > 0:
            base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        else:
            # Madencilikte ağır rezerv arama (Exploration) giderleri FCF'i eksi yapabilir.
            # Şirketi sıfırlamamak için EBITDA'nın %35'i (Sektör standardı) serbest nakde çevrilir.
            base_fcf_cents = ttm_ebitda_cents * 0.35
            is_normalized_used = True
            logger.warning(f"[{ticker}] Negatif/Eksik FCF saptandı. Mid-Cycle EBITDA Normalizasyonu (%35) uygulandı.")

        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif EBITDA. Operasyonel kâr üretilemiyor."}

        # 4. TÜKENEN VARLIK İÇİN ENFLASYON UYUMLU AZALAN BÜYÜME (Decaying Growth)
        # Maden ömrü azaldığı için nominal büyüme faize oranla bile yıllar içinde sıfıra yakınsar.
        growth_path = [
            risk_free_rate * 0.60,  
            risk_free_rate * 0.40,  
            risk_free_rate * 0.20,  
            0.05,  
            0.00   
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

        # 5. UÇ DEĞER (Terminal Value) - PERPETUITY ILLUSION KESİNTİSİ
        # Maden şirketleri sonsuza kadar yaşamaz. Gordon formülü yerine, 
        # nakit akışını doğrudan iskonto oranına bölüp rezerv ömrü riski yansıtılır.
        terminal_value = projected_cash_flows[-1] / discount_rate
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        # Sadece madenin (operasyonun) değeri
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 6. CASH DESTRUCTION (NAKİT İMHASI) KORUMASI VE NET BORÇ
        # KOZAL gibi şirketlerin ekside olan (yani pozitif) devasa net nakitleri,
        # operasyonel iskonto ve tükenme cezalarından arındırılarak değere BİREBİR (1:1) eklenmelidir.
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        # Toplam Şirket Değeri (TL) - Zemin (Floor) testinden geçmesi için
        target_equity_value_tl = max(0.0, target_equity_value_cents / 100.0)

        model_report = {
            "model_used": "Madencilik_Depleting_Asset_DCF",
            "is_fcf_normalized": is_normalized_used,
            "applied_wacc": discount_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100.0,
            "zero_terminal_growth_applied": True,
            "enterprise_value_tl": enterprise_value_cents / 100.0,
            "net_cash_premium_applied": net_debt_cents < 0,
            "total_equity_value_target_tl": target_equity_value_tl
        }

        # Toplam değer orchestrator'a gönderiliyor (Hisse başına indirgeme üst katmanda yapılacak)
        return target_equity_value_tl, model_report