import logging
import pandas as pd
from typing import Dict, Any, Tuple
from valuation.models.base_model import BaseValuationModel
from valuation.bist_registry import CurrencyType

logger = logging.getLogger(__name__)

class OtomotivModel(BaseValuationModel):
    """
    OTOMOTİV SEKTÖRÜ İZOLE MODELLİ (Örn: FROTO, TOASO)
    Otomotiv şirketleri "Model Döngüsü" ile çalışır. Yeni araç platformu (örn: Elektrikli Ticari)
    yatırımları sırasında CapEx zirve yapar, FCF düşer. Sonraki yıllarda hasat toplanır.
    """
    
    SECTOR_BETA = 1.10               # BİST ortalamasına yakın, nispeten defansif (İhracat koruması)
    TERMINAL_GROWTH_RATE = 0.02      # Global otomotiv pazarı olgun bir pazardır, büyüme muhafazakardır.
    PROJECTION_YEARS = 5

    def calculate_intrinsic_value(
        self, 
        df: pd.DataFrame, 
        metadata: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        
        ticker = metadata.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Otomotiv EV/Model Geçişli DCF Modeli çalıştırılıyor.")
        
        if 'CALC_OWNERS_EARNINGS_TTM' not in df.index:
            raise ValueError(f"[{ticker}] Patronun Nakdi (Owner's Earnings) eksik.")
            
        base_fcf_cents = float(df.loc['CALC_OWNERS_EARNINGS_TTM'].iloc[-1])
        
        if base_fcf_cents <= 0:
            return 0.0, {"warning": "Negatif FCF tespit edildi. Döngü dibi veya ağır CapEx yılı. Zemin (Floor) beklenecek."}

        # BİST Otomotiv devlerinin (FROTO, TOASO) gelirleri büyük oranda Euro'dur.
        # Eğer metadata functional_currency = EUR diyorsa, risksiz getiri TL tahvilleri yerine Eurobond/Euribor bazlı düşünülmeli.
        # Not: Şimdilik basitleştirilmiş lokal WACC kullanıyoruz, ileride kur bazlı WACC'a geçilebilir.
        func_currency = metadata.get("functional_currency", CurrencyType.TRY)
        
        risk_free_rate = 0.35  
        erp = 0.08             
        discount_rate = self.calculate_wacc(risk_free_rate, self.SECTOR_BETA, erp)

        # 1. OTOMOTİV MODEL DÖNGÜSÜ (Model Cycle Projection)
        projected_cash_flows = []
        current_fcf = base_fcf_cents
        present_value_of_fcf = 0.0
        
        # Varsayım: Otomotiv sektörü önümüzdeki 2 yıl elektrikli araç (EV) bantları için ağır yatırım (CapEx)
        # yapacak, nakit akışı yavaşlayacak, 3. yıldan itibaren satış patlamasıyla hasat toplanacak.
        # Bu pattern: J-Curve (J Eğrisi) nakit akışıdır.
        growth_path = [0.05, 0.02, 0.15, 0.12, 0.05]
        
        for year in range(1, self.PROJECTION_YEARS + 1):
            growth = growth_path[year - 1]
            current_fcf = current_fcf * (1 + growth)
            projected_cash_flows.append(current_fcf)
            
            discount_factor = (1 + discount_rate) ** year
            present_value_of_fcf += (current_fcf / discount_factor)

        # 2. UÇ DEĞER VE FİRMA DEĞERİ
        terminal_value = (projected_cash_flows[-1] * (1 + self.TERMINAL_GROWTH_RATE)) / (discount_rate - self.TERMINAL_GROWTH_RATE)
        pv_of_terminal_value = terminal_value / ((1 + discount_rate) ** self.PROJECTION_YEARS)
        
        enterprise_value_cents = present_value_of_fcf + pv_of_terminal_value

        # 3. KİRA (IFRS-16) VE NET BORÇ DÜZELTMESİ
        net_debt_cents = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0)
        target_equity_value_cents = enterprise_value_cents - net_debt_cents

        target_equity_value_tl = target_equity_value_cents / 100.0

        model_report = {
            "model_used": "Otomotiv_Model_Cycle_DCF",
            "applied_wacc": discount_rate,
            "functional_currency_flag": func_currency.value,
            "pv_of_fcf_tl": present_value_of_fcf / 100,
            "enterprise_value_tl": enterprise_value_cents / 100,
        }

        return target_equity_value_tl, model_report