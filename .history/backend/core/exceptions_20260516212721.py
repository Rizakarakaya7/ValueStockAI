"""
Sistemin merkezi hata yönetimi (Centralized Exception Handling) modülü.
Buradaki özel hatalar, hatanın nerede (Veri çekerken mi, hesaplarken mi) 
patladığını Orkestratör'ün anlamasını sağlar.
"""

class ValueStockBaseError(Exception):
    """Tüm ValueStockAI hatalarının atası."""
    pass

class ValuationPipelineError(ValueStockBaseError):
    """
    Değerleme boru hattı uçtan uca (End-to-End) çalışırken bir noktada 
    kırılırsa fırlatılan ana hatadır.
    """
    pass

class DataExtractionError(ValueStockBaseError):
    """
    İş Yatırım veya Yahoo Finance'ten veri çekilirken API çökerse, 
    rate-limit yenirse veya zaman aşımı (Timeout) olursa fırlatılır.
    """
    pass

# İleride eklenebilecek diğer hatalar için yer tutucular
class NormalizationError(ValueStockBaseError):
    """Ham veri standart Bilanço/Gelir Tablosu formatına çevrilemezse fırlatılır."""
    pass

class DispatcherError(ValueStockBaseError):
    """Tanımsız bir sektör için Model veya Hook talep edilirse fırlatılır."""
    pass