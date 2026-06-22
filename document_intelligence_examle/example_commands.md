# Example Commands

## Local Ollama route to MiniMax M3 Cloud

```bash
ollama signin
ollama run minimax-m3:cloud
python main.py --input sample_docs/sample_invoice.txt --out outputs
python main.py --input sample_docs/sample_contract.txt --out outputs
```

## Direct Ollama Cloud API

macOS / Linux:

```bash
export OLLAMA_API_KEY="your_api_key"
python main.py --direct-cloud --model minimax-m3 --input sample_docs/sample_invoice.txt
```

Windows PowerShell:

```powershell
$env:OLLAMA_API_KEY="your_api_key"
python main.py --direct-cloud --model minimax-m3 --input sample_docs/sample_invoice.txt
```

If the direct cloud model name is not found, try:

```bash
python main.py --direct-cloud --model minimax-m3:cloud --input sample_docs/sample_invoice.txt
```

## Streamlit dashboard

```bash
streamlit run app.py
```
