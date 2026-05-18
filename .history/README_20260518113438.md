# 📈 ValueStockAI: Otonom BİST Değerleme ve Yapay Zeka Analiz Terminali

**ValueStockAI**, Borsa İstanbul (BİST) hisseleri için tasarlanmış, Wall Street standartlarında otonom bir kantitatif değerleme ve yapay zeka (LLM) analiz terminalidir. 

---

## 💡 Hikayemiz: Neden Bu Projeyi Geliştirdik?

Günümüzde bireysel yatırımcıların kullandığı finansal platformların ve hisse tarayıcılarının (screener) büyük bir çoğunluğu temel bir mantık hatası üzerine kuruludur: **Her şirkete aynı değerleme formülünü dayatmak.** Klasik sistemler, bir bankayı da, dev bir sanayi şirketini de, bir holdingi de aynı standart "İndirgenmiş Nakit Akışı (DCF)" veya basit "Fiyat/Kazanç (F/K)" çarpanlarıyla değerlemeye çalışır. Oysa gerçek finans dünyasında:
* Bankaların "FAVÖK (EBITDA)" veya "Serbest Nakit Akışı" diye bir kavramı yoktur; parayı satarlar.
* Holdingler ürettikleri nakit ile değil, iştiraklerinin toplam değeri (SOTP/NAV) ile ölçülür.
* Petrokimya gibi döngüsel (cyclical) şirketler, kriz dönemlerinde geçici olarak negatif nakit akışı üretirler ve klasik formüller bu şirketlere matematiksel olarak "-15 TL" gibi imkansız ve yanıltıcı hedef fiyatlar biçer.

**ValueStockAI işte bu yanlışı düzeltmek için doğdu.** Amacımız; şirketin faaliyet alanını otonom olarak tanıyan, bilançosunu yapılandıran, tam olarak o sektöre ait profesyonel finansal modeli koşturan ve salt matematiksel sonuçları **Google Gemini Yapay Zeka Ajanı** ile yorumlayarak bireysel yatırımcıya kurumsal bir "Hedge Fund Analist Raporu" sunan hatasız bir sistem inşa etmekti.

---

## 🌟 Öne Çıkan Özellikler (Key Features)

### 1. Akıllı Arketip Kapısı (Archetype Gate)
Sistem, her hissenin yapısal kimliğini (`Archetype`) tanır. Şirketin verilerini veri sağlayıcıdan çektikten sonra bir karar ağacına sokar. Bankalar, holdingler veya sigorta şirketleri için hatalı FAVÖK normalizasyonlarını pas geçerek onları doğrudan kendi özel ve izole değerleme modellerine yönlendirir.

### 2. Güçlü Zemin Koruması (Book Value Floor & Safeguards)
Sistemimiz, finansal krizlere karşı "Korumalı (Defansif)" bir mimariye sahiptir. Nakit akışı krizinde olan döngüsel şirketleri değerlerken nakit akışı sıfırın altına düşerse, sistemi patlatmak veya eksi değer üretmek yerine **"Zemin Koruması"** algoritmasını tetikler. Hedef fiyatı anında şirketin Net Aktif Değerine (Defter Değeri) kilitleyerek yatırımcıya güvenli bir taban fiyat sunar.

### 3. Yapay Zeka Destekli Yatırım Komitesi Raporu
ValueStockAI'ın ürettiği sayılar havada kalmaz. Çıkan tüm değerler (Tek seferlik kazanç düzeltmeleri, CapEx kesintileri, IFRS-16 kira borçları, net borç pozisyonları ve makro kancalar), arka planda asenkron çalışan LLM Ajanına (Gemini 2.5) gönderilir. Ajan, bu karmaşık verileri saniyeler içinde okuyarak son kullanıcı için anlaşılır, maddeler halinde bir yatırım raporu yazar.

### 4. "Fail-Gracefully" (Güvenli Çöküş) ve Yüksek Hata Toleransı
Sistem, eksik veri veya API limitlerine karşı inanılmaz dirençlidir:
* Finansal veri sağlayıcısında (YFinance) tablo eksikse, sahte rapor üretmek yerine işlemi anında durdurur.
* Google Gemini API'sinde kota aşımı (429) veya sunucu yoğunluğu (503) yaşanırsa sistem **çökmez**; otomatik olarak "Fallback (B Planı)" moduna geçerek sadece matematiksel motorun ürettiği net hedef fiyatları ekrana basar.

---

## 🏗️ Desteklenen Sektörler ve Otonom Değerleme Modelleri

ValueStockAI, BİST'teki şirketleri aşağıdaki sektörel modellere göre ayrıştırarak değerler:

| Sektör / Arketip | Uygulanan Değerleme Modeli | Metodoloji Açıklaması |
| :--- | :--- | :--- |
| **Sanayi & Üretim** | `İzole DCF (Compounder)` | İndirgenmiş serbest nakit akışları, bakım CapEx kesintileri ve IFRS-16 borç ayarlamaları. |
| **Petrokimya & Emtia** | `Döngüsel DCF (Cyclical)` | Emtia döngülerini baz alan, negatif nakit akışında "Defter Değeri Zemin Koruması" tetikleyen model. |
| **Enerji Dağıtım / Üretim** | `Regüle Getiri Modeli` | Sabit tarife garantileri (Regulated Yield) ve ağır yatırım harcamalarını (CapEx) filtreleyen altyapı DCF'i. |
| **Savunma Sanayii** | `Sipariş Yönlendirmeli DCF` | Şirketin elindeki iş bakiye gücüne (Backlog-Driven) dayalı nakit akışı projeksiyonu. |
| **Telekomünikasyon** | `Abonelik Tabanlı DCF` | Düzenli abonelik gelirlerini (Subscription) ve ağır telekom altyapı maliyetlerini baz alan model. |
| **Bankacılık** | `Artık Gelir (Residual Income)` | Klasik DCF işlemez. Özkaynak kârlılığı (ROE) ve tahvil faiz makası (Cost of Equity) üzerinden değerleme yapılır. |
| **Sigortacılık** | `Şamandıra (Float) & ROE` | Toplanan prim havuzunun yatırım getirisi ve defansif beta katsayısı kullanılarak hesaplanır. |
| **Holdingler & Yatırım** | `SOTP / NAV İskonto Modeli` | Şirketin doğrudan konsolide özkaynakları (Net Aktif Değer) alınır ve üzerine tarihsel "Holding İskontosu" uygulanır. |

---

## 🛠️ Teknoloji Yığını (Tech Stack)

* **Backend:** FastAPI, Python 3.12+, Uvicorn (RESTful API)
* **Veri İşleme (Data Pipeline):** Pandas, NumPy, YFinance
* **Yapay Zeka (LLM):** Google GenAI SDK (Gemini 2.5 Flash)
* **Asenkron İletişim:** `aiohttp`, `asyncio`, `httpx`
* **Frontend:** Streamlit (Interaktif Dashboard)
* **Altyapı ve Önbellek:** Docker, Docker Compose, Redis

---

## ⚙️ Kurulum ve Çalıştırma (Installation)

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyin. En stabil ve temiz yöntem **Docker** kullanmaktır.

### 1. Depoyu İndirin
```bash
git clone [https://github.com/KULLANICI_ADIN/ValueStockAI.git](https://github.com/Rizakarakaya7/ValueStockAI.git)
cd ValueStockAI