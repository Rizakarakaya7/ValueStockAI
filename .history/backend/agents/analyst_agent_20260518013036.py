# analyst_agent.py

import json
import logging
from datetime import datetime
from typing import Dict, Any

from agents.prompts import ANALYST_SYSTEM_PROMPT, ANALYST_USER_TEMPLATE

logger = logging.getLogger(__name__)

class AnalystAgent:
    """
    Quant Engine'in (Orchestrator) ürettiği saf matematiksel çıktıları,
    prompts.py içindeki katı kurallara sadık kalarak Wall Street formatında
    bir yatırım raporuna (Markdown) dönüştüren Ajan Servisi.
    """
    
    def __init__(self, gemini_client=None):
        self.client = gemini_client

    def _prepare_payload_string(self, pipeline_result: Dict[str, Any]) -> str:
        try:
            return json.dumps(pipeline_result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Pipeline JSON dönüştürme hatası: {str(e)}")
            return str(pipeline_result)

    async def generate_investment_report(self, pipeline_result: Dict[str, Any]) -> str:
        ticker = pipeline_result.get("ticker", "UNKNOWN")
        logger.info(f"[{ticker}] Analist Ajanı yatırım raporu yazma sürecini başlattı.")

        # 1. Ham JSON verisini hazırla
        engine_json_str = self._prepare_payload_string(pipeline_result)

        # --- DÜZELTME BURADA YAPILDI ---
        # 2. Sistemin güncel tarihini alıp (Gün.Ay.Yıl) formatına çeviriyoruz
        bugunun_tarihi = datetime.now().strftime("%d.%m.%Y")

        # 3. Prompt'u LLM'e göndermeden önce hem veriyi hem de TESPİT EDİLMİŞ TARİHİ içine basıyoruz
        user_content = ANALYST_USER_TEMPLATE.format(
            engine_json_str=engine_json_str,
            current_date=bugunun_tarihi
        )

        if not self.client:
            logger.warning(f"[{ticker}] Canlı LLM Client bulunamadı! Fallback Mock Rapor üretiliyor.")
            return self._generate_fallback_mock_report(pipeline_result)

        try:
            response = await self.client.aio.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_content,
                config={
                    "system_instruction": ANALYST_SYSTEM_PROMPT,
                    "temperature": 0.1, 
                    "top_p": 0.95
                }
            )
            
            logger.info(f"[{ticker}] LLM Raporu başarıyla üretildi.")
            return response.text

        except Exception as e:
            logger.error(f"[{ticker}] LLM API çağrısı sırasında kritik hata: {str(e)}")
            return self._generate_fallback_mock_report(pipeline_result, error_msg=str(e))

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