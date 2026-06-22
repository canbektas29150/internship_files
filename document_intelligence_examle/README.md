# Document Intelligence with Ollama Cloud MiniMax M3

Bu proje, finansal araştırma agent'ından farklı olarak **akıllı doküman işleme** üzerine kurulmuş küçük ama genişletilebilir bir demodur. OpenAI API veya OpenAI Agents SDK kullanmaz. Model çağrısı Ollama'nın native `/api/chat` endpoint'i üzerinden **MiniMax M3 Cloud** modeline gider.

## Ne yapar?

Bir TXT/PDF/image belgesinden metin çıkarır ve MiniMax M3 ile şu bilgileri üretir:

- belge türü
- firma / taraf bilgileri
- belge numarası
- tarih ve vade tarihi
- vergi numarası
- toplam tutar
- madde başlıkları
- riskli hükümler
- kısa özet
- önerilen aksiyonlar
- eksik alanlar
- kaynak kanıtları
- verification skoru
- insan incelemesi gerekiyor mu?

## Mimari

```text
Input document
↓
Document Reader / OCR Layer
↓
Extraction Agent
↓
Risk Analysis Agent
↓
Verifier Agent
↓
JSON + Excel Report
↓
Streamlit Dashboard
```

Buradaki agent'lar framework bağımlılığı olmayan Python class'larıdır. Ama sistem agentic pipeline mantığını gösterir: her aşama ayrı sorumluluk alır ve final çıktıyı bir sonraki aşamaya taşır.

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

macOS / Linux için:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Kullanım 1: Local Ollama üzerinden Cloud model

Bu yöntem en rahatıdır. Bilgisayarda Ollama çalışır, model cloud'da çalışır.

```bash
ollama signin
ollama run minimax-m3:cloud
python main.py --input sample_docs/sample_invoice.txt --out outputs
```

Sözleşme örneği:

```bash
python main.py --input sample_docs/sample_contract.txt --out outputs
```

## Kullanım 2: Direct Ollama Cloud API

```bash
set OLLAMA_API_KEY=your_api_key
python main.py --direct-cloud --model minimax-m3 --input sample_docs/sample_invoice.txt
```

PowerShell:

```powershell
$env:OLLAMA_API_KEY="your_api_key"
python main.py --direct-cloud --model minimax-m3 --input sample_docs/sample_invoice.txt
```

Eğer model adı bulunamazsa şunu dene:

```bash
python main.py --direct-cloud --model minimax-m3:cloud --input sample_docs/sample_invoice.txt
```

## Dashboard

```bash
streamlit run app.py
```

Dashboard'dan PDF/TXT/image yükleyip sonucu JSON ve Excel olarak indirebilirsin.

## Çıktılar

Varsayılan olarak `outputs/` klasörüne iki dosya yazar:

```text
analysis.json
analysis.xlsx
```

Excel içinde şu sheet'ler bulunur:

```text
summary
parties
risks
actions
missing_fields
evidence
unsupported
inconsistent
```

## OCR notu

- TXT ve normal text-based PDF dosyaları doğrudan çalışır.
- Image OCR için `pytesseract` ve işletim sisteminde Tesseract kurulu olmalıdır.
- Taranmış PDF'lerde `pypdf` az metin çıkarabilir. Bu durumda PDF sayfalarını image'a çevirip OCR ile çalıştırmak daha doğru olur.

## Staj raporuna yazılabilecek kısa açıklama

Bu projede doküman tabanlı bilgi çıkarımı için MiniMax M3 Cloud kullanan bir Document Intelligence pipeline geliştirildi. Sistem; belge metnini çıkarma, belge türünü anlama, kritik alanları JSON formatında üretme, riskli hükümleri işaretleme ve üretilen çıktıyı doğrulama adımlarından oluşmaktadır. Sonuçlar hem JSON hem Excel formatında dışa aktarılmış, ayrıca Streamlit arayüzü ile kullanıcıya görsel bir inceleme ekranı sunulmuştur.

## Geliştirilebilir taraflar

- Taranmış PDF'ler için sayfa bazlı OCR ekleme
- Tablo ve satır kalemi çıkarımı
- İnsan onay ekranı
- RAG ile kaynak maddeye tıklama
- Çoklu belge karşılaştırma
- KVKK / sözleşme risk checklist'i
- İş akışı logları ve agent trace dashboard
