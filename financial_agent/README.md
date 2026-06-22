# Financial Agent Clean V2

Bu sürüm daha düzenli dashboard ve daha temiz summary output için sadeleştirildi.

## Yapı

```text
financial_agent_clean_v2/
├── README.md
├── requirements.txt
├── schemas.py      # Pydantic output modelleri
├── resolver.py     # Şirket adı -> ticker adayları
├── tools.py        # yfinance, DDGS, FRED, World Bank, SEC, export
├── agent_flow.py   # planner -> async research -> analyst tools -> writer -> verifier
├── dashboard.py    # Düzenli Streamlit UI
├── app.py          # CLI
└── __init__.py
```

## Ana akış

```text
User Prompt
↓
Ticker Resolver
↓
Confirmation if needed
↓
Planner
↓
Async data + research collection
↓
Specialist analyst summaries
↓
Writer summary
↓
Verifier
↓
Dashboard + JSON/Excel export
```

## Ne düzeltildi?

- Output artık tek parça dağınık metin değil.
- Ana ekranda kısa executive summary var.
- Score kartları ayrı.
- Key positives / key risks ayrı.
- Araştırılan sorgular ve kaynaklar ayrı gösteriliyor.
- SEC, macro, financials ve news verileri ayrı expander içinde.
- Trace timeline daha okunabilir.
- Dashboard hata ve confirmation akışı daha temiz.

## Kurulum

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PowerShell izin hatası olursa:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

## Dashboard

```powershell
python -m streamlit run dashboard.py
```

## CLI

```powershell
python app.py "apple"
python app.py "ford"
python app.py "AAPL risk analysis"
```

## Agents SDK

OpenAI Agents SDK varsa ve `OPENAI_API_KEY` tanımlıysa writer kısmı Agent/Runner/tool mantığını kullanabilir.
Yoksa aynı akış fallback modda deterministic olarak çalışır.

```powershell
$env:OPENAI_API_KEY="sk-..."
```

Bu çıktı yatırım tavsiyesi değildir; due diligence ve araştırma desteği için tasarlanmıştır.

## V3 düzeltmeleri

- `APPLE` yazınca artık raw ticker `APPLE` değil, `Apple Inc. / AAPL` adayı gelir.
- Dashboard içinde `st.json(...)` ile görünen çirkin JSON blokları kaldırıldı.
- Research Plan, Verifier, Trace ve Raw Data okunabilir metin/kart formatına çevrildi.
- Raw Data bölümü `Data Snapshot` olarak sadeleştirildi.
- Kaynaklar filtreleniyor; Outlook login, generic macro platform gibi alakasız sonuçlar ayıklanıyor.
- Search query'leri artık `Ticker: APPLE` gibi saçma stringler değil, doğru şirket adı + ticker ile oluşturulur.

## V4 dashboard düzenlemesi

- Üstteki teknik açıklama yazısı kaldırıldı.
- Dashboard başlığı profesyonel hale getirildi.
- JSON blokları ve raw teknik görüntü ana ekrandan kaldırıldı.
- Sonuçlar artık şu sırayla gösterilir: Company overview, score cards, executive summary, key findings, tabs.
- Research Plan, Sources, Verification, Data Snapshot ve Trace Timeline tab içinde temiz formatta gösterilir.
- Confirmation ekranı daha düzenli kart formatına alındı.

## V5 dashboard düzenlemesi

- Analyst Findings artık Research Plan'den önce gösterilir.
- Research Plan son taba taşındı; artık ana analizden önce teknik plan gösterilmiyor.
- Her analyst için Role + Assessment + Positive Signals + Risk/Limitation Signals alanları eklendi.
- Analyst açıklamaları daha anlaşılır hale getirildi: hangi veriye baktığı ve sonucu nasıl yorumladığı yazıyor.
- Macro, SEC ve News analyst bölümlerindeki kısa ama bağlamsız cümleler daha açıklayıcı hale getirildi.

## V6 dashboard düzenlemesi

- Streamlit toolbar / Deploy / menu görünümü CSS ve `.streamlit/config.toml` ile gizlendi.
- Uygulama varsayılan olarak koyu tema ve siyaha yakın arka planla açılır.
- Füme arka plan yerine daha net siyah profesyonel tema kullanıldı.
- Font ailesi Inter / Segoe UI / Roboto sırasıyla ayarlandı.
- Header, score cards, tabs, buttons ve input alanları daha kurumsal görünüme çekildi.
- Teknik ve gereksiz açıklama cümleleri arayüzden temizlendi.

## V7 dashboard düzenlemesi

- Arayüz tamamen siyah-beyaz yapıldı.
- Kırmızı vurgu, gradient ve renkli status tonları kaldırıldı.
- Sol bardaki örnek promptlar kaldırıldı.
- Streamlit toolbar / menu görünümü gizlenmeye devam ediyor.
- Varsayılan tema `.streamlit/config.toml` ile dark ve siyah arka plan olarak ayarlandı.
- Tasarım ikonlara bağlı kalmayacak şekilde sade metin/kart yapısına çekildi.

## V8 dashboard düzeltmesi

- Streamlit chat_message kaldırıldı; renkli avatar/kaymış yazı problemi çözüldü.
- Arayüz artık klasik chat balonları yerine tek sayfalık profesyonel araştırma paneli kullanır.
- Sidebar başlangıçta kapalıdır ve örnek promptlar tamamen kaldırıldı.
- Hata mesajları kırmızı/yellow Streamlit alert yerine siyah-beyaz özel panel olarak gösterilir.
- Ethereum ve Bitcoin alias desteği eklendi: Ethereum -> ETH-USD, Bitcoin -> BTC-USD.
- Layout kaymasını azaltmak için custom result card yapısı kullanıldı.
