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

class FinancialNormalizer:
    """
    Ham finansal API payload'larını kurumsal seviye, vectorization destekleyen
    (Int64 bazlı) ve versioned metadata taşıyan Pandas matrislerine dönüştürür.
    Yahoo Finance API standartlarına göre revize edilmiştir.
    """
    
    # Backtesting ve Regression Tespiti için Normalizer Versiyonu
    VERSION = "3.0.0"

    def __init__(self, currency_code: str = "TRY", scaling_factor: int = 1):
        self.base_currency = currency_code
        self.scaling_factor = scaling_factor

    def normalize_yfinance_payload(
        self, 
        ticker: str,
        raw_data: Dict[str, Any], 
        extraction_timestamp_utc: str
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Yahoo Finance formatındaki ham veriyi standardize eder.
        Sütunlar tarih (Datetime), satırlar finansal metriklerdir.
        
        Args:
            ticker: Hisse kodu
            raw_data: YFinance Extractor'dan gelen 3 tablolu raw payload.
            extraction_timestamp_utc: Verinin API'den çekildiği an.
        """
        
        # 1. Validation Phase
        if not raw_data or not isinstance(raw_data, dict):
            logger.warning(f"[{ticker}] Normalizer'a boş veya geçersiz payload geldi.")
            return pd.DataFrame(), self._generate_metadata(ticker, True, extraction_timestamp_utc)

        df_list = []
        
        # 2. 3 Ana Tablonun Birleştirilmesi (Consolidation)
        for stmt_name, data_dict in raw_data.items():
            if not data_dict:
                continue
                
            # yfinance verisi dict'ten DataFrame'e çevrildiğinde:
            # Sütunlar = Tarihler, Satırlar = Finansal Kalemler olarak gelir
            stmt_df = pd.DataFrame(data_dict)
            df_list.append(stmt_df)
            
        if not df_list:
            logger.warning(f"[{ticker}] İşlenebilir finansal tablo bulunamadı.")
            raise NormalizationError(f"{ticker} için işlenebilir finansal tablo bulunamadı.")

        # Tabloları dikey eksende birleştir (Tarih sütunları otomatik hizalanır)
        combined_df = pd.concat(df_list, axis=0)
        
        # 3. Duplicate Handling
        # yfinance'de aynı kalem (örn: Net Income) hem gelir tablosunda hem nakit akışında olabilir
        # Satırları (index) kontrol edip mükerrerleri temizliyoruz
        combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
        
        df = combined_df
        
        # 4. PeriodIndex Dönüşümü (freq="Q") - TTM ve Vectorized hesaplamalar için şart!
        try:
            df.columns = pd.to_datetime(df.columns).to_period("Q")
        except Exception as e:
            logger.warning(f"[{ticker}] Periyot dönüşüm hatası: {e}")
            raise NormalizationError(f"Tarih formatı PeriodIndex'e dönüştürülemedi: {e}")

        # 5. Zaman tünelini kronolojik sıraya diz (Eskiden Yeniye / Soldan Sağa)
        df = df.sort_index(axis=1)

        # 6. Institutional Grade Storage (Int64 Cents) + Scaling Application
        for col in df.columns:
            # YFinance'den gelen değerleri güvenli numeric tipe cast et
            raw_series = pd.to_numeric(df[col], errors='coerce')
            
            # Kuruşa Çevirme (x100) + Metadata Scaling Factor Çarpanı + Int64 Cast
            # NaN değerler Int64 tipinde <NA> olarak kalır ve hafıza/işlem avantajı sağlar
            df[col] = (raw_series * self.scaling_factor * 100).round(0).astype('Int64')

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
            "normalized_periods": periods or []
        }