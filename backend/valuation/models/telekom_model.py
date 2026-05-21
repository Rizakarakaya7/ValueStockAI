import pandas as pd
from typing import Dict, Any, Tuple
import logging

from valuation.models.base_model import BaseValuationModel
from valuation.core_logic.taxonomy_registry import FinancialConcept, get_taxonomy_keys
from valuation.bist_registry import FinancialGroupCode

logger = logging.getLogger(__name__)

class TelekomModel(BaseValuationModel):
    """
    TELEKOMÜNİKASYON SEKTÖRÜ İZOLE MODELİ (BIST UYUMLU) (Örn: TCELL, TTKOM)
    Yüksek amortisman, döviz bazlı ağır CapEx gereksinimi ve 
    'EBITDA İllüzyonu' filtreli, BIST tarihsel çarpanlarına optimize edilmiş karma model.
    """
    
    def calculate_intrinsic_value(self, df: pd.DataFrame, metadata: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        ticker = metadata.get("ticker", "UNKNOWN")
        reporting_group = FinancialGroupCode.SANAYI
        logger.info(f"[{ticker}] Telekomünikasyon Sektör Modeli çalıştırılıyor (BIST Optimize).")
        
        # 1. NET BORÇ DÜZELTMESİ
        total_debt_try = metadata.get("balance_sheet_snapshot", {}).get("net_debt_cents", 0.0) / 100.0

        # 2. TTM EBITDA HESAPLAMA
        ebit_keys = get_taxonomy_keys(reporting_group, FinancialConcept.EBIT)
        da_keys = get_taxonomy_keys(reporting_group, FinancialConcept.DEPRECIATION)
        
        valid_ebit = [k for k in ebit_keys if k in df.index]
        valid_da = [k for k in da_keys if k in df.index]
        
        ttm_ebit = float(df.loc[valid_ebit[0], df.columns[-4:]].sum()) if valid_ebit else 0.0
        ttm_da = float(df.loc[valid_da[0], df.columns[-4:]].sum()) if valid_da else 0.0
        ttm_ebitda_try = (ttm_ebit + ttm_da) / 100.0
        
        if ttm_ebitda_try <= 0:
            logger.warning(f"[{ticker}] TTM EBITDA negatif veya sıfır. Değerleme bypass edildi.")
            return 0.0, {"error": "Negative EBITDA"}

        # 3. BIST-SPESİFİK DİNAMİK ÇARPAN YÖNETİMİ
        # Amortisman yükü (EBITDA İllüzyonu)
        da_to_ebitda_ratio = ttm_da / (ttm_ebit + ttm_da) if (ttm_ebit + ttm_da) > 0 else 0.0
        
        # Gelişmekte olan pazar (EM) Telekom tarihsel çarpanları daha düşüktür (Risk/Faiz baskısı)
        base_ebitda_mult = 4.0  # Eski 5.0'dan BIST gerçeğine çekildi
        base_oe_mult = 5.0      # Eski 7.0'dan muhafazakar seviyeye çekildi
        
        # 4. OWNER EARNINGS (HİSSEDAR NAKİT AKIŞI) HESABI
        if "CALC_OWNERS_EARNINGS_TTM" in df.index:
            oe_raw = float(df.loc["CALC_OWNERS_EARNINGS_TTM"].iloc[-1]) / 100.0
            # Sistemden gelen OE, amortisman/capex şokunu yansıtmıyorsa güvenlik marjı uygula
            oe_try = min(oe_raw, ttm_ebitda_try * 0.25)
        else:
            # Telekomların ağır CapEx ve faiz yükü nedeniyle EBITDA'nın ancak %15-%20'si serbest nakde döner.
            oe_try = ttm_ebitda_try * 0.18 
        
        # 5. FİRMA DEĞERİ (EV) VE HARMANLANMIŞ OTO-DEĞER
        ev_ebitda_eq = max(0, (ttm_ebitda_try * base_ebitda_mult) - total_debt_try)
        ev_oe_eq = max(0, (oe_try * base_oe_mult))
        
        if da_to_ebitda_ratio > 0.60:
            logger.warning(f"[{ticker}] EBITDA İllüzyonu Saptandı! Amortisman/EBITDA Oranı: %{da_to_ebitda_ratio*100:.2f}.")
            # Amortisman çok yüksekse, şirketin gerçeği EBITDA değil, kalan cılız Nakit Akışıdır (OE).
            # OE modelinin ağırlığı radikal şekilde artırılır.
            ebitda_weight, oe_weight = 0.30, 0.70
        else:
            ebitda_weight, oe_weight = 0.60, 0.40
            
        # Toplam Şirket Değeri (TL)
        blended_equity_tl = (ev_ebitda_eq * ebitda_weight) + (ev_oe_eq * oe_weight)

        model_report = {
            "model_used": "Telekom_Infrastructure_Adjusted_BIST",
            "ttm_ebitda_tl": ttm_ebitda_try,
            "da_to_ebitda_ratio": round(da_to_ebitda_ratio, 4),
            "applied_ebitda_mult": base_ebitda_mult,
            "applied_oe_mult": base_oe_mult,
            "is_ebitda_illusion_triggered": da_to_ebitda_ratio > 0.60,
            "applied_ebitda_weight": ebitda_weight,
            "net_debt_tl": total_debt_try,
            "total_equity_value_tl": blended_equity_tl
        }

        # Üst katman (floors_multiples.py veya orchestrator) bu toplam değeri hisse adedine bölecektir.
        return blended_equity_tl, model_report