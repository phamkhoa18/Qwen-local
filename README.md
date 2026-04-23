# VKS Legal AI Platform

Chatbot AI Phap Luat cho Vien Kiem Sat Nhan Dan Viet Nam.

## Features

- **Legal RAG** - Retrieval-Augmented Generation using `vietlegal-harrier-0.6b` + 518K Vietnamese legal documents
- **Qwen3-30B-A3B** - Local LLM with thinking mode for complex legal reasoning
- **Chat Playground** - Premium web interface for prosecutors
- **API Keys** - Create & manage API keys
- **OpenAI-Compatible API** - `/v1/chat/completions` with streaming
- **Legal Citations** - Automatic source references with similarity scores

## Architecture

```
User Question --> vietlegal-harrier-0.6b (Embedding) --> FAISS Search --> Top-K Legal Passages
                                                                              |
                                                                              v
                                                              Qwen3-30B-A3B (LLM) --> Answer with Citations
```

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Qwen3-30B-A3B via Ollama |
| Embedding | vietlegal-harrier-0.6b (sentence-transformers) |
| Vector Store | FAISS |
| Backend | FastAPI + Motor (async MongoDB) |
| Database | MongoDB |
| Frontend | Vanilla HTML/CSS/JS |
| Dataset | th1nhng0/vietnamese-legal-documents (518K docs) |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start MongoDB
mongod --dbpath ./data/db

# 3. Start Ollama + pull model
ollama serve
ollama pull qwen3:30b-a3b

# 4. Run API server
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 5. Open browser: http://localhost:8000
# Login: admin / vks@2024
```

## Cloud Deployment (Vast.ai)

```bash
chmod +x setup_cloud.sh
./setup_cloud.sh
./start.sh
```

## API Usage

```python
import openai

client = openai.OpenAI(
    base_url="http://YOUR_SERVER:8000/v1",
    api_key="vks-your-api-key"
)

response = client.chat.completions.create(
    model="qwen3:30b-a3b",
    messages=[{"role": "user", "content": "Phan tich Dieu 173 BLHS 2015"}]
)
print(response.choices[0].message.content)
```
