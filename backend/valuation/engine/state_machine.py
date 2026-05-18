import logging
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ==========================================
# 1. DURUM SABİTLERİ (Enums)
# ==========================================
class PipelineStatus(Enum):
    """Değerleme boru hattının geçebileceği aşamalar."""
    PENDING = "PENDING"
    DATA_FETCHED = "DATA_FETCHED"
    NORMALIZED = "NORMALIZED"
    VALUED = "VALUED"
    HOOKED = "HOOKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ==========================================
# 2. PYDANTIC ŞEMASI (Veri Modeli)
# ==========================================
class JobState(BaseModel):
    """Bir değerleme görevinin (Job) anlık durumunu tutan veri yapısı."""
    job_id: str
    status: PipelineStatus
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_msg: Optional[str] = None


# ==========================================
# 3. YÖNETİCİ SINIF (Manager)
# ==========================================
class StateManager:
    """
    Orkestratörün adımlarını takip eden modül.
    Geliştirme aşamasında olduğumuz için şimdilik verileri In-Memory (RAM) 
    üzerinde bir sözlükte tutar. İleride Redis'e bağlanabilir.
    """
    
    def __init__(self):
        # Görev ID'lerini ve durumlarını tutan RAM içi veritabanı
        self._store: Dict[str, JobState] = {}

    async def update_state(self, job_id: str, status: PipelineStatus, error_msg: str = None):
        """Orkestratör yeni bir aşamaya geçtiğinde durumu günceller."""
        state = JobState(
            job_id=job_id,
            status=status,
            error_msg=error_msg,
            updated_at=datetime.now(timezone.utc)
        )
        self._store[job_id] = state
        
        if error_msg:
            logger.error(f"[{job_id}] DURUM: {status.value} | HATA: {error_msg}")
        else:
            logger.debug(f"[{job_id}] DURUM GÜNCELLENDİ: {status.value}")

    async def get_state(self, job_id: str) -> Optional[JobState]:
        """İstenilen bir görevin durumunu döndürür."""
        return self._store.get(job_id)