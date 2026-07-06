# SEO RAG backend

FastAPI service for SEO content generation for a digital media platform, with **RAG** over crawled site content. Portfolio / pet-project demo of a full content generation pipeline.

## Stack

- **FastAPI** — HTTP API
- **LangChain** — chains / RAG
- **Ollama** — local **Qwen** chat + embeddings (configure model names via env)
- **Qdrant** — vector store
- **Playwright + Trafilatura** — website ingestion (rendered HTML → clean text)
- (optional) **FireCrawl** — legacy ingestion helpers (deprecated; not on primary ingestion path)

## Quick start

Requires **Python 3.9+** (3.11+ recommended).

```bash
cd /path/to/seo_generation_text
python -m venv .venv && source .venv/bin/activate
pip install -e .
```
//if 'internal error: 500', then do this command and check whether docker runs or not
// ollama pull qwen2.5:7b-instruct

Ensure **Ollama** is running with your Qwen instruct model and an embedding model (e.g. `nomic-embed-text`), and **Qdrant** is reachable.

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5:0.5b-instruct
export OLLAMA_EMBED_MODEL=nomic-embed-text
export QDRANT_URL=http://127.0.0.1:6333
export QDRANT_COLLECTION=seo_crawl
# Playwright ingestion config (primary ingestion path)
export PLAYWRIGHT_HEADLESS=true
export PLAYWRIGHT_NAV_TIMEOUT_MS=30000
# export PLAYWRIGHT_USER_AGENT="Mozilla/5.0 ..."
# One-time: python -m playwright install chromium


# Optional: pipe-separated AI fluff phrases to ban in `/generation/content` validation
# export BANNED_AI_PHRASES="as an ai|delve into|game-changer"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Liveness |
| GET | `/readyz` | Readiness (Ollama + Qdrant) |
| POST | `/ingestion/firecrawl` | Ingest crawled pages into Qdrant |
| POST | `/ingestion/crawl` | **Standalone pipeline:** Playwright crawl (same-domain) → Trafilatura → chunk → embed → Qdrant (`source_type`, `domain`, `language` on each chunk) |
| POST | `/retrieval/query` | Top-k RAG snippets (optional ``source_scope``: ``source_type``, ``domain``, ``language``, ``site_id``) |
| POST | `/generation/block` | Generate `use_cases_block` or `online_vs_desktop` (legacy shape) |
| POST | `/generation/content` | **Pipeline:** page/block types, LSI, product features, metadata-filtered RAG, validation report, rewrite |

## Project layout

- `app/routers/` — thin HTTP layer
- `app/services/` — ingestion, **crawl_ingestion** (standalone site crawl pipeline), retrieval, generation, validation, rewrite
- `app/agents/` — LangChain RAG / generation wiring
- `app/integrations/` — Ollama, Qdrant, FireCrawl clients
- `app/prompts/` — prompt templates (easy to extend)
- `app/services/content_pipeline/` — structured generation orchestration
## Docker (local run + DevOps handoff)

### Prerequisites
- Docker Desktop (or Docker Engine + Compose)
- Local Ollama running on the host (for Qwen)
  - macOS/Windows: `host.docker.internal` works from containers by default
  - Linux: you may need to replace `host.docker.internal` with your host IP or add an extra_hosts entry

### 1) Create your env file

```bash
cp .env.example .env
```

Edit `.env`:
- Set `QWEN_BASE_URL` to your Ollama host URL (default assumes local Ollama)
- Set `QWEN_MODEL_NAME` / `QWEN_EMBED_MODEL` to models you have pulled
### Optionally set `FIRECRAWL_API_KEY` if you will call ingestion endpoints

### 2) Build and start

```bash
docker compose up --build -d
```
# ollama pull nomic-embed-text
ollama list
### 3) Verify the API is running

```bash
# Liveness
curl -fsS "http://localhost:${APP_PORT:-8000}/healthz" && echo

# Readiness (checks Qdrant + Ollama reachability)
curl -fsS "http://localhost:${APP_PORT:-8000}/readyz" && echo
```

### 4) Stop the stack

```bash
docker compose down
```

### 5) Local validation (quick)

```bash
# Retrieval query with optional metadata filtering
curl -sS -X POST "http://localhost:${APP_PORT:-8000}/retrieval/query" \
  -H 'Content-Type: application/json' \
  -d '{"query":"video editor","source_scope":{"source_type":"platform","language":"en"},"top_k":3}'
```

### DevOps handoff notes
- **Secrets**: use a secret manager (Kubernetes secrets, Vault, SSM, etc.) for and `QDRANT_API_KEY`.
- **Qwen inference**: replace `QWEN_BASE_URL` (currently host-local Ollama) with a dedicated inference host/service.
- **Persistence**: Qdrant data is stored in the `qdrant_data` volume locally; use a PVC / managed disk in production.
- **Ingress / TLS**: put the API behind a reverse proxy/ingress (NGINX, Traefik, ALB, etc.).
- **Scaling**: scale API replicas independently from Qdrant; consider adding a worker service if you introduce background jobs.
- **Observability**: add metrics/tracing/log shipping (OTel, Prometheus, centralized logs). See TODOs in `Dockerfile`, `docker-compose.yml`, and `scripts/start.sh`.
