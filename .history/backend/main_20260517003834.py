import logging
import time  # EKLENDİ: time modülü içe aktarıldı
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from valuation.engine.orchestrator import ValuationOrchestrator
from valuation.engine.state_machine import StateManager
from agents.analyst_agent import AnalystAgent

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

state_manager = StateManager()
orchestrator = ValuationOrchestrator(state_manager=state_manager)
analyst_agent = AnalystAgent(gemini_client=None) 

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
    
    # DÜZELTİLDİ: logging.time.time() yerine time.time() kullanıldı
    job_id = f"job_{ticker}_{int(time.time())}"
    
    logger.info(f"YENİ İSTEK ALINDI: {ticker} (Job ID: {job_id})")
    
    try:
        quant_result = await orchestrator.execute_job(job_id=job_id, ticker=ticker)
        report_markdown = await analyst_agent.generate_investment_report(pipeline_result=quant_result)
        
        return ValuationResponse(
            ticker=ticker,
            quant_payload=quant_result,
            analyst_report=report_markdown
        )
        
    except Exception as e:
        logger.error(f"Değerleme sırasında sunucu hatası ({ticker}): {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))