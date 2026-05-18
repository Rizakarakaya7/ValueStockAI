import logging
import datetime
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np

# Merkezi loglama standartı
logger = logging.getLogger(__name__)

class NormalizationError(Exception):
    """Veri hizalama veya kalibrasyon hataları için özel istisna."""
    pass

class MalformedPeriodError(NormalizationError):
    pass

class FinancialNormalizer:
    """
    Ham finansal API payload'larını kurumsal seviye, vectorization destekleyen
    (Int64 bazlı) ve versioned metadata taşıyan Pandas matrislerine dönüştürür.
    """
    
    # Backtesting ve Regression Tespiti için Normalizer Versiyonu
    VERSION = "1.0.0"

    def __init__(self, currency_code: str = "TRY", scaling_factor: int = 1):
        self.base_currency = currency_code
        self.scaling_factor = scaling_factor
        self._display_registry: Dict[str, str] = {}

    def _validate_periods(self, periods: List[Dict[str, str]]) -> None:
        """API'den gelen periyot objelerinin bütünlüğünü doğrular."""
        if not periods or not isinstance(periods, list):
            raise MalformedPeriodError("Periyot verisi boş veya liste formatında değil.")
        
        for p in periods:
            if not isinstance(p, dict) or 'year' not in p or 'period' not in p:
                raise MalformedPeriodError(f"Hatalı periyot yapısı: {p}")
            if not p.get('year') or not p.get('period'):
                raise MalformedPeriodError(f"Periyot içerisinde boş değer (year/period) mevcut: {p}")

    def normalize_isyatirim_payload(
        self, 
        ticker: str,
        raw_data: List[Dict[str, Any]], 
        actual_periods: List[Dict[str, str]],
        extraction_timestamp_utc: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        İş Yatırım formatındaki ham veriyi standardize eder.
        
        Args:
            ticker: Hisse kodu
            raw_data: Extractor'dan gelen raw payload.
            actual_periods: API'den dönen doğrulanmış dönemler.
            extraction_timestamp_utc: Verinin API'den çekildiği an (Look-ahead bias koruması için).
        """
        # 1. Validation Phase
        self._validate_periods(actual_periods)
        
        df = pd.DataFrame(raw_data)
        
        if df.empty:
            logger.warning(f"[{ticker}] Normalizer'a boş payload geldi.")
            return pd.DataFrame(), self._generate_metadata(ticker, True, extraction_timestamp_utc)

        # 2. Taxonomy & Display Registry
        if 'itemDescTr' in df.columns and 'itemCode' in df.columns:
            new_registry = pd.Series(df.itemDescTr.values, index=df.itemCode).to_dict()
            self._display_registry.update(new_registry)
            columns_to_drop = [c for c in ['itemDescTr', 'itemDescEng'] if c in df.columns]
            df.drop(columns=columns_to_drop, inplace=True)

        # 3. Duplicate Handling (Summation Strategy)
        if df.duplicated(subset=['itemCode']).any():
            duplicate_count = df.duplicated(subset=['itemCode']).sum()
            logger.info(f"[{ticker}] {duplicate_count} adet duplicate 'itemCode' bulundu. Summation uygulanıyor.")
            
            numeric_cols = [col for col in df.columns if str(col).startswith('value')]
            for col in numeric_cols:
                # String temizliği ve memory-efficient geçici float cast'i
                df[col] = pd.to_numeric(df[col].astype("string").str.replace(',', ''), errors='coerce')
            
            df = df.groupby('itemCode', as_index=False)[numeric_cols].sum(min_count=1)

        # Canonical API Kodu
        df.set_index('itemCode', inplace=True)

        # 4. Explicit Column Mapping & Q-Semantics
        column_mapping = {}
        for idx, period in enumerate(actual_periods, start=1):
            col_key = f"value{idx}"
            if col_key in df.columns:
                year = period.get('year')
                month_int = int(period.get('period'))
                
                # Finansal Çeyrek Hesaplaması (1-3: Q1, 4-6: Q2 ...)
                quarter = (month_int - 1) // 3 + 1
                q_period_str = f"{year}Q{quarter}"
                column_mapping[col_key] = q_period_str

        df = df[list(column_mapping.keys())].rename(columns=column_mapping)

        # Gerçek PeriodIndex Dönüşümü (freq="Q") - TTM hesaplamaları için şart!
        df.columns = pd.PeriodIndex(df.columns, freq="Q")

        # 5. Institutional Grade Storage (Int64 Cents) + Scaling Application
        for col in df.columns:
            # İş Yatırım'dan string gelme ihtimaline karşı virgül temizliği
            raw_series = pd.to_numeric(df[col].astype("string").str.replace(',', ''), errors='coerce')
            
            # Kuruşa Çevirme (x100) + Metadata Scaling Factor Çarpanı + Int64 Cast
            df[col] = (raw_series * self.scaling_factor * 100).round(0).astype('Int64')

        # 6. Column Ordering Guarantee
        df = df.sort_index(axis=1)

        # 7. Lineage & Versioned Metadata
        metadata = self._generate_metadata(
            ticker=ticker, 
            empty=False, 
            extraction_time=extraction_timestamp_utc,
            periods=[str(p) for p in df.columns]
        )

        return df, metadata

    def _generate_metadata(
        self, 
        ticker: str, 
        empty: bool, 
        extraction_time: str,
        periods: List[str] = None
    ) -> Dict[str, Any]:
        """Data lineage, audit trail ve context metadata oluşturur."""
        return {
            "ticker": ticker,
            "is_empty": empty,
            "normalizer_version": self.VERSION,
            "currency": self.base_currency,
            "scale_multiplier": self.scaling_factor,
            "storage_format": "Int64_cents",
            "extraction_timestamp_utc": extraction_time,
            "normalization_timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "normalized_periods": periods or [],
            "display_registry_keys_count": len(self._display_registry)
        }