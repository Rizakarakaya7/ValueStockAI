import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Sistemin ana modülleri
from valuation.engine.orchestrator import ValuationOrchestrator
from valuation.engine.state_machine import StateManager
from agents.analyst_agent import AnalystAgent

# Loglama ayarları (Uygulamanın konsolda temiz görünmesi için)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# FastAPI Uygulamasını Başlat
app = FastAPI(title="ValueStockAI Quant Engine", version="1.0.0")

# CORS Ayarları (Frontend'in Backend'e sorunsuz istek atabilmesi için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Prod ortamında spesifik IP'lere daraltılır
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servislerin Global Olarak Başlatılması (Singleton)
state_manager = StateManager()
orchestrator = ValuationOrchestrator(state_manager=state_manager)
# İleride buraya gerçek Gemini Client'ı eklenecek. Şimdilik None vererek kural bazlı raporu tetikliyoruz.
analyst_agent = AnalystAgent(gemini_client=None) 

# Çıktı Şeması
class ValuationResponse(BaseModel):
    ticker: str
    quant_payload: dict
    analyst_report: str

@app.get("/api/v1/health")
async def health_check():
    """Sistemin ayakta olup olmadığını kontrol eden basit uç nokta."""
    return {"status": "operational", "engine": "running"}

@app.get("/api/v1/valuate/{ticker}", response_model=ValuationResponse)
async def valuate_stock(ticker: str):
    """
    Kullanıcıdan gelen hisse kodunu (Örn: FROTO) alır, değerleme motorunu 
    ve ardından Analist Ajanı'nı tetikleyerek nihai paketi döner.
    """
    ticker = ticker.upper().strip()
    job_id = f"job_{ticker}_{int(logging.time.time())}"
    
    logger.info(f"YENİ İSTEK ALINDI: {ticker} (Job ID: {job_id})")
    
    try:
        # 1. Kantitatif Motoru (Orchestrator) Çalıştır
        quant_result = await orchestrator.execute_job(job_id=job_id, ticker=ticker)
        
        # 2. Üretilen sonucu LLM Ajanına ver ve raporu al
        report_markdown = await analyst_agent.generate_investment_report(pipeline_result=quant_result)
        
        # 3. İkisini birleştir ve arayüze (Frontend'e) gönder
        return ValuationResponse(
            ticker=ticker,
            quant_payload=quant_result,
            analyst_report=report_markdown
        )
        
    except Exception as e:
        logger.error(f"Değerleme sırasında sunucu hatası ({ticker}): {str(e)}")
        # API çökmelerini standart HTTP 500 hatası olarak Frontend'e bildiriyoruz
        raise HTTPException(status_code=500, detail=str(e))