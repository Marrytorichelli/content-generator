# SEO RAG backend — local deployment guide

End-to-end guide to run the service on your laptop, seed the vector knowledge base with platform content, and hand the stack off to DevOps.

The stack has four moving parts:

1. **Ollama** with Qwen (chat) and an embedding model — runs on the host.
2. **Qdrant** vector database — runs in Docker.
3. **SEO RAG API** (FastAPI + LangChain) — runs in Docker and serves the UI at `/ui/`.
4. **Playwright + Trafilatura ingestion**, triggered from the API or from a CLI script.

You do NOT need cloud services for anything. Everything runs locally.

---

## 0. Prerequisites

- Docker Desktop (macOS/Windows) or Docker Engine + Compose plugin (Linux)
- `curl` available on the host (used for health checks)
- ~10 GB free disk for Ollama models and Qdrant data
- Network access for the first-time model/dependency download

On Linux, Docker containers cannot reach the host via `host.docker.internal` by default. Either:

- add `--add-host=host.docker.internal:host-gateway` (already respected by Compose if you set `extra_hosts`), or
- set `QWEN_BASE_URL=http://172.17.0.1:11434` (or your `docker0` IP).

---

## 1. Install and run Ollama with Qwen

Ollama is the local inference server for Qwen (chat) and for the embedding model.

### 1.1 Install Ollama

- macOS: download the installer from <https://ollama.com/download> and drag to Applications. Ollama auto-starts on login.
- Windows: installer from <https://ollama.com/download>.
- Linux:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  sudo systemctl enable --now ollama
  ```

Verify:

```bash
curl -fsS http://127.0.0.1:11434/api/tags
```

You should get `{"models":[]}` on a fresh install.

### 1.2 Pull the chat model (Qwen)

Good defaults for a laptop with 16 GB RAM:

```bash
ollama pull qwen2.5:7b-instruct
```

If you have a less powerful machine, `qwen2.5:3b-instruct` also works. On an Apple Silicon / RTX 4070+ class machine, `qwen2.5:14b-instruct` gives noticeably better copy.

### 1.3 Pull the embedding model

```bash
ollama pull nomic-embed-text
```

This produces 768-dim vectors, which matches the default `QDRANT_VECTOR_SIZE=768` in the project. If you swap embeddings, update `QDRANT_VECTOR_SIZE` to match the new dimension AND drop any existing Qdrant collection so it gets recreated at startup.

### 1.4 Smoke test

```bash
curl -fsS http://127.0.0.1:11434/api/generate \
  -d '{"model":"qwen2.5:7b-instruct","prompt":"Say hi in five words.","stream":false}'
```

You should get JSON with a `response` field.

---

## 2. Configure the project

```bash
cd seo_generation_text
cp .env.example .env
```

Edit `.env` — the only values you normally need to touch:

| Variable | Value | Notes |
|---|---|---|
| `QWEN_BASE_URL` | `http://host.docker.internal:11434` | macOS / Windows. On Linux use your host IP or see Prerequisites. |
| `QWEN_MODEL_NAME` | `qwen2.5:7b-instruct` | Must match `ollama pull` above. |
| `QWEN_EMBED_MODEL` | `nomic-embed-text` | Must match the embedding model you pulled. |
| `QDRANT_VECTOR_SIZE` | `768` | Must match the embedding model's dimension. |
| `APP_PORT` | `8000` | Host port where the API + UI are exposed. |
| `BANNED_AI_PHRASES` | (prefilled) | Pipe-separated list of phrases the validator will flag. |

`FIRECRAWL_API_KEY` is optional and only needed for legacy endpoints. Leave blank.

---

## 3. Start the stack

```bash
docker compose up --build -d
```

This brings up two containers: `seo-rag-qdrant` (data in the `qdrant_data` volume) and `seo-rag-api`. The API image also installs Playwright + Chromium, so the crawl endpoint works in-container.

Check everything is healthy:

```bash
curl -fsS "http://localhost:${APP_PORT:-8000}/healthz"   # → {"status":"ok"}
curl -fsS "http://localhost:${APP_PORT:-8000}/readyz"    # → {"status":"ready","checks":{"ollama":true,"qdrant":true}}
```

If `checks.ollama` is `false`, your container cannot reach Ollama — re-check `QWEN_BASE_URL` (see Prerequisites).

---

## 4. Open the web UI

Go to <http://localhost:8000/ui/> (or just <http://localhost:8000/> — it redirects).

The UI has three panels:

1. **Refresh knowledge** — enter a base URL, pick source type (`platform` / `competitor`) and hit *Crawl & index*. A preset button applies platform defaults (source type and language) without a hardcoded domain.
2. **Generation input** — page type, block type (`use_cases_block` or `online_vs_desktop`), prompt variant (`v1`, `v2`, `v3`), feature description, authoritative platform feature list, LSI (required), keywords (optional), retrieval scope, banned competitor brand list, and a *Use RAG* toggle.
3. **Result** — generated text, word count, validation pill (pass / issues), rewrite attempts, the retrieval evidence used to ground the text, and an activity log.

Everything is plain `fetch()` calls against the public FastAPI endpoints — no build step, no extra server.

---

## 5. Populate the vector database

### 5.1 Seed platform content (from the UI)

Panel "Refresh knowledge" → click *Preset: platform source*, enter your site base URL, then *Crawl & index*. Watch the activity log for a line like:

```
crawl ok: 142 chunks from 23 pages, errors=0
```

### 5.2 Seed platform content (from the CLI)

```bash
curl -sS -X POST "http://localhost:8000/ingestion/crawl" \
  -H 'Content-Type: application/json' \
  -d '{
    "source_type": "platform",
    "base_url":    "https://your-site.example/",
    "language":    "en",
    "max_pages":   40,
    "max_depth":   2
  }' | jq
```

Response fields: `chunks_upserted`, `pages_processed`, `domain`, `errors`. Increase `max_pages` / `max_depth` to cover deeper product pages.

### 5.3 Add a competitor site later

Same endpoint, just flip `source_type` to `competitor` so it lands in a separate metadata bucket and never leaks into platform-scoped retrieval:

```bash
curl -sS -X POST "http://localhost:8000/ingestion/crawl" \
  -H 'Content-Type: application/json' \
  -d '{
    "source_type": "competitor",
    "base_url":    "https://example-video-editor.com/",
    "language":    "en",
    "max_pages":   30,
    "max_depth":   1
  }' | jq
```

### 5.4 Verify retrieval

```bash
curl -sS -X POST "http://localhost:8000/retrieval/query" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "offline video editor for large files",
    "source_scope": {"source_type":"platform","language":"en"},
    "top_k": 3
  }' | jq '.sources[] | {score, url: .metadata.url, title: .metadata.title}'
```

You should see entries with `source_type: "platform"` and URLs from the crawled site.

---

## 6. Generate content

### 6.1 Full pipeline call (Online vs Desktop, variant v2)

```bash
curl -sS -X POST "http://localhost:8000/generation/content" \
  -H 'Content-Type: application/json' \
  -d '{
    "page_type": "landing",
    "content_block_type": "online_vs_desktop",
    "prompt_variant": "v2",
    "feature_description": "Desktop video editor — tool for trimming, joining, titles, effects, export.",
    "product_features": [
      "video trimming", "video merging", "multi-track timeline",
      "titles and captions", "effects and filters",
      "audio fade in/out", "chroma key", "video stabilization",
      "export in multiple formats", "export presets for YouTube, TikTok, Facebook"
    ],
    "lsi_keywords": [
      "offline video editor", "desktop video editor", "no internet needed",
      "local video editing", "full quality export", "large file support",
      "privacy-friendly editing"
    ],
    "keywords": ["video editor", "free trial video editor"],
    "language": "en",
    "source_scope": {"source_type":"platform","language":"en"},
    "competitor_brands": [],
    "use_rag": true,
    "top_k": 6
  }' | jq
```

The response includes `final_text`, `validation_report`, `retrieved_sources_summary`, and `rewrite_attempts`.

### 6.2 List available prompt variants

```bash
curl -sS http://localhost:8000/generation/prompts/online_vs_desktop/variants
# {"variants":["v1","v2","v3"]}
```

### 6.3 Prompt file locations

- `app/prompts/online_vs_desktop.txt` — v1 (balanced, practical)
- `app/prompts/online_vs_desktop_v2.txt` — v2 (scenario-led opener)
- `app/prompts/online_vs_desktop_v3.txt` — v3 (when-does-each-make-sense)
- `app/prompts/use_cases_block.txt` — v1 (clean four-case structure)
- `app/prompts/use_cases_block_v2.txt` — v2 (persona-driven)
- `app/prompts/use_cases_block_v3.txt` — v3 (outcome-first)
- `app/prompts/rewrite_pipeline.txt` — used by the rewrite agent when validation fails

All prompts use Python `str.format` placeholders (`{feature_description}`, `{product_features}`, `{lsi_keywords}`, `{keywords}`, etc.). To add a new variant, drop a new file `online_vs_desktop_v4.txt` into the folder — the `/generation/prompts/{block}/variants` endpoint picks it up automatically.

---

## 7. Validation contract

Every generated block is checked against:

- word count in `[GENERATION_MIN_WORDS, GENERATION_MAX_WORDS]` (200–250 by default),
- structure rules per block (`use_cases_block` needs four bold headings, `online_vs_desktop` must not be a bullet list),
- every LSI keyword appears at least once (case-insensitive),
- no banned AI filler phrase is present (pipe-separated list in `BANNED_AI_PHRASES`, prefilled with `best of the best`, `ultimate`, `fantastic`, `incredible`, `state-of-the-art`, etc.),
- no competitor brand from the request's `competitor_brands` list,
- product-feature grounding — strong capability claims must reference an entry from the authoritative `product_features`.

If any check fails, the rewrite agent runs up to `GENERATION_MAX_REWRITE_ATTEMPTS` times (default 2) with `app/prompts/rewrite_pipeline.txt`.

---

## 8. Common troubleshooting

| Symptom | Fix |
|---|---|
| `readyz` shows `ollama: false` from inside Docker | Linux: set `QWEN_BASE_URL=http://172.17.0.1:11434` or add `extra_hosts`. Verify with `docker compose exec api curl -fsS $QWEN_BASE_URL/api/tags`. |
| `readyz` shows `qdrant: false` | The API container is up before Qdrant is healthy. Wait 10 s and retry; Compose already declares `depends_on: qdrant: service_healthy`. |
| First `/generation/content` call is slow | Ollama has to load the model into RAM. Second call is fast. |
| `ingestion/crawl` returns `chunks_upserted: 0` | Playwright could not render the page. Check container logs: `docker compose logs -f api`. Try a simpler URL. |
| Embedding dimension mismatch | You changed the embed model. Drop the collection: `curl -X DELETE http://localhost:6333/collections/seo_crawl` and restart. |
| `Missing prompt file` error | Check filename matches `{block}.txt` or `{block}_<variant>.txt` inside `app/prompts/`. |
| `Prompt template missing placeholder` | You introduced a `{` in a prompt that isn't a real variable. Escape it as `{{`. |

---

## 9. Running without Docker (pure Python)

Only needed for deep debugging — prefer Docker for day-to-day use.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .
python -m playwright install chromium

export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5:7b-instruct
export OLLAMA_EMBED_MODEL=nomic-embed-text
export QDRANT_URL=http://127.0.0.1:6333
export QDRANT_COLLECTION=seo_crawl
export QDRANT_VECTOR_SIZE=768

# Qdrant still needs to run somewhere — easiest is:
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:v1.11.5

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then browse to <http://localhost:8000/ui/>.

---

## 10. DevOps handoff checklist

When you're ready to deploy to a production server, give Ops this list:

- Move secrets (`QDRANT_API_KEY`, optional `FIRECRAWL_API_KEY`) into a secret manager; `.env` is dev-only.
- Replace `host.docker.internal` with a real internal DNS entry for the Qwen inference host (or run Ollama on the same box).
- Back the `qdrant_data` volume with a managed disk / PVC; snapshots daily.
- Put the API behind an ingress (NGINX / Traefik / ALB) and terminate TLS there; the container listens on plain HTTP.
- Set `UVICORN_WORKERS` based on CPU count, or switch to `gunicorn -k uvicorn.workers.UvicornWorker`.
- Add observability: the service already emits JSON logs on stdout; ship via Vector / Fluent Bit and scrape `/healthz` + `/readyz` with your platform probes.
- Run the crawl endpoint from a separate worker pod if you expect large ingestion jobs — the `ingestion` placeholder is already sketched in `docker-compose.yml`.
- Schedule a daily re-crawl job (cron / Airflow / CronJob) hitting `/ingestion/crawl` to keep the knowledge base fresh.
