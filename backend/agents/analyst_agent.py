# analyst_agent.py

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any

from agents.prompts import (
    RISK_SYSTEM_PROMPT, RISK_USER_TEMPLATE,
    MACRO_SYSTEM_PROMPT, MACRO_USER_TEMPLATE,
    QUANT_SYSTEM_PROMPT, QUANT_USER_TEMPLATE,
    CIO_SYSTEM_PROMPT, CIO_USER_TEMPLATE
)

logger = logging.getLogger(__name__)

class AnalystAgent:
    """
    4-Ajanlı Yatırım Komitesi (Parallel Multi-Agent Architecture).
    Risk, Makro ve Quant ajanları paralel çalışarak veriyi analiz eder.
    CIO ajanı bu üçünün görüşünü sentezleyip nihai halka açık raporu yazar.
    """
    
    def __init__(self, gemini_client=None):
        self.client = gemini_client

    def _prepare_payload_string(self, pipeline_result: Dict[str, Any]) -> str:
        try:
            return json.dumps(pipeline_result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Pipeline JSON dönüştürme hatası: {str(e)}")
            return str(pipeline_result)

    async def _call_llm(self, user_prompt: str, system_prompt: str) -> str:
        """LLM'e istek atan ortak yardımcı fonksiyon."""
        if not self.client:
            return "LLM Client bulunamadı. Veri okunamadı."
        
        try:
            response = await self.client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.3, # Yaratıcılığı biraz açtık ki halk dili doğal olsun
                    "top_p": 0.95
                }
            )
            return response.text
        except Exception as e:
            logger.error(f"LLM API çağrısı sırasında hata: {str(e)}")
            return f"[HATA OLUŞTU: {str(e)}]"

    async def generate_investment_report(self, pipeline_result: Dict[str, Any]) -> str:
        ticker = pipeline_result.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Komite (Multi-Agent) süreci başlatıldı.")

        if not self.client:
            logger.warning(f"[{ticker}] Canlı LLM Client yok! Fallback Mock Rapor üretiliyor.")
            return self._generate_fallback_mock_report(pipeline_result)

        engine_json_str = self._prepare_payload_string(pipeline_result)
        bugunun_tarihi = datetime.now().strftime("%d.%m.%Y")

        # 1. AŞAMA: PARALEL ÇALIŞAN UZMANLAR (Aynı anda istek atılır)
        logger.info(f"[{ticker}] Risk, Makro ve Matematik ajanları paralel analiz yapıyor...")
        
        risk_task = self._call_llm(
            user_prompt=RISK_USER_TEMPLATE.format(engine_json_str=engine_json_str),
            system_prompt=RISK_SYSTEM_PROMPT
        )
        
        macro_task = self._call_llm(
            user_prompt=MACRO_USER_TEMPLATE.format(engine_json_str=engine_json_str),
            system_prompt=MACRO_SYSTEM_PROMPT
        )
        
        quant_task = self._call_llm(
            user_prompt=QUANT_USER_TEMPLATE.format(engine_json_str=engine_json_str),
            system_prompt=QUANT_SYSTEM_PROMPT
        )

        # Üç ajanın işini bitirmesini bekliyoruz
        risk_report, macro_report, quant_report = await asyncio.gather(risk_task, macro_task, quant_task)

        # 2. AŞAMA: SENTEZ (CIO AJANI)
        logger.info(f"[{ticker}] CIO Ajanı nihai sentez raporunu yazıyor...")
        
        cio_user_prompt = CIO_USER_TEMPLATE.format(
            ticker=ticker,
            current_date=bugunun_tarihi,
            risk_report=risk_report,
            macro_report=macro_report,
            quant_report=quant_report
        )

        final_report = await self._call_llm(
            user_prompt=cio_user_prompt,
            system_prompt=CIO_SYSTEM_PROMPT
        )

        logger.info(f"[{ticker}] Komite raporu başarıyla tamamlandı.")
        return final_report

    def _generate_fallback_mock_report(self, res: Dict[str, Any], error_msg: str = None) -> str:
        ticker = res.get("ticker", "UNKNOWN")
        bugun = datetime.now().strftime("%d.%m.%Y")
        return f"""# {ticker} HİSSE DEĞERLEME RAPORU (SİSTEM OTOMATİK ÇIKTISI)
**UYARI:** Yapay Zeka Servisi şu anda devre dışıdır ({error_msg or 'Client Enjekte Edilmedi'}). Rapor matematiksel veri motorundan doğrudan üretilmiştir.

## 1. YÖNETİCİ ÖZETİ
- **Tarih:** {bugun}
- **Hisse Kodu:** {ticker}
- **Mevcut Fiyat:** {res.get('current_price')} TL
- **Hesaplanan Adil Değer:** {res.get('intrinsic_price_per_share')} TL
- **Getiri Potansiyeli:** % {res.get('upside_potential_pct')}
"""