import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode
import logging

logger = logging.getLogger(__name__)

class BankacilikModel(BaseValuationModel):
    """
    BANKACILIK SEKTÖRÜ İZOLE MODELLİ (Örn: AKBNK, ISCTR)
    Bankalar için FAVÖK/DCF işlemez. Bunun yerine 'Residual Income' (Aşırı Getiri)
    veya Temettü İndirgeme Modeli (DDM) türevleri kullanılır.
    """
    
    # Sektöre Özel Sabitler
    SECTOR_BETA = 1.30               # Bankacılık endeksi BİST'in lokomotifi ve daha volatildir
    TERMINAL_ROE_PREMIUM = 0.01      # Sonsuzlukta ROE'nin COE'yi ancak %1 geçebileceği varsayımı
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.BANKING
        
        logger.info(f"[{ticker}] Bankacılık Residual Income Modeli çalıştırılıyor.")
        
        # 1. GİRDİLERİN ÇEKİLMESİ (Stock vs Flow Strict Typing koruması altında)
        # Bankalarda Net Borç hesabı yapılmaz. Hedef doğrudan Özkaynak Değeridir.
        equity_keys = get_taxonomy_keys(reporting_group, FinancialConcept.TOTAL_EQUITY)
        net_income_keys = get_taxonomy_keys(reporting_group, FinancialConcept.NET_INCOME)
        
        if not equity_keys or not net_income_keys:
            logger.error(f"[{ticker}] Banka değerlemesi için gerekli taxonomy mapping eksik.")
            return 0.0, {"warning": "Missing Taxonomy for Banking"}
            
        # Son çeyrekteki Defter Değeri (Book Value)
        current_book_value_cents = float(df.loc[equity_keys, df.columns[-1]].sum(skipna=True))
        
        # Son 4 Çeyrek (TTM) Net Kâr (Kümülatif çözücüden çıkmış yalın çeyreklerin toplamı)
        # Sütun bazlı TTM toplamını al
        net_income_ttm_cents = float(df.loc[net_income_keys, df.columns[-4:]].sum().sum())
        
        # 2. MEVCUT ÖZKAYNAK KÂRLILIĞI (Current ROE)
        if current_book_value_cents <= 0:
            return 0.0, {"warning": "Negative Book Value (İflas Riski)"}
            
        current_roe = net_income_ttm_cents / current_book_value_cents
        
        # 3. SERMAYE MALİYETİ (Cost of Equity - COE)
        risk_free_rate = 0.35  
        erp = 0.08             
        coe = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 4. AŞIRI GETİRİ (RESIDUAL INCOME) PROJEKSİYONU
        projected_residual_incomes = []
        projected_book_values = [current_book_value_cents]
        
        # Bankanın ROE'sinin 5 yıl içinde kademeli olarak hedef ROE'ye düşeceği/çıkacağı varsayımı
        # Piyasada hiçbir banka sonsuza dek %60 ROE üretemez (Ortalamaya dönüş)
        target_roe = coe + 0.02 # Uzun vadede maliyeti sadece 2 puan yenebilir varsayımı
        roe_path = [current_roe - ((current_roe - target_roe) / self.PROJECTION_YEARS) * i for i in range(1, self.PROJECTION_YEARS + 1)]
        
        dividend_payout_ratio = 0.15 # BİST bankaları kârın çoğunu bünyede tutar (BDDK regülasyonları)
        
        present_value_of_ri = 0.0
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            year_roe = roe_path[year - 1]
            prev_bv = projected_book_values[-1]
            
            # O yılki net kâr ve dağıtılmayan kârın özkaynağa eklenmesi
            net_income = prev_bv * year_roe
            retained_earnings = net_income * (1 - dividend_payout_ratio)
            new_bv = prev_bv + retained_earnings
            projected_book_values.append(new_bv)
            
            # Residual Income (Aşırı Getiri) = (ROE - COE) * Önceki Yılın Defter Değeri
            residual_income = (year_roe - coe) * prev_bv
            projected_residual_incomes.append(residual_income)
            
            # İndirgeme
            present_value_of_ri += residual_income / ((1 + coe) ** year)

        # 5. UÇ DEĞER (Terminal Value)
        # Sonsuzluktaki Artık Değer (Terminal RI)
        terminal_ri = (roe_path[-1] - coe) * projected_book_values[-1]
        terminal_growth = 0.0 # Artık getiride büyüme olmaz varsayımı muhafazakardır
        pv_of_terminal_ri = (terminal_ri / (coe - terminal_growth)) / ((1 + coe) ** self.PROJECTION_YEARS)

        # 6. NİHAİ DEĞER (HİSSE DEĞERİ)
        # Banka Değeri = Mevcut Defter Değeri + Gelecek Aşırı Getirilerin Bugünü
        target_equity_value_cents = current_book_value_cents + present_value_of_ri + pv_of_terminal_ri
        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Banking_Residual_Income",
            "current_roe": current_roe,
            "cost_of_equity_coe": coe,
            "current_book_value_tl": current_book_value_cents / 100,
            "pv_of_residual_income_tl": present_value_of_ri / 100,
            "pv_of_terminal_ri_tl": pv_of_terminal_ri / 100
        }

        return target_equity_value_tl, model_report