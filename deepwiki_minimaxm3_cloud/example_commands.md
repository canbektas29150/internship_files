# Example Commands

## Default: local Ollama host + MiniMax M3 cloud model

This assumes your Ollama app/CLI is signed in and can run `minimax-m3:cloud`.

```bash
python main.py --repo openai/codex --mode overview
python main.py --repo openai/codex --mode language
python main.py --repo openai/openai-agents-python --mode setup
python main.py --repo openai/openai-agents-python --mode architecture
python main.py --repo openai/openai-agents-python --mode risks
python main.py --repo openai/openai-agents-python --mode contribution
python main.py --repo openai/openai-agents-python --mode custom --question "Explain the MCP filesystem example simply."
```

## Direct Ollama Cloud API

```bash
export OLLAMA_API_KEY="your_ollama_cloud_api_key"
python main.py --direct-cloud --repo openai/codex --mode overview
```

On Windows PowerShell:

```powershell
$env:OLLAMA_API_KEY="your_ollama_cloud_api_key"
python main.py --direct-cloud --repo openai/codex --mode overview
```

## Debug DeepWiki only

This skips MiniMax M3 and prints only the raw DeepWiki MCP answer.

```bash
python main.py --repo openai/codex --mode overview --raw-mcp
```
