# Barta - AI News Assistant

A production-grade AI news assistant built with FastAPI, Next.js, PostgreSQL, and Redis.

## Quick Start

```bash
# Clone and navigate to project
cd barta

# Start all services
make up

# Check health
make health
```

Visit:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000/api/v1/health
- **Metrics**: http://localhost:8000/api/v1/metrics

## Architecture

### Backend (FastAPI)
- **API**: Python 3.11, FastAPI, Uvicorn
- **Database**: PostgreSQL 15 + pgvector for vector search
- **Cache**: Redis for session and data caching
- **Migrations**: Alembic for database versioning

### Frontend (Next.js)
- **Framework**: Next.js 14 with App Router
- **Styling**: Tailwind CSS + shadcn/ui (dark theme)
- **Components**: React 18 with TypeScript

### Infrastructure
- **Containers**: Docker + docker-compose
- **Development**: Hot reload for both API and web
- **Testing**: Pytest for backend, built-in Next.js testing

## Development

### Prerequisites
- Docker & docker-compose
- Make (optional, for convenience commands)

### Commands

```bash
# Development
make dev          # Start with auto-rebuild
make up           # Start services
make down         # Stop services
make logs         # View all logs
make logs-api     # API logs only
make logs-web     # Web logs only

# Database
make migrate      # Run migrations
make migrate-create msg="description"  # Create migration
make shell-db     # Access database

# Testing
make test         # Run backend tests
make health       # Check service health

# Maintenance
make clean        # Clean containers/volumes
make shell-api    # API container shell
make shell-web    # Web container shell
```

### File Structure

```
barta/
├── apps/
│   ├── api/              # FastAPI backend
│   │   ├── main.py       # App entry point
│   │   ├── routes/       # API endpoints
│   │   │   ├── health.py # Health checks
│   │   │   └── metrics.py# System metrics
│   │   └── core/         # Core modules
│   │       ├── config.py # Configuration
│   │       └── db.py     # Database setup
│   └── web/              # Next.js frontend
│       ├── app/          # App Router pages
│       ├── components/   # React components
│       └── lib/          # Utilities
├── infra/
│   ├── docker/           # Dockerfiles
│   └── migrations/       # Alembic migrations
├── tests/                # Backend tests
├── docker-compose.yml    # Services orchestration
├── Makefile             # Development commands
└── pyproject.toml       # Python dependencies
```

## Services

### API Service
- **Port**: 8000
- **Health**: `/api/v1/health`
- **Metrics**: `/api/v1/metrics`
- **Dependencies**: PostgreSQL, Redis

### Web Service  
- **Port**: 3000
- **Proxy**: API calls forwarded to backend
- **Theme**: Dark mode only (shadcn/ui)

### Database (PostgreSQL + pgvector)
- **Port**: 5432
- **Extensions**: pgvector for embeddings
- **Credentials**: barta/barta

### Cache (Redis)
- **Port**: 6379
- **Use**: Sessions, caching, pub/sub

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://barta:barta@localhost:5432/barta

# External APIs (when ready)
NEWS_API_KEY=your-news-api-key
OPENAI_API_KEY=your-openai-api-key
```

## Ingestion Quickstart

The production-ready ingestion pipeline fetches articles, extracts content, deduplicates, chunks, embeds, and stores in PostgreSQL with pgvector.

### Setup & Usage

```bash
# 1. Start services (includes Postgres 5433->5432, Redis 6380->6379)
make up

# 2. Run migrations to create ingestion tables
make db-migrate

# 3. Install playwright (first time only)
docker compose exec api bash
playwright install --with-deps
exit

# 4. Run ingestion pipeline
make ingest

# 5. Generate embeddings for articles
make embed-once
```

### Port Mappings

- **Postgres**: Container 5432 → Host 5433
- **Redis**: Container 6379 → Host 6380
- **Local dev URLs**: Use ports 5433/6380 when connecting from host

### Features

- Full article extraction (not just RSS) using Playwright + Trafilatura
- Near-duplicate detection via SimHash (Hamming distance ≤ 3)
- Word-based chunking (800 words, 120 overlap)
- Vector embeddings (3072-dim) with pgvector indexing
- Full-text search with tsvector/GIN indexes
- Deterministic fallback when OpenAI API key missing
- CLI runners with comprehensive error handling

## Retrieval System

Production-grade hybrid retrieval combining BM25 full-text search and dense vector search with MMR diversification and cross-encoder reranking.

### How It Works

1. **Hybrid Search**: Combines BM25 (PostgreSQL tsvector) + Dense vector search (pgvector)
2. **Score Normalization**: Min-max scaling per method to prevent dominance
3. **Deduplication**: Merges results by chunk_id, keeping highest scores
4. **MMR Diversification**: Applies Maximal Marginal Relevance (λ=0.7) for diverse results
5. **Cross-encoder Reranking**: Uses `ms-marco-MiniLM-L-6-v2` for final relevance scoring
6. **Redis Caching**: Caches rerank scores to reduce latency and compute costs

### API Usage

```bash
# Search articles
curl "http://localhost:8000/api/search?q=climate%20change"

# Example response
{
  "query": "climate change",
  "results": [
    {
      "chunk_id": 123,
      "article_id": 45,
      "title": "Climate Report 2024",
      "url": "https://example.com/climate-report",
      "published_at": "2024-08-29T12:34:56Z",
      "source_domain": "example.com",
      "content": "Global temperatures continue to rise...",
      "score": 0.78,
      "rerank_score": 15.3
    }
  ]
}
```

### Performance Configuration

```bash
# In .env - adjust for performance/quality tradeoffs
RERANKER_ENABLED=true                    # Enable/disable reranking
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2  # CPU-friendly model
RETRIEVAL_K_BM25=100                     # BM25 candidates
RETRIEVAL_K_DENSE=100                    # Dense candidates  
RETRIEVAL_MMR_K=40                       # Post-MMR candidates
RETRIEVAL_FINAL_K=8                      # Final results
RETRIEVAL_MMR_LAMBDA=0.7                 # MMR relevance vs diversity (0=diversity, 1=relevance)
CACHE_TTL_SECONDS=3600                   # Redis cache TTL
```

### Disable Reranker (for faster/lighter builds)

```bash
# In .env
RERANKER_ENABLED=false

# This disables sentence-transformers/torch loading
# Reduces image size and startup time
# Falls back to BM25+dense scores only
```

### Performance Tips

- **Redis Running**: Ensures reranker caching works (major latency improvement)
- **Smaller K Values**: Reduce `RETRIEVAL_K_BM25/DENSE` for faster dev queries  
- **Lambda Tuning**: Lower `RETRIEVAL_MMR_LAMBDA` for more diverse results
- **Model Selection**: Use smaller cross-encoder models for speed vs accuracy tradeoffs

### Monitoring

Prometheus metrics available at `/metrics`:
- `retrieval_latency_ms`: Query response times
- `retrieval_queries_total`: Total queries processed
- `reranker_cache_hits/misses_total`: Cache performance

## Chat & Memory

AI-powered chat agent with two-pass answers, strict citations, conversation memory, and SSE streaming.

### How It Works

1. **Two-Pass System**: Plan → Answer for better structured responses
2. **Hybrid Retrieval**: Uses existing search pipeline to find relevant passages
3. **Strict Citations**: Inline `[1],[2]` markers with Sources section
4. **Memory**: Rolling conversation summaries stored in PostgreSQL
5. **SSE Streaming**: Real-time response streaming to frontend

### API Usage

```bash
# Chat via curl (Server-Sent Events)
curl -N -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message":"What happened today in Dhaka?"}'

# With existing conversation
curl -N -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message":"Tell me more", "conversation_id":"uuid-here"}'
```

### Expected SSE Stream

```
event: delta
data: {"token": "##"}

event: delta  
data: {"token": " TL;DR\n\n"}

event: delta
data: {"token": "Recent developments in Dhaka include..."}

event: done
data: {"ok": true, "conversation_id": "abc-123", "sources": [{"index": 1, "title": "...", "url": "..."}]}
```

### Configuration

```bash
# In .env - LLM and chat settings
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=700
LLM_TEMPERATURE=0.2
CITATION_STRICT=true
PLAN_MAX_BULLETS=8
```

### Features

- **Fake Streaming**: Works without `OPENAI_API_KEY` for development
- **Citation Enforcement**: Retries responses lacking proper citations
- **Memory Persistence**: Conversation history and summaries in database
- **Source Integration**: Clickable citations linked to original articles
- **Graceful Degradation**: Falls back to deterministic responses when API unavailable

### Frontend Integration

The React chat component (`apps/web/components/Chat.tsx`) provides:
- Real-time SSE streaming with token display
- Clickable citation links with anchored sources  
- Conversation persistence via localStorage
- Dark theme styling consistent with app design
- Auto-scroll and loading states

## Testing

```bash
# Backend tests (includes ingestion + retrieval tests)
make test

# Manual API testing
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/metrics
```

## Deployment

Production-ready with:
- Multi-stage Docker builds
- Health checks and metrics
- Database migrations
- Volume persistence
- Horizontal scaling ready

---

**Status**: Basic skeleton complete - ready for feature development!
