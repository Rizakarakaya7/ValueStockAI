import os
import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd

# ==========================================
# 1. SAYFA YAPILANDIRMASI VE CSS DÜZELTMELERİ
# ==========================================
st.set_page_config(
    page_title="FinansAjanı | AI Destekli Değerleme Terminali",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tema bağımsız kesin görünüm için CSS enjeksiyonu
st.markdown("""
    <style>
    /* Her bir metrik kartının arka planını kesin olarak koyu griye sabitler */
    div[data-testid="stMetric"] {
        background-color: #1E1E1E !important;
        padding: 20px !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.4) !important;
        border: 1px solid #2D3748 !important;
    }
    
    /* Metrik içindeki değer (rakam) rengini her zaman beyaz yapar */
    div[data-testid="stMetricValue"] > div {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    
    /* Metrik başlıklarının (etiketlerinin) rengini açık gri yapar */
    div[data-testid="stMetricLabel"] > div {
        color: #A0AEC0 !important;
        font-size: 14px !important;
    }
    
    /* Değişim/Delta (Oklar ve yüzdeler) için kalınlık ayarı */
    div[data-testid="stMetricDelta"] > div {
        font-weight: 600 !important;
    }
    
    /* Yapay Zeka Rapor Kutusu Ayarları */
    .report-box {
        background-color: #1E1E1E;
        color: #F8F9FA !important;
        padding: 30px;
        border-radius: 10px;
        border-left: 5px solid #FF4B4B;
        font-size: 16px;
        line-height: 1.7;
        box-shadow: 0 4px 6px rgba(0,0,0,0.4);
        border: 1px solid #2D3748;
    }
    
    /* Rapor içindeki Markdown başlıklarının renk optimizasyonu */
    .report-box h1, .report-box h2, .report-box h3 {
        color: #FFFFFF !important; 
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
# DİNAMİK API BAĞLANTISI (DOCKER / LOCALHOST UYUMU)
# ==========================================
# Ortam değişkeni (Docker) varsa onu alır, yoksa (Lokal) localhost'u kullanır.
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
API_URL = f"{BASE_URL}/api/v1/valuate/"

# ==========================================
# 2. YAN MENÜ (SIDEBAR) KONTROLLERİ
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2633/2633320.png", width=100)
    st.title("FinansAjanı Terminali")
    st.markdown("Quant Motoru & Gemini AI")
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
        with st.spinner(f"🤖 {ticker_input} için veriler toplanıyor, DCF modeli çalıştırılıyor ve Yapay Zeka raporu yazılıyor..."):
            try:
                response = requests.get(f"{API_URL}{ticker_input}", timeout=45)
                
                if response.status_code == 200:
                    data = response.json()
                    quant = data["quant_payload"]
                    report_markdown = data["analyst_report"]
                    
                    # Verilerin Güvenli Çıkarılması
                    curr_price = quant.get("current_price") or 0.0
                    target_price = quant.get("intrinsic_price_per_share") or 0.0
                    upside = quant.get("upside_potential_pct") or 0.0
                    
                    meta = quant.get("valuation_metadata", {})
                    wacc = meta.get("model_report", {}).get("applied_wacc", 0.0) * 100
                    model_used = meta.get("model_report", {}).get("model_used", "Bilinmiyor")

                    # ==========================================
                    # 4. SKOR KARTLARI (METRICS GRID)
                    # ==========================================
                    st.markdown(f"### {ticker_input} Finansal Check-up Özeti")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    col1.metric(
                        label="Anlık Piyasa Fiyatı", 
                        value=f"₺ {curr_price:,.2f}" if curr_price > 0 else "Veri Yok"
                    )
                    col2.metric(
                        label="Hesaplanan Hedef Fiyat", 
                        value=f"₺ {target_price:,.2f}" if target_price > 0 else "Hesaplanamadı"
                    )
                    col3.metric(
                        label="Getiri Potansiyeli", 
                        value=f"% {upside:,.2f}", 
                        delta=f"{upside:,.2f}%" if upside != 0 else None,
                        delta_color="normal" if upside > 0 else "inverse"
                    )
                    col4.metric(
                        label="Uygulanan Sermaye Maliyeti", 
                        value=f"% {wacc:,.1f} WACC", 
                        delta=model_used.replace("_", " "), 
                        delta_color="off"
                    )
                    
                    st.divider()

                    # ==========================================
                    # 5. GÖRSEL GRAFİK VE ANALİST RAPORU
                    # ==========================================
                    left_col, right_col = st.columns([1, 1.5])
                    
                    with left_col:
                        st.subheader("📊 Potansiyel Kadranı")
                        
                        # Kadran Grafiği (Gauge Chart) Sınır Tayini
                        max_range = max(curr_price, target_price) * 1.5 if max(curr_price, target_price) > 0 else 1000
                        
                        fig = go.Figure(go.Indicator(
                            mode="gauge+number+delta",
                            value=target_price,
                            domain={'x': [0, 1], 'y': [0, 1]},
                            title={'text': "Hisse Başı Adil Değer", 'font': {'size': 20, 'color': '#FFFFFF' if st.get_option("theme.base") == "dark" else '#000000'}},
                            delta={'reference': curr_price, 'increasing': {'color': "green"}},
                            gauge={
                                'axis': {'range': [0, max_range], 'tickwidth': 1},
                                'bar': {'color': "#FF4B4B"},
                                'steps': [
                                    {'range': [0, curr_price], 'color': '#2D3748'},
                                    {'range': [curr_price, max_range], 'color': '#1A202C'}
                                ],
                                'threshold': {
                                    'line': {'color': "gold", 'width': 4},
                                    'thickness': 0.8,
                                    'value': target_price
                                }
                            }
                        ))
                        fig.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        with st.expander("🔍 Değerleme Denetim İzi (Audit Trace)"):
                            st.json(meta.get("audit_trace", {}))
                            st.json(meta.get("balance_sheet_snapshot", {}))

                    with right_col:
                        st.subheader("🤖 Hedge Fund Analist Raporu")
                        st.markdown(f'<div class="report-box">{report_markdown}</div>', unsafe_allow_html=True)
                
                else:
                    st.error(f"API Hatası (Kod: {response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("Bağlantı Hatası: Arka plan API sunucusuna (FastAPI) ulaşılamıyor. 'uvicorn main:app --reload' komutunun çalıştığından emin olun.")
            except Exception as e:
                st.error(f"Beklenmeyen bir hata oluştu: {str(e)}")
else:
    st.info("👈 Analize başlamak için sol menüden bir hisse kodu girin (Örn: FROTO, TOASO) ve 'Analizi Başlat' butonuna tıklayın.")