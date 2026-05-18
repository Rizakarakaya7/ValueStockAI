import logging
import time  
import sys
import asyncio
import os

# 1. Ortam değişkenlerini sisteme yükler
from dotenv import load_dotenv
load_dotenv()

# WINDOWS PLAYWRIGHT (SUBPROCESS) YAMASI
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from valuation.engine.orchestrator import ValuationOrchestrator
from valuation.engine.state_machine import StateManager
from agents.analyst_agent import AnalystAgent

# 2. GEMINI CLIENT ENTEGRASYONU
from google import genai

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="ValueStockAI Quant Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servis Başlatmaları
state_manager = StateManager()
orchestrator = ValuationOrchestrator(state_manager=state_manager)

# 3. LLM API Anahtarını al ve Client'ı oluştur
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    logger.info("Gemini API Anahtarı bulundu. Analist Ajanı 'Canlı' modda başlatılıyor.")
    gemini_client = genai.Client(api_key=gemini_api_key)
else:
    logger.warning("GEMINI_API_KEY bulunamadı! Analist Ajanı 'Mock' modunda çalışacak.")
    gemini_client = None

# Ajanımıza Client'ı Enjekte Ediyoruz
analyst_agent = AnalystAgent(gemini_client=gemini_client) 

class ValuationResponse(BaseModel):
    ticker: str
    quant_payload: dict
    analyst_report: str

@app.get("/api/v1/health")
async def health_check():
    return {"status": "operational", "engine": "running"}

@app.get("/api/v1/valuate/{ticker}", response_model=ValuationResponse)
async def valuate_stock(ticker: str):
    ticker = ticker.upper().strip()
    job_id = f"job_{ticker}_{int(time.time())}"
    
    logger.info(f"YENİ İSTEK ALINDI: {ticker} (Job ID: {job_id})")
    
    try:
        # Önce matematiksel motor (Quant Engine) çalışır
        quant_result = await orchestrator.execute_job(job_id=job_id, ticker=ticker)
        
        # Sonra sonuçlar yapay zekaya (Analist Ajanı) gönderilir
        report_markdown = await analyst_agent.generate_investment_report(pipeline_result=quant_result)
        
        return ValuationResponse(
            ticker=ticker,
            quant_payload=quant_result,
            analyst_report=report_markdown
        )
        
    except Exception as e:
        logger.error(f"Değerleme sırasında sunucu hatası ({ticker}): {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))