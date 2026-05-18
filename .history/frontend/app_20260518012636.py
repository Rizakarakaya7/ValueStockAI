import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd

# ==========================================
# 1. SAYFA YAPILANDIRMASI (PROFESYONEL GÖRÜNÜM)
# ==========================================
st.set_page_config(
    page_title="FinansAjanı | AI Destekli Değerleme Terminali",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Koyu tema için özel CSS yaması (Okunabilirlik Düzeltildi)
st.markdown("""
    <style>
    .stMetric {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Metrik yazılarının her temada beyaz/açık kalmasını garanti eder */
    div[data-testid="stMetricValue"] { color: #FFFFFF !important; }
    div[data-testid="stMetricLabel"] { color: #A0AEC0 !important; }
    div[data-testid="stMetricDelta"] { font-weight: bold; }
    
    /* Rapor Kutusu Düzeltmeleri */
    .report-box {
        background-color: #1E1E1E; /* Daha soft bir karanlık arka plan */
        color: #F8F9FA !important; /* YAZI RENGİ TAM BEYAZ/AÇIK GRİ YAPILDI */
        padding: 25px;
        border-radius: 10px;
        border-left: 5px solid #FF4B4B;
        font-size: 16px; /* Yazı boyutu büyütüldü */
        line-height: 1.6; /* Satır aralığı ferahlatıldı */
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Markdown içindeki başlıkların (H1, H2, vb.) rengi */
    .report-box h1, .report-box h2, .report-box h3 {
        color: #FFFFFF !important; 
        margin-bottom: 15px;
    }
    
    /* Listelerin daha okunaklı olması için */
    .report-box ul {
        margin-left: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# FastAPI Arka Plan Adresi
API_URL = "http://127.0.0.1:8000/api/v1/valuate/"

# ==========================================
# 2. YAN MENÜ (SIDEBAR) CONTROLS
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2633/2633320.png", width=100) # Temsili Logo
    st.title("FinansAjanı Terminali")
    st.markdown("Quant Motoru & Gemini AI")
    st.divider()
    
    ticker_input = st.text_input("Hisse Kodu Giriniz", "FROTO").upper()
    
    # Butona basıldığında analiz başlar
    run_button = st.button("🚀 Analizi Başlat", type="primary", use_container_width=True)
    
    st.divider()
    st.caption("Sistem Durumu: 🟢 API Aktif")

# ==========================================
# 3. ANA EKRAN VE API ÇAĞRISI
# ==========================================
if run_button:
    if not ticker_input:
        st.warning("Lütfen geçerli bir hisse kodu giriniz.")
    else:
        # Spinner ile kullanıcıya sürecin işlediğini gösteriyoruz
        with st.spinner(f"🤖 {ticker_input} için veriler toplanıyor, DCF modeli çalıştırılıyor ve Yapay Zeka raporu yazılıyor (Ort: 6-10 sn)..."):
            try:
                response = requests.get(f"{API_URL}{ticker_input}", timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    quant = data["quant_payload"]
                    report_markdown = data["analyst_report"]
                    
                    # Verileri Çıkarma
                    curr_price = quant.get("current_price") or 0.0
                    target_price = quant.get("intrinsic_price_per_share") or 0.0
                    upside = quant.get("upside_potential_pct") or 0.0
                    
                    meta = quant.get("valuation_metadata", {})
                    wacc = meta.get("model_report", {}).get("applied_wacc", 0.0) * 100
                    sector = quant.get("sector", "Bilinmiyor")
                    model_used = meta.get("model_report", {}).get("model_used", "Bilinmiyor")

                    # ==========================================
                    # 4. METRİK KARTLARI (KPIs)
                    # ==========================================
                    st.markdown(f"### {ticker_input} Finansal Check-up Özeti")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    col1.metric(label="Anlık Piyasa Fiyatı", value=f"₺ {curr_price:,.2f}" if curr_price > 0 else "Veri Yok")
                    col2.metric(label="Hesaplanan Hedef Fiyat", value=f"₺ {target_price:,.2f}")
                    
                    # Renge duyarlı ok gösterimi (Delta)
                    col3.metric(label="Getiri Potansiyeli", value=f"% {upside:,.2f}", delta=f"{upside:,.2f}%", delta_color="normal" if upside > 0 else "inverse")
                    
                    col4.metric(label="Model & İskonto", value=f"% {wacc:,.2f} WACC", delta=model_used, delta_color="off")
                    
                    st.divider()

                    # ==========================================
                    # 5. GÖRSELLEŞTİRME VE YAPAY ZEKA RAPORU
                    # ==========================================
                    left_col, right_col = st.columns([1, 1.5])
                    
                    with left_col:
                        st.subheader("📊 Potansiyel Kadranı")
                        # Plotly Gauge (Hız Göstergesi) Çizelgesi
                        fig = go.Figure(go.Indicator(
                            mode = "gauge+number+delta",
                            value = target_price,
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': "Adil Değer Hedefi (TL)", 'font': {'size': 24}},
                            delta = {'reference': curr_price, 'increasing': {'color': "green"}},
                            gauge = {
                                'axis': {'range': [None, max(curr_price, target_price) * 1.5], 'tickwidth': 1, 'tickcolor': "darkblue"},
                                'bar': {'color': "darkblue"},
                                'bgcolor': "white",
                                'borderwidth': 2,
                                'bordercolor': "gray",
                                'steps': [
                                    {'range': [0, curr_price], 'color': '#ff4b4b'}, # Ucuz Bölge
                                    {'range': [curr_price, max(curr_price, target_price) * 1.5], 'color': '#00cc96'} # Primli Bölge
                                ],
                                'threshold': {
                                    'line': {'color': "black", 'width': 4},
                                    'thickness': 0.75,
                                    'value': target_price
                                }
                            }
                        ))
                        fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Denetim İzi (Özet)
                        with st.expander("🔍 Değerleme Denetim İzi (Audit Trace)"):
                            st.json(meta.get("audit_trace", {}))

                    with right_col:
                        st.subheader("🤖 Hedge Fund Analist Raporu")
                        # Şık bir kutu içinde Markdown Raporu
                        st.markdown(f'<div class="report-box">{report_markdown}</div>', unsafe_allow_html=True)
                
                else:
                    st.error(f"API Hatası (Kod: {response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("Bağlantı Hatası: Arka plan API sunucusuna (FastAPI) ulaşılamıyor. 'uvicorn main:app --reload' komutunun backend tarafında çalıştığından emin olun.")
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
else:
    # Karşılama Ekranı
    st.info("👈 Analize başlamak için sol menüden bir hisse kodu girin ve 'Analizi Başlat' butonuna tıklayın.")