import logging
import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class NormalizationError(Exception):
    pass

class FinancialNormalizer:
    VERSION = "4.1.0" # Akıllı Veri Çıkarımı (Smart Imputation Support)

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
        
        # Boş satır ve sütunları çöpe at
        df = combined_df.dropna(axis=1, how='all').dropna(axis=0, how='all')
        
        try:
            # Datetime'a çevir, timezone bilgisi varsa temizle, sonra Periyot'a çevir
            clean_columns = pd.to_datetime(df.columns).tz_localize(None)
            df.columns = clean_columns.to_period("Q")
        except Exception as e:
            logger.warning(f"[{ticker}] Periyot dönüşüm hatası: {e}")
            raise NormalizationError(f"Tarih formatı dönüştürülemedi: {e}")

        df = df.sort_index(axis=1)

        # 1. KORUMA: Float64 Cents dönüştürmesi. Numpy "Mean of empty slice" hatasını kalıcı olarak engeller.
        for col in df.columns:
            raw_series = pd.to_numeric(df[col], errors='coerce')
            df[col] = raw_series * self.scaling_factor * 100.0

        # 2. KORUMA: İleri Taşıma (Forward Fill)
        # Eğer bir çeyrekte veri eksikse (NaN), bir önceki çeyreğin verisini oraya kopyala.
        df = df.ffill(axis=1)

        # 3. KORUMA: HOOK'LAR İÇİN METADATA ÇIKARTIMI
        latest_metrics = self._extract_latest_metrics(df)

        metadata = self._generate_metadata(
            ticker=ticker, 
            empty=False, 
            extraction_time=extraction_timestamp_utc,
            periods=[str(p) for p in df.columns]
        )
        
        # Süzdüğümüz kilit verileri Metadata içine enjekte ediyoruz
        metadata.update(latest_metrics)

        return df, metadata

    def _extract_latest_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        En güncel çeyrekten Sektörel Kancaların ihtiyaç duyduğu ham verileri yakalar ve TL'ye çevirip basar.
        Bulamazsa None bırakır ki Hooks içindeki eksik veri kurtarıcı (Smart Imputation) devreye girsin.
        """
        if df.empty:
            return {}

        latest_col = df.columns[-1]
        latest_data = df[latest_col]

        def get_val(keys: List[str]) -> float:
            for key in keys:
                target = key.lower().replace("_", "").replace(" ", "")
                matches = [idx for idx in latest_data.index if str(idx).lower().replace("_", "").replace(" ", "") == target]
                if matches:
                    val = latest_data[matches[0]]
                    if pd.notna(val):
                        # Tabloda Cent (kuruş) olarak tutulduğu için TL'ye (bölü 100) çevirerek veriyoruz.
                        return float(val) / 100.0
            return None

        return {
            "ebitda": get_val(["ebitda", "favok", "normalizedebitda", "normalized ebitda"]),
            "operating_income": get_val(["operatingincome", "ebit", "faaliyetkari", "operating profit", "operating margin"]),
            "depreciation": get_val(["depreciation", "amortization", "depreciationandamortization", "depreciation & amortization"]),
            "total_debt": get_val(["totaldebt", "toplamborc", "shortlongtermdebt", "total debt"]),
            "total_cash": get_val(["cashandcashequivalents", "totalcash", "nakit", "cash and cash equivalents"]),
            "net_debt": get_val(["netdebt", "netborc", "net debt"]),
            "equity": get_val(["totalequity", "equity", "ozkaynaklar", "stockholders equity"]),
            "total_assets": get_val(["totalassets", "toplamvarliklar", "total assets"])
        }

    def _generate_metadata(
        self, ticker: str, empty: bool, extraction_time: str, periods: List[str] = None
    ) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "is_empty": empty,
            "normalizer_version": self.VERSION,
            "currency": self.base_currency,
            "scale_multiplier": self.scaling_factor,
            "storage_format": "float64_cents",
            "extraction_timestamp_utc": extraction_time,
            "normalized_periods": periods or []
        }