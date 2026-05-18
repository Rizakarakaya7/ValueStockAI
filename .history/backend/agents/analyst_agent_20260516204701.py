# analyst_agent.py

import json
import logging
from datetime import datetime
from typing import Dict, Any

# Prompts dosyasından katı kurallarımızı içeri alıyoruz
from agents.prompts import ANALYST_SYSTEM_PROMPT, ANALYST_USER_TEMPLATE

logger = logging.getLogger(__name__)

class AnalystAgent:
    """
    Quant Engine'in (Orchestrator) ürettiği saf matematiksel çıktıları,
    prompts.py içindeki katı kurallara sadık kalarak Wall Street formatında
    bir yatırım raporuna (Markdown) dönüştüren Ajan Servisi.
    """
    
    def __init__(self, gemini_client=None):
        """
        Gemini veya herhangi bir LLM Client'ı dışarıdan enjekte edilir (Dependency Injection).
        Bu sayede test edilebilirlik kolaylaşır.
        """
        self.client = gemini_client

    def _prepare_payload_string(self, pipeline_result: Dict[str, Any]) -> str:
        """
        Gelen devasa pipeline sonucunu temiz bir şekilde stringleştirir.
        Gereksiz ham veri çöplükleri varsa burada elenebilir.
        """
        try:
            # Okunabilirliği artırmak için indentli biçimlendiriyoruz
            return json.dumps(pipeline_result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Pipeline JSON dönüştürme hatası: {str(e)}")
            return str(pipeline_result)

    async def generate_investment_report(self, pipeline_result: Dict[str, Any]) -> str:
        """
        Orkestratör tamamlandığında çağrılan ana asenkron fonksiyon.
        """
        ticker = pipeline_result.get("ticker", "UNKNOWN")
        sector = pipeline_result.get("sector", "UNKNOWN")
        logger.info(f"[{ticker}] Analist Ajanı yatırım raporu yazma sürecini başlattı.")

        # 1. Ham JSON verisini hazırla
        engine_json_str = self._prepare_payload_string(pipeline_result)

        # 2. Kullanıcı promptunu şablon ile birleştir
        user_content = ANALYST_USER_TEMPLATE.format(engine_json_str=engine_json_str)

        # 3. Eğer canlı bir LLM Client enjekte edilmediyse Mock/Fallback rapor üret (Sistem patlamasın)
        if not self.client:
            logger.warning(f"[{ticker}] Canlı LLM Client bulunamadı! Fallback Mock Rapor üretiliyor.")
            return self._generate_fallback_mock_report(pipeline_result)

        try:
            # 4. Google Gemini API (Asenkron Çağrı)
            # Not: Kullanılan SDK sürümüne göre 'aio' veya asenkron client yapısı çağrılır.
            # Burada standart asenkron gemini protokolü modellenmiştir.
            response = await self.client.aio.models.generate_content(
                model='gemini-2.5-flash', # Hız ve maliyet odaklı en güncel analitik model
                contents=user_content,
                config={
                    "system_instruction": ANALYST_SYSTEM_PROMPT,
                    "temperature": 0.1, # Yaratıcılığı neredeyse sıfırlıyoruz, tam tutarlılık sağlar.
                    "top_p": 0.95
                }
            )
            
            logger.info(f"[{ticker}] LLM Raporu başarıyla üretildi.")
            return response.text

        except Exception as e:
            logger.error(f"[{ticker}] LLM API çağrısı sırasında kritik hata: {str(e)}")
            # API çökerse yatırımcı ekransız kalmasın, kural bazlı fallback raporu döndür
            return self._generate_fallback_mock_report(pipeline_result, error_msg=str(e))

    def _generate_fallback_mock_report(self, res: Dict[str, Any], error_msg: str = None) -> str:
        """LLM API'sinin çöktüğü veya olmadığı durumlarda üretilecek steril kural bazlı rapor."""
        ticker = res.get("ticker", "UNKNOWN")
        return f"""# {ticker} HİSSE DEĞERLEME RAPORU (SİSTEM OTOMATİK ÇIKTISI)
**UYARI:** Yapay Zeka Servisi şu anda devre dışıdır ({error_msg or 'Client Enjekte Edilmedi'}). Rapor matematiksel veri motorundan doğrudan üretilmiştir.

## 1. YÖNETİCİ ÖZETİ
- **Hisse Kodu:** {ticker}
- **Mevcut Fiyat:** {res.get('current_price')} TL
- **Hesaplanan Adil Değer:** {res.get('intrinsic_value')} TL
- **Getiri Potansiyeli:** % {res.get('upside_potential_pct')}

## 2. MOTOR PARAMETRELERİ
- **Uygulanan Model:** {res.get('valuation_metadata', {}).get('model_report', {}).get('model_used', 'Bilinmiyor')}
- **Ham Ham Değer:** {res.get('base_intrinsic_value')} TL

## 3. UYARI
Lütfen sistem yöneticinizle görüşerek LLM API bağlantılarını kontrol edin. Rakamlar yukarıda belirtildiği gibidir.
"""