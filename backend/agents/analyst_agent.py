# backend/agents/analyst_agent.py

import json
import logging
import time
import math
from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from agents.prompts import NARRATIVE_SYSTEM_PROMPT, NARRATIVE_USER_TEMPLATE

logger = logging.getLogger(__name__)

class NarrativeOutput(BaseModel):
    yonetici_ozeti: str
    matematiksel_analiz: str
    risk_ve_makro_analiz: str

class AnalystAgent:
    def __init__(self, gemini_client=None):
        self.client = gemini_client
        self.model_name = 'gemini-2.5-flash'

    def _recursive_find(self, data: Any, target_keys: list) -> Any:
        if isinstance(data, dict):
            for k, v in data.items():
                if str(k).lower() in [t.lower() for t in target_keys]:
                    if v is not None and not (isinstance(v, float) and math.isnan(v)):
                        return v
            for k, v in data.items():
                result = self._recursive_find(v, target_keys)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._recursive_find(item, target_keys)
                if result is not None:
                    return result
        return None

    def _safe_get(self, data: Dict[str, Any], keys_to_try: list, default: Any = None) -> Any:
        val = self._recursive_find(data, keys_to_try)
        if val is not None:
            if isinstance(val, float):
                return round(val, 2)
            return val
        return default

    # --- PURE PYTHON ENGINES ---

    def _quant_engine(self, upside: float) -> int:
        if upside > 40: return 9
        if upside > 25: return 7
        if upside > 10: return 6
        if upside > -10: return 4
        return 2

    # DİKKAT: Eski genel geçer (Generic) _risk_engine BURADAN SİLİNDİ!
    # Risk hesaplaması artık sektör bazlı olarak Hooks'ta (Örn: petrokimya_hooks.py) yapılıyor.

    def _decision_engine(self, upside: float, risk_score: int) -> str:
        
        """Kural Bazlı Karar Motoru"""
        
        adjusted_risk = risk_score - 2 if upside > 100 else risk_score
        if upside > 30 and risk_score <= 6:
            return "AL"
        elif upside > 15 and risk_score <= 7:
            return "TUT"
        elif risk_score >= 9:
            return "UZAK DUR"
        
        else:
            return "TUT"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_narrative_with_retry(self, payload_str: str) -> NarrativeOutput:
        if not self.client:
            raise Exception("LLM Client yok.")
            
        # DİKKAT: dict yerine types.GenerateContentConfig kullanıyoruz!
        config = types.GenerateContentConfig(
            system_instruction=NARRATIVE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1 
        )
        
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=NARRATIVE_USER_TEMPLATE.format(payload=payload_str),
            config=config
        )
        
        result_dict = json.loads(response.text)
        return NarrativeOutput(**result_dict)

    async def generate_investment_report(self, pipeline_result: Dict[str, Any]) -> str:
        ticker = pipeline_result.get("ticker", "UNKNOWN")
        sektor = self._safe_get(pipeline_result, ["sector", "sektor", "industry"], "Bilinmiyor")
        
        # 1. TEMEL DEĞERLER
        current_price = self._safe_get(pipeline_result, ["current_price", "price"], 0)
        intrinsic_price = self._safe_get(pipeline_result, ["intrinsic_price_per_share", "fairValue"], 0)
        upside = self._safe_get(pipeline_result, ["upside_potential_pct", "upside"], 0)

        logger.info(f"[{ticker}] Deterministik Python motorları çalışıyor...")

        # 2. PYTHON ENGINES (Deterministik Hesaplamalar)
        quant_score = self._quant_engine(upside)
        
        # YENİ RİSK ENTEGRASYONU: Risk verilerini kendi hesaplamak yerine Pipeline'dan (Hooks'tan) hazır çek!
        risk_score = self._safe_get(pipeline_result, ["sector_risk_score"], 5)  # Hooks'tan gelmezse default 5
        key_risks = self._safe_get(pipeline_result, ["sector_risk_flags"], ["Sektörel risk analizi uygulanamadı."])
        
        # 3. NİHAİ KARAR (Python veriyor)
        final_decision = self._decision_engine(upside, risk_score)
        
        narrative_payload = {
            "ticker": ticker,
            "sektor": sektor,
            "decision": final_decision,
            "upside": f"% {upside:.2f}",
            "scores": {
                "quant_score_10": quant_score,
                "risk_score_10": risk_score
            },
            "key_risks": key_risks
        }

        # 4. LLM NARRATOR (Açıklama Katmanı)
        try:
            payload_json = json.dumps(narrative_payload, indent=2, ensure_ascii=False)
            logger.info(f"[{ticker}] Karar ({final_decision}) verildi. LLM raporu yazıyor (Risk Skoru: {risk_score})...")
            narrative = await self._generate_narrative_with_retry(payload_json)
        except Exception as e:
            logger.error(f"[{ticker}] LLM API 3 denemede de başarısız oldu: {str(e)}")
            return self._generate_failover_report(ticker, current_price, intrinsic_price, upside, final_decision, key_risks)

        # 5. KESİN MARKDOWN ÇIKTISI
        uyarilar_markdown = "\n".join([f"> - {r}" for r in key_risks])

        final_markdown = f"""# {ticker} YATIRIM KOMİTESİ KARAR RAPORU

---
### 📦 1. YÖNETİCİ ÖZETİ VE POTANSİYEL KAZANÇ
> **Vitrindeki Fiyatı (Şu Anki):** {current_price:.2f} TL
> **Bizim Hesapladığımız Gerçek Ederi:** {intrinsic_price:.2f} TL
> **Potansiyel Kazanç / Kayıp:** % {upside:.2f}
> **Komite Kararı:** **{final_decision}**
---

### 🧮 2. MATEMATİKSEL GERÇEKLER (Değer Nereden Geliyor?)
> {narrative.matematiksel_analiz}

---

### ⚠️ 3. RİSKLER VE FRENLEYİCİ FAKTÖRLER
> {narrative.risk_ve_makro_analiz}
**Tespit Edilen Sektörel Uyarılar:**
{uyarilar_markdown}

---
### 🎯 4. NİHAİ KARAR AÇIKLAMASI
> {narrative.yonetici_ozeti}
---
"""
        return final_markdown

    def _generate_failover_report(self, ticker, current_price, intrinsic_price, upside, decision, risks) -> str:
        risk_str = "\n".join([f"- {r}" for r in risks])
        return f"""# {ticker} YATIRIM KOMİTESİ KARAR RAPORU
**SİSTEM UYARISI:** Doğal Dil İşleme servisi şu an yanıt vermiyor. Aşağıdaki veriler saf deterministik motor çıktılarıdır.

- **Vitrindeki Fiyatı:** {current_price:.2f} TL
- **Gerçek Ederi:** {intrinsic_price:.2f} TL
- **Potansiyel:** % {upside:.2f}
- **NİHAİ KARAR:** {decision}

**Sektörel Risk Bayrakları:**
{risk_str}
"""