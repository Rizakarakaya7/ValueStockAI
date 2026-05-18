import logging
import asyncio
import yfinance as yf
from typing import Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """
    Sistemin genel makroekonomik iklimini belirleyen ana şalterler.
    Kullanıcı arayüzünden (UI) veya bir LLM ajanı tarafından anlık olarak ayarlanabilir.
    """
    NORMAL = "normal"
    BULL_MARKET = "bull_market"           # Düşük faiz, yüksek yabancı girişi
    STAGFLATION = "stagflation"           # Yüksek enflasyon, düşük büyüme
    CRISIS_MODE = "crisis_mode"           # CDS patlamış, kur şoku var

class MacroContextManager:
    """
    Tüm sektörel Kancalar (Hooks) için gereken makro veriyi tek bir merkezde toplar.
    Küresel verileri canlı (YFinance), yerel verileri ise Rejim bazlı üretir.
    """
    
    def __init__(self, current_regime: MarketRegime = MarketRegime.NORMAL):
        self.current_regime = current_regime
        # İleride veritabanı veya TCMB API eklenecekse client'lar burada tanımlanır.

    async def _fetch_live_global_macros(self) -> Dict[str, float]:
        """
        Yahoo Finance üzerinden global emtia ve parite verilerini asenkron çeker.
        """
        global_data = {}
        # Semboller: Brent (BZ=F), Altın (GC=F), EUR/USD (EURUSD=X)
        tickers = {"brent": "BZ=F", "gold": "GC=F", "eur_usd": "EURUSD=X"}
        
        def _get_prices():
            prices = {}
            for key, symbol in tickers.items():
                try:
                    tkr = yf.Ticker(symbol)
                    prices[key] = float(tkr.fast_info.last_price)
                except Exception as e:
                    logger.warning(f"Makro veri çekilemedi ({symbol}): {e}")
                    prices[key] = None
            return prices

        try:
            global_data = await asyncio.to_thread(_get_prices)
        except Exception as e:
            logger.error(f"Global makro veri havuzu çöktü: {e}")

        return global_data

    def _generate_local_macros_by_regime(self) -> Dict[str, Any]:
        """
        TCMB faizleri, CDS ve EPDK gibi canlı çekilmesi zor olan yerel regülatif 
        verileri, seçilen 'Piyasa Rejimine' (Market Regime) göre simüle eder.
        """
        macros = {}
        
        if self.current_regime == MarketRegime.NORMAL:
            macros = {
                "tr_5yr_cds": 300,
                "foreign_portfolio_flows": "neutral",
                "tcmb_rate_cycle": "neutral",
                "tr_mortgage_rate_annual": 40.0,
                "epdk_price_cap_pressure": "low",
                "tr_fiscal_deficit_trend": "stable",
                "tr_consumer_confidence_index": 75.0,
                "expected_cpi_inflation": 45.0,
                "try_annual_depreciation_forecast": 30.0
            }
        elif self.current_regime == MarketRegime.CRISIS_MODE:
            macros = {
                "tr_5yr_cds": 650, # Yabancı kaçar, Holdingler iskonto yer
                "foreign_portfolio_flows": "strong_outflow",
                "tcmb_rate_cycle": "aggressive_hiking", # Bankalar NIM daralması yaşar
                "tr_mortgage_rate_annual": 60.0, # Çimento ve GYO çöker
                "epdk_price_cap_pressure": "high", # Enerji şirketlerine tavan fiyat gelir
                "tr_fiscal_deficit_trend": "deteriorating", # Savunma şirketleri tahsilat yapamaz
                "tr_consumer_confidence_index": 50.0, # Perakende hacim kaybeder
                "expected_cpi_inflation": 70.0,
                "try_annual_depreciation_forecast": 60.0 # Madenciler ve ihracatçılar (FROTO) bayram eder
            }
        elif self.current_regime == MarketRegime.BULL_MARKET:
            macros = {
                "tr_5yr_cds": 150,
                "foreign_portfolio_flows": "strong_inflow",
                "tcmb_rate_cycle": "easing",
                "tr_mortgage_rate_annual": 25.0,
                "epdk_price_cap_pressure": "low",
                "tr_fiscal_deficit_trend": "improving",
                "tr_consumer_confidence_index": 90.0,
                "expected_cpi_inflation": 25.0,
                "try_annual_depreciation_forecast": 15.0
            }
        
        # Sektörel Özel Sinyaller (Şimdilik Nötr varsayılanlar)
        macros.update({
            "med_crack_spread_trend": "stable",
            "global_pmi": 50.0,
            "eu_auto_market": "stable",
            "min_wage_hike_surprise_pct": 0.0,
            "global_geopolitical_risk": "normal",
            "nato_defense_spending_trend": "stable",
            "auto_health_claims_inflation": "low",
            "global_tech_liquidity_environment": "neutral",
            "tr_corporate_capex_trend": "stable"
        })
        
        return macros

    async def get_macro_context(self) -> Dict[str, Any]:
        """
        Orkestratörün Kancalar (Hooks) için çağıracağı ana fonksiyon.
        Canlı küresel veriler ile yerel rejim verilerini harmanlayıp tek bir sözlük döner.
        """
        logger.info(f"Makro Bağlam (Macro Context) oluşturuluyor... Rejim: {self.current_regime.value}")
        
        # 1. Canlı Verileri Çek
        live_globals = await self._fetch_live_global_macros()
        
        # 2. Yerel Verileri Üret
        local_macros = self._generate_local_macros_by_regime()
        
        # 3. Harmanla ve Mantıksal Dönüşümleri Yap (Raw Data -> Trend Sinyalleri)
        context = {**local_macros}
        
        # Parite
        if live_globals.get("eur_usd"):
            context["eur_usd_parity"] = live_globals["eur_usd"]
            
        # Altın Trendi (Basit bir varsayım: 2300 üzeri Bull Market kabul edelim)
        gold_price = live_globals.get("gold")
        if gold_price:
            context["global_gold_price_trend"] = "bull_market" if gold_price > 2300 else "stable"
            
        # Brent Trendi (90 Dolar üzeri Spike sayalım)
        brent_price = live_globals.get("brent")
        if brent_price:
            context["brent_crude_price_trend"] = "severe_spike" if brent_price > 90 else "stable"
            
        logger.debug(f"Makro Context başarıyla harmanlandı. Toplam Sinyal: {len(context)}")
        return context