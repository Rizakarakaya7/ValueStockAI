import asyncio
import logging
from typing import List, Dict
from datetime import datetime, timezone
from extractors.yf_engine import YFinanceEngine
from normalizer import FinancialNormalizer

logger = logging.getLogger(__name__)

class BistPipelineOrchestrator:
    def __init__(self, max_concurrent_tasks: int = 5):
        self.engine = YFinanceEngine()
        self.normalizer = FinancialNormalizer()
        # Aynı anda çalışan asenkron görev sayısını sınırlar (Rate limit'e destek)
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)

    async def _process_single_ticker(self, ticker: str) -> Dict:
        async with self.semaphore:
            logger.info(f"[{ticker}] Veri çekimi başlatılıyor...")
            raw_data = await self.engine.fetch_all_data_async(ticker)
            
            timestamp = datetime.now(timezone.utc).isoformat()
            
            try:
                # Sadece finansal matrisi normalize et
                normalized_df, metadata = self.normalizer.normalize_financials(
                    ticker, raw_data["financials"], timestamp
                )
                
                return {
                    "ticker": ticker,
                    "status": "success",
                    "market_data": raw_data["market_data"],
                    "financial_matrix": normalized_df,
                    "metadata": metadata
                }
            except Exception as e:
                logger.error(f"[{ticker}] Normalizasyon hatası: {e}")
                return {"ticker": ticker, "status": "error", "error": str(e)}

    async def run_pipeline(self, tickers: List[str]):
        tasks = [self._process_single_ticker(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r.get("status") == "success")
        logger.info(f"Pipeline Tamamlandı. Başarılı: {success_count}/{len(tickers)}")
        return results