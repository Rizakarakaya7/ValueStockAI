import logging
import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

class NormalizationError(Exception):
    pass

class FinancialNormalizer:
    VERSION = "4.0.0" # Protected Pipeline Sürümü

    def __init__(self, currency_code: str = "TRY", scaling_factor: int = 1):
        self.base_currency = currency_code
        self.scaling_factor = scaling_factor

    def normalize_financials(
        self, 
        ticker: str,
        raw_financials: Dict[str, Any], 
        extraction_timestamp_utc: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        
        if not raw_financials:
            return pd.DataFrame(), self._generate_metadata(ticker, True, extraction_timestamp_utc)

        df_list = []
        
        # Tabloları güvenli bir şekilde dolaş
        for stmt_name in ["income_statement", "balance_sheet", "cash_flow"]:
            data_dict = raw_financials.get(stmt_name, {})
            if not data_dict:
                logger.debug(f"[{ticker}] {stmt_name} verisi boş, atlanıyor.")
                continue
                
            stmt_df = pd.DataFrame(data_dict)
            if not stmt_df.empty:
                df_list.append(stmt_df)
            
        if not df_list:
            logger.warning(f"[{ticker}] İşlenebilir hiçbir finansal tablo bulunamadı.")
            return pd.DataFrame(), self._generate_metadata(ticker, True, extraction_timestamp_utc)

        combined_df = pd.concat(df_list, axis=0)
        combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
        
        df = combined_df.dropna(axis=1, how='all') # Tamamen boş sütunları at
        
        try:
            # Datetime'a çevir, timezone bilgisi varsa temizle, sonra Periyot'a çevir
            clean_columns = pd.to_datetime(df.columns).tz_localize(None)
            df.columns = clean_columns.to_period("Q")
        except Exception as e:
            logger.warning(f"[{ticker}] Periyot dönüşüm hatası: {e}")
            raise NormalizationError(f"Tarih formatı dönüştürülemedi: {e}")

        df = df.sort_index(axis=1)

        # Int64 Vectorized Casting
        for col in df.columns:
            raw_series = pd.to_numeric(df[col], errors='coerce')
            df[col] = (raw_series * self.scaling_factor * 100).round(0).astype('Int64')

        metadata = self._generate_metadata(
            ticker=ticker, 
            empty=False, 
            extraction_time=extraction_timestamp_utc,
            periods=[str(p) for p in df.columns]
        )

        return df, metadata

    def _generate_metadata(
        self, ticker: str, empty: bool, extraction_time: str, periods: List[str] = None
    ) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "is_empty": empty,
            "normalizer_version": self.VERSION,
            "currency": self.base_currency,
            "scale_multiplier": self.scaling_factor,
            "storage_format": "Int64_cents",
            "extraction_timestamp_utc": extraction_time,
            "normalized_periods": periods or []
        }