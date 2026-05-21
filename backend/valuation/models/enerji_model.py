import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class EnerjiModel(BaseValuationModel):
    """
    ENERJİ SEKTÖRÜ İZOLE MODELLİ (BIST UYUMLU) (Örn: ENJSA, GWIND)
    Elektrik üretim/dağıtım şirketleri yüksek borçla kurulur ancak nakit akışları (YEKDEM, EPİAŞ vb.) 
    garanti altındadır. Yüksek FAVÖK marjı, yüksek CapEx ve Enflasyon duyarlı Regulated Yield modeli.
    """
    
    SECTOR_BETA = 0.85               # Defansif. Krizlerde bile temel enerji tüketimi devam eder.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI # Enerji bilançoları Sanayi/Üretim formatındadır
        logger.info(f"[{ticker}] Enerji Regulated Yield DCF Modeli çalıştırılıyor (BIST Optimize).")
        
        # 1. MAKRO FAİZ VE UYUMLU İSKONTO (WACC) HESABI
        risk_free_rate = metadata.get("macro_context", {}).get("tr_risk_free_rate", 0.35)  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 2. TTM EBITDA HESABI (Yedekleme ve Normalizasyon İçin)
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_cents = ttm_ebit + ttm_da

        # 3. NAKİT AKIŞI (FCF) KONTROLÜ VE MİD-CYCLE NORMALİZASYON
        is_normalized_used = False
        if 'CALC_OWNERS_EARNINGS_TTM' in df.index and float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1]) > 0:
            base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        else:
            # Enerji şirketleri yeni RES/GES kurarken nakit eksiye düşer. Şirketi 0'lamamak için:
            # Enerjide ağır finansman giderleri ve bakım yatırımları (CapEx) nedeniyle EBITDA'nın ortalama %25'i serbest nakde döner.
            base_fcf_cents = ttm_ebitda_cents * 0.25
            is_normalized_used = True
            logger.warning(f"[{ticker}] Negatif/Eksik FCF saptandı. Mid-Cycle EBITDA Normalizasyonu (%25) devreye alındı.")

        if base_fcf_cents <= 0:
            logger.warning(f"[{ticker}] Şirket operasyonel kâr (EBITDA) da üretemiyor. Değerleme bypass edildi.")
            return 0.0, {"warning": "Negatif EBITDA."}

        # 4. ENFLASYON/FAİZ DUYARLI DİNAMİK BÜYÜME PROJEKSİYONU
        # Sabit [0.25, 0.15...] kullanmak yerine BIST makro dinamiklerine uygun büyüme patikası:
        terminal_growth_rate = risk_free_rate * 0.15 # %35 faiz için ~%5.2 uzun vadeli büyüme
        
        # Enerjide regüle fiyat artışları (zamlar) enflasyona yakınsar, ancak hacim (megawatt) sınırlıdır.
        growth_path = [
            risk_free_rate * 0.90,  # 1. Yıl (Enflasyonun gerisinde kalan elektrik zammı simülasyonu)
            risk_free_rate * 0.60,  # 2. Yıl
            risk_free_rate * 0.40,  # 3. Yıl
            risk_free_rate * 0.20,  # 4. Yıl
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

        # 5. UÇ DEĞER (Terminal Value) HESAPLAMA
        if discount_rate <= terminal_growth_rate:
            discount_rate = terminal_growth_rate + 0.05 # Matematiksel koruma
            
        terminal_value = (projected_cash_flows[-1] * (1 + terminal_growth_rate)) / (discount_rate - terminal_growth_rate)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 6. NET BORÇ DÜZELTMESİ (TL bazında Toplam Şirket Özkaynak Değeri)
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents
        target_equity_value_tl = max(0.0, target_equity_value_cents / 100.0)

        # 7. HİSSE ADEDİ (SHARES OUTSTANDING) NORMALİZASYONU
        # Yüzlerce milyarlık şirket değerini, doğru hisse fiyatına indirger.
        shares_outstanding = metadata.get("market_data", {}).get("shares_outstanding", None)
        
        if shares_outstanding and shares_outstanding > 0:
            final_target_price_tl = target_equity_value_tl / shares_outstanding
            is_per_share = True
        else:
            # Metadata'da bilgi yoksa, harmanlama katmanı için Toplam Değer döndürülür.
            final_target_price_tl = target_equity_value_tl
            is_per_share = False
            logger.warning(f"[{ticker}] 'shares_outstanding' verisi bulunamadı. Toplam Piyasa Değeri döndürülüyor.")

        model_report = {
            "model_used": "Enerji_Regulated_Yield_DCF",
            "is_fcf_normalized": is_normalized_used,
            "is_divided_by_shares": is_per_share,
            "applied_wacc": discount_rate,
            "terminal_growth_rate_nominal": terminal_growth_rate,
            "pv_of_fcf_tl": present_value_of_fcf / 100.0,
            "enterprise_value_tl": enterprise_value_cents / 100.0,
            "net_debt_tl": net_debt_cents / 100.0,
            "total_equity_value_target_tl": target_equity_value_tl,
            "final_target_price_tl": final_target_price_tl
        }

        return final_target_price_tl, model_report