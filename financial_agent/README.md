# Financial Agent Real V4

Bu sürüm önceki hataları düzeltir ve artık sadece IBM için ezberlenmiş cevap vermez.

## Bu sürümdeki ana fark

Kullanıcı promptu şu sırayla işlenir:

```text
Prompt
↓
Company / ticker resolver
↓
Intent parser
↓
Research planner
↓
Finance data tool
↓
News / web search tool
↓
SEC / filings tool
↓
Score calculator
↓
Prompt-first answer writer
↓
Verifier
↓
Dashboard + trace timeline + local logs
```

Yani sistem artık promptu alıp:
- hangi şirketten bahsedildiğini bulur,
- kullanıcının ne sorduğunu sınıflandırır,
- buna göre araştırma sorguları üretir,
- yfinance / ddgs / SEC benzeri araçları çağırmaya çalışır,
- gelen veriye göre kısa cevap ve detaylı rapor üretir,
- her adımı `logs/trace_events.jsonl` içine yazar.

## Çalıştırma

```powershell
cd financial_agent_real_v4
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py
```

CLI:

```powershell
python app.py "Apple 3. çeyrekte nasıl bir şey yapar"
python app.py "IBM şirketinin yaptığı yatırımlar orta vadede nasıl etkiler?"
python app.py "NVIDIA için riskler neler?"
```

## Ollama / Minimax M3 kullanımı

OpenAI API kullanılmaz. LLM kullanmak istersen Ollama endpointi üzerinden çalışır:

```powershell
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:OLLAMA_MODEL="minimax-m3"
```

Ollama yoksa sistem deterministic fallback writer ile yine çalışır.

## Langfuse

Langfuse zorunlu değildir. Key yoksa sistem çökmez. Lokal log her zaman üretilir.

```powershell
$env:LANGFUSE_PUBLIC_KEY="pk-lf-..."
$env:LANGFUSE_SECRET_KEY="sk-lf-..."
$env:LANGFUSE_HOST="https://cloud.langfuse.com"
```

## Dosyalar

```text
app.py                # CLI
dashboard.py          # Streamlit dashboard
agent_flow.py         # Ana agent akışı
schemas.py            # dataclass modeller
resolver.py           # Prompt -> company/ticker
research_planner.py   # Prompt -> research plan
tools.py              # yfinance, ddgs, SEC araçları
scoring.py            # Investment/risk score hesapları
writer.py             # Kısa cevap + rapor üretimi
trace_logger.py       # Lokal trace + opsiyonel Langfuse
llm_client.py         # Opsiyonel Ollama writer
```

Bu çıktı yatırım tavsiyesi değildir; araştırma ve due diligence desteği amaçlıdır.

## V5 Trace / Explainability Layer

Bu sürümde dashboard yapısı korunarak tracing tarafı güçlendirildi. Ana sekmeler aynı kaldı; geliştirmeler özellikle **Trace Timeline** sekmesinin altında toplandı.

Trace sistemi artık her adım için şunları kaydeder:

- step adı ve hedefi
- kullanılan tool ve veri kaynağı
- source URL
- input / output özeti
- latency
- confidence
- decision log
- reasoning
- validation sonucu
- requested / returned / missing fields
- evidence mapping
- source quality
- final answer claim validation

Trace kayıtları yine lokal tutulur:

```text
logs/trace_events.jsonl
```

Dashboard içinde bakılacak yer:

```text
Trace Timeline
├── ana timeline tablosu
├── Decision Log
├── Tool Calls / Field Coverage
├── Evidence Mapping
├── Source Quality
├── Final Answer Validation
└── Downloads
```

Bu yapı sayesinde sadece final cevaba değil, cevaba giderken agent'ın hangi veriyi nereden çektiğine, hangi field'ların eksik olduğuna ve final cevaptaki claim'lerin ne kadar desteklendiğine bakılabilir.
