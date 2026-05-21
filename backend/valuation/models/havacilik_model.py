import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class HavacilikModel(BaseValuationModel):
    def calculate_intrinsic_value(self, df: pd.DataFrame, metadata: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        
        # 1. KUR DÖNÜŞÜMÜ (FX-AWARE) - THYAO Gibi Döviz Raporlayanlar İçin Kritik!
        currency = str(metadata.get("market_data", {}).get("currency", "TRY")).split('.')[-1].upper()
        
        # Gerçek bir sistemde bu FX rate metadata içinden (örn: metadata.get("fx_usd_try")) 
        # dinamik gelmelidir. Şimdilik güvenlik ağı (fallback) olarak sabitliyoruz:
        fx_rate = 1.0
        if currency == "USD":
            fx_rate = 32.20  
        elif currency == "EUR":
            fx_rate = 35.10
        
        # debt_adjuster.py IFRS-16 düzeltmesini halihazırda yaptığı için çifte sayımı kaldırdık!
        total_adjusted_debt_try = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0.0) / 100.0

        # 2. TTM EBITDA HESAPLAMASI (Mükerrer satır engellemesi ile)
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        # Tüm eşleşenleri ".sum().sum()" ile toplamak yerine, 
        # kârı 2'ye katlamamak için matristeki İLK geçerli taxonomy etiketini alıyoruz.
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        
        # Kuruş (cents) formatından kurtarıp, doğru FX çarpanı ile TRY bazına oturtuyoruz
        ttm_ebitda_try = ((ttm_ebit + ttm_da) / 100.0) * fx_rate
        
        if ttm_ebitda_try <= 0:
            logger.warning(f"[{ticker}] TTM EBITDA (TRY) negatif. Değerleme yapılamıyor.")
            return 0.0, {"error": "Negative EBITDA", "blended_equity_tl": 0.0}

        # 3. DİNAMİK ÇARPAN YÖNETİMİ
        leverage_ratio = total_adjusted_debt_try / ttm_ebitda_try if ttm_ebitda_try > 0 else 5.0
        
        is_thyao = (ticker == "THYAO")
        base_ebitda_mult = 6.5 if is_thyao else 6.0
        base_oe_mult = 9.0 if is_thyao else 8.5
        
        # Kaldıraç cezalandırması / ödüllendirmesi
        if leverage_ratio > 3.5:
            base_ebitda_mult -= 0.5
            base_oe_mult -= 1.0
        elif leverage_ratio < 1.5:
            base_ebitda_mult += 0.5
            base_oe_mult += 0.5

        # 4. OWNER EARNINGS (SAHİPLİK KAZANÇLARI)
        if "CALC_OWNERS_EARNINGS_TTM" in df.index:
            oe_raw = float(df.loc["CALC_OWNERS_EARNINGS_TTM"].iloc[-1]) / 100.0
            oe_try = oe_raw * fx_rate
        else:
            oe_ratio = max(0.30, min(0.50, 0.50 - (leverage_ratio * 0.05)))
            oe_try = ttm_ebitda_try * oe_ratio
            
        oe_try = min(oe_try, ttm_ebitda_try * 0.7)

        # 5. FİRMA DEĞERİ (EV) HESAPLAMA
        ev_ebitda_eq = max(0, (ttm_ebitda_try * base_ebitda_mult) - total_adjusted_debt_try)
        ev_oe_eq = max(0, (oe_try * base_oe_mult))
        
        blended_equity_tl = (ev_ebitda_eq * 0.65) + (ev_oe_eq * 0.35)
        
        return blended_equity_tl, {
            "ticker": ticker,
            "currency_applied": currency,
            "fx_rate_multiplier": fx_rate,
            "ttm_ebitda_try": ttm_ebitda_try,
            "leverage_ratio": leverage_ratio,
            "blended_equity_tl": blended_equity_tl
        }