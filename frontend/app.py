import os
import streamlit as st
import requests
import pandas as pd

# ==========================================
# 1. SAYFA YAPILANDIRMASI VE CSS DÜZELTMELERİ
# ==========================================
st.set_page_config(
    page_title="ValueStockAI | AI Destekli Değerleme Terminali",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Logo dosyasının dinamik yolunu buluyoruz (frontend klasörü içi)
LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")

# CSS Enjeksiyonu
st.markdown("""
    <style>
    /* YENİ: Metrik kartları (Fiyat Kutuları) - Açık Mavi Tema ve KESİN EŞİT BOYUT */
    div[data-testid="stMetric"] {
        background-color: #E3F2FD !important; /* Ferah açık mavi arka plan */
        padding: 20px !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        border: 1px solid #90CAF9 !important; /* İnce mavi/lacivert çerçeve */
        height: 140px !important; /* Bütün kutuların yüksekliğini eşitler */
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important; /* İçeriği dikey eksende kusursuz ortalar */
    }
    
    /* Açık mavi arka planda sayıların (Fiyatların) okunaklı olması için koyu lacivert/siyah renk */
    div[data-testid="stMetricValue"] > div {
        color: #1A202C !important; 
        font-weight: 800 !important;
    }
    
    /* Başlıkların rengi (Koyu mavi) */
    div[data-testid="stMetricLabel"] > div {
        color: #1565C0 !important; 
        font-size: 15px !important;
        font-weight: 600 !important;
    }
    
    /* Yüzdelik değişimlerin (Okların) kalınlığı */
    div[data-testid="stMetricDelta"] > div {
        font-weight: 700 !important;
    }
    
    /* Yapay Zeka Rapor Kutusu Ayarları (Göz yormayan açık renk) */
    .report-box {
        background-color: #F8F9FA; 
        color: #2D3748 !important; 
        padding: 30px;
        border-radius: 10px;
        border-left: 5px solid #FF4B4B;
        font-size: 16px;
        line-height: 1.7;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #E2E8F0;
    }
    
    .report-box h1, .report-box h2, .report-box h3 {
        color: #1A202C !important; 
        margin-top: 20px;
        margin-bottom: 15px;
        font-weight: 600;
    }
    
    .report-box ul {
        margin-left: 25px;
        margin-bottom: 15px;
    }
    
    .report-box li {
        margin-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# DİNAMİK API BAĞLANTISI 
# ==========================================
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
API_URL = f"{BASE_URL}/api/v1/valuate/"

# ==========================================
# 2. YAN MENÜ (SIDEBAR) KONTROLLERİ
# ==========================================
with st.sidebar:
    st.write("<br>", unsafe_allow_html=True)
    # Yan menüdeki logoyu ortalamak ve büyütmek için kolon hilesi
    sidebar_logo_col1, sidebar_logo_col2, sidebar_logo_col3 = st.columns([1, 4, 1])
    with sidebar_logo_col2:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_column_width=True)
        else:
            st.warning("Logo bulunamadı.")
        
    st.title("ValueStockAI Terminali")
    st.markdown("Quant Motoru & Yatırım Komitesi")
    st.divider()
    
    ticker_input = st.text_input("Hisse Kodu Giriniz", "FROTO").upper().strip()
    run_button = st.button("🚀 Analizi Başlat", type="primary", use_container_width=True)
    
    st.divider()
    st.caption("Sistem Durumu: 🟢 API Aktif")

# ==========================================
# 3. ANA EKRAN VE RUN TIME TETİKLEYİCİSİ
# ==========================================
if run_button:
    if not ticker_input:
        st.warning("Lütfen geçerli bir hisse kodu giriniz.")
    else:
        with st.spinner(f"🤖 {ticker_input} için komite toplanıyor, veriler sentezleniyor..."):
            try:
                response = requests.get(f"{API_URL}{ticker_input}", timeout=45)
                
                if response.status_code == 200:
                    data = response.json()
                    quant = data["quant_payload"]
                    report_markdown = data["analyst_report"]
                    
                    curr_price = quant.get("current_price") or 0.0
                    target_price = quant.get("intrinsic_price_per_share") or 0.0
                    upside = quant.get("upside_potential_pct") or 0.0

                    # Başlığı tam ortaya alıyoruz
                    st.markdown(f"<h3 style='text-align: center;'>{ticker_input} Finansal Özeti</h3>", unsafe_allow_html=True)
                    
                    st.write("<br><br><br>", unsafe_allow_html=True)
                    st.markdown(
                        "<p style='text-align: center; color: #718096; font-size: 13px; font-style: italic;'>"
                        "⚠️ <b>Yasal Uyarı:</b> Burada yer alan yatırım bilgi, yorum ve tavsiyeleri yatırım danışmanlığı kapsamında değildir. "
                        "Bu analizler yalnızca bilgilendirme amaçlı olup, herhangi bir yatırım enstrümanı için alım-satım önerisi teşkil etmez."
                        "</p>",
                        unsafe_allow_html=True
                    )
                     
                    # ==========================================
                    # LOGOYU SONUÇLARIN TEPESİNE ORTALAMA (Bir Tık Büyütüldü)
                    # ==========================================
                    logo_col1, logo_col2, logo_col3 = st.columns([1.8, 1.4, 1.8]) 
                    with logo_col2:
                        if os.path.exists(LOGO_PATH):
                            st.image(LOGO_PATH, use_column_width=True)
                    
                    st.write("<br>", unsafe_allow_html=True) 

                    # ==========================================
                    # 4. SKOR KARTLARI (Eşit ve Açık Mavi 3 Sütun)
                    # ==========================================
                    col1, col2, col3 = st.columns(3)
                    
                    col1.metric(
                        label="Anlık Piyasa Fiyatı", 
                        value=f"₺ {curr_price:,.2f}" if curr_price > 0 else "Veri Yok"
                    )
                    col2.metric(
                        label="Adil Değer", 
                        value=f"₺ {target_price:,.2f}" if target_price > 0 else "Hesaplanamadı"
                    )
                    col3.metric(
                        label="Getiri Potansiyeli", 
                        value=f"% {upside:,.2f}", 
                        delta=f"{upside:,.2f}%" if upside != 0 else None,
                        delta_color="normal" if upside > 0 else "inverse"
                    )
                    
                    st.divider()

                    # ==========================================
                    # 5. AJAN RAPORU (Tam Genişlik)
                    # ==========================================
                    st.markdown(f'<div class="report-box">{report_markdown}</div>', unsafe_allow_html=True)
                
                else:
                    st.error(f"API Hatası (Kod: {response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("Bağlantı Hatası: Arka plan API sunucusuna ulaşılamıyor.")
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
else:
    # ==========================================
    # ANA EKRAN (KARŞILAMA): Daha Da Büyütülmüş ve Ortalanmış Logo
    # ==========================================
    st.write("<br><br>", unsafe_allow_html=True) 
    
    col1, col2, col3 = st.columns([0.5, 3, 0.5]) # Yan sütunlar daraltılarak orta logo alanı genişletildi (Daha büyük görünüm)
    with col2:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_column_width=True)
            
    st.markdown("<h3 style='text-align: center; color: #A0AEC0; margin-top: 20px;'>Analize başlamak için sol menüden bir hisse kodu girin.</h3>", unsafe_allow_html=True)