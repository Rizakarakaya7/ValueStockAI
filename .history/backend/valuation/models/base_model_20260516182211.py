from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class BaseValuationModel(ABC):
    """
    Tüm sektörel değerleme modellerinin türemek zorunda olduğu Soyut Sınıf (Interface).
    Sistemin her modelden aynı standart çıktıyı beklemesini garanti eder.
    """
    
    @abstractmethod
    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Girdi: Temizlenmiş matris ve Kasa/Borç/Zemin bilgisi içeren metadata.
        Çıktı: (Hedef Piyasa Değeri, Model İç Raporu)
        """
        pass

    def calculate_wacc(self, risk_free_rate: float, beta: float, equity_risk_premium: float) -> float:
        """
        Ağırlıklı Ortalama Sermaye Maliyeti (Basitleştirilmiş Cost of Equity bileşeni).
        Makro verilerden alınan risksiz getiri ve sektörel beta ile hesaplanır.
        """
        # CAPM (Sermaye Varlıkları Fiyatlama Modeli)
        cost_of_equity = risk_free_rate + (beta * equity_risk_premium)
        return cost_of_equity