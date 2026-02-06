# Video Ads Engine

A production-grade **Multi-Product Video Ads Generation Engine** that turns product catalogs into complete video advertising campaigns automatically.

**Input**: Brand identity + Market research + Product images (1 to 100+)
**Output**: Product-specific videos (N x 3 variants) + General brand videos (3 variants), exported for every social platform.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Quick Start](#quick-start)
3. [API Reference](#api-reference)
4. [Integration Guide](#integration-guide)
5. [Project Structure](#project-structure)
6. [Configuration](#configuration)
7. [How It Works](#how-it-works)
8. [AI Models](#ai-models)
9. [Testing](#testing)
10. [Deployment](#deployment)

---

## Architecture

```
                         ┌──────────────────────┐
                         │   Your Backend App   │
                         │  (any language/stack) │
                         └──────────┬───────────┘
                                    │  HTTP / JSON
                         ┌──────────▼───────────┐
                         │   FastAPI  (REST)     │
                         │   JWT + API Key Auth  │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
   ┌──────────▼──────────┐ ┌───────▼───────┐ ┌───────────▼─────────┐
   │  Campaign Service   │ │ Strategy Eng. │ │  Template Library   │
   │  (Orchestration)    │ │ (Rule-based)  │ │  (108 templates)    │
   └──────────┬──────────┘ └───────────────┘ └─────────────────────┘
              │
   ┌──────────▼──────────┐
   │   Celery + Redis    │  ← Job queue, progress tracking
   │   Task Dispatch     │
   └──────────┬──────────┘
              │
    ┌─────────┼─────────┬────────────────┐
    │         │         │                │
┌───▼──┐ ┌───▼──┐ ┌────▼───┐  ┌─────────▼────────┐
│Prod 1│ │Prod 2│ │Prod N  │  │ General Brand    │
│Worker│ │Worker│ │Worker  │  │ Video Worker     │
└───┬──┘ └───┬──┘ └────┬───┘  └─────────┬────────┘
    │         │         │                │
    └─────────┼─────────┼────────────────┘
              │
   ┌──────────▼──────────┐
   │  Video Pipeline     │
   │  Asset Prep → Gen → │
   │  QA → Export        │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  S3 Storage + CDN   │
   └─────────────────────┘
```

**Tech Stack**: Python 3.10+ · FastAPI · PostgreSQL · FFmpeg · SDXL · AnimateDiff · Docker
**Optional**: Redis · Celery (for distributed workers) · S3 (for cloud storage)

---

## Quick Start

### Option A: MacBook / Low-RAM / No-GPU (recommended for getting started)

Runs on **MacBook M1 with 8GB RAM**. Only needs PostgreSQL + FFmpeg. Installs in ~30 seconds.

```bash
# Prerequisites: Python 3.10+, Docker, FFmpeg
brew install ffmpeg          # macOS
# sudo apt install ffmpeg    # Linux

# 1. Clone and configure
git clone <this-repo>
cd video-ads-engine
cp .env.example .env
# Edit .env → set OPENAI_API_KEY=sk-your-key (for AI-generated ad copy)

# 2. One command to set up and run:
make quickstart
# Or step by step:
#   make setup-lite   ← lightweight deps (~200MB, no PyTorch)
#   make db           ← start Postgres via Docker
#   make migrate      ← create tables
#   make seed         ← load 108 templates
#   make run          ← start API server
```

That's it. API is at `http://localhost:8000/docs`. Videos saved to `./output/`.

**What works on 8GB M1:**
| Feature | Status | How |
|---------|--------|-----|
| Full API + strategy engine | Works | Pure Python, ~100MB RAM |
| Video generation (zoom, text, grid, carousel) | Works | FFmpeg (native ARM) |
| Platform export (Instagram, TikTok, etc.) | Works | FFmpeg encoding |
| Ad-copy generation | Works | OpenAI API (no local model) |
| Background removal | Skipped | Falls back to original image |
| AI upscaling | Skipped | Falls back to Pillow resize |
| AI animation (AnimateDiff) | Skipped | Falls back to FFmpeg zoom/pan |
| SDXL image generation | Skipped | Falls back to gradient backgrounds |

The fallbacks produce professional results. The AI features add polish when you have a GPU server later.

### Option A2: Local Mode with full AI packages (16GB+ RAM recommended)

Same as above but with `pip install -r requirements.txt` instead of `requirements-lite.txt`.
This installs PyTorch, rembg, diffusers etc. for background removal and AI features.

### Option B: Full Stack (Docker Compose -- all services)

### Option B: Full Stack (Docker Compose -- all services)

For production-like setup with Redis, Celery workers, S3 (MinIO), and monitoring.

```bash
# 1. Configure for full mode
cp .env.example .env
# Edit .env and set:
#   USE_CELERY=true
#   REDIS_ENABLED=true
#   STORAGE_BACKEND=s3

# 2. Start everything
docker compose up -d

# 3. Run migrations
docker compose exec api alembic upgrade head

# 4. Seed templates
docker compose exec api python scripts/seed_templates.py
```

### 5. Create your first campaign

```bash
curl -X POST http://localhost:8000/api/v1/campaigns \
  -H "X-API-Key: my-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "Summer Launch",
    "brand_identity": {
      "brand_name": "Glow Naturals",
      "colors": {"primary": "#2E8B57", "secondary": "#F0F8FF", "background": "#FFF", "text": "#000"},
      "fonts": {"heading": "Playfair Display", "body": "Lato"},
      "voice": "warm",
      "tone": "confident",
      "industry": "skincare"
    },
    "market_research": {
      "saturation_percent": 72.0,
      "competitive_edge_percent": 78.0,
      "sentiment": "positive"
    },
    "products": [
      {"product_name": "Vitamin C Serum", "product_image_url": "https://placehold.co/1024x1024/png", "product_category": "skincare", "tags": {"is_new": true}},
      {"product_name": "Moisturizer", "product_image_url": "https://placehold.co/1024x1024/png", "product_category": "skincare", "tags": {"is_bestseller": true}}
    ],
    "campaign_goal": "awareness",
    "platforms": ["instagram_feed", "tiktok"],
    "duration_preference": 15
  }'
```

### 6. Poll progress

```bash
curl http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/status \
  -H "X-API-Key: my-api-key"
```

### 7. Get results

```bash
curl http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/results \
  -H "X-API-Key: my-api-key"
```

### Service URLs

| Service        | URL                          |
|---------------|------------------------------|
| API Docs      | http://localhost:8000/docs   |
| ReDoc         | http://localhost:8000/redoc  |
| Flower (tasks)| http://localhost:5555        |
| MinIO Console | http://localhost:9001        |

---

## API Reference

All endpoints require authentication via either:
- **JWT Bearer token**: `Authorization: Bearer <token>`
- **API Key header**: `X-API-Key: <key>`

### Campaign Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/campaigns` | Create a multi-product campaign |
| `GET` | `/api/v1/campaigns/{id}/status` | Poll generation progress |
| `GET` | `/api/v1/campaigns/{id}/results` | Get completed videos + downloads |
| `POST` | `/api/v1/campaigns/{id}/regenerate` | Re-generate failed videos |

### Template Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/templates` | List/filter templates |
| `GET` | `/api/v1/templates/{id}` | Get template details |

### Project Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/projects/{id}/campaigns` | List campaigns for a project |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/ready` | Readiness probe |

### Request Body: Create Campaign

```json
{
  "campaign_name": "string (required)",
  "project_id": "string (default: 'default')",

  "brand_identity": {
    "brand_name": "string (required)",
    "tagline": "string (optional)",
    "logo_url": "string (optional)",
    "colors": {
      "primary": "#hex (required)",
      "secondary": "#hex (required)",
      "accent": "#hex (optional)",
      "background": "#hex (default: #FFFFFF)",
      "text": "#hex (default: #000000)"
    },
    "fonts": {
      "heading": "string (default: Montserrat)",
      "body": "string (default: Open Sans)"
    },
    "voice": "string (default: professional)",
    "tone": "string (default: confident)",
    "industry": "string (optional)"
  },

  "market_research": {
    "saturation_percent": "float 0-100 (default: 50)",
    "competitive_edge_percent": "float 0-100 (default: 50)",
    "sentiment": "positive|neutral|negative|mixed (default: neutral)",
    "trending_keywords": ["string array"],
    "target_audience_age_min": "int (default: 18)",
    "target_audience_age_max": "int (default: 65)",
    "target_audience_gender": "all|male|female (default: all)"
  },

  "products": [
    {
      "product_name": "string (required)",
      "product_image_url": "string (required)",
      "product_description": "string (optional)",
      "product_category": "string (optional)",
      "product_features": {"key": "value"},
      "price": 0.00,
      "tags": {"is_new": false, "is_bestseller": false}
    }
  ],

  "campaign_goal": "awareness|consideration|conversion|retention",
  "platforms": ["instagram_feed", "instagram_story", "tiktok", "youtube_shorts", "meta_ads"],
  "duration_preference": "int 5-60 seconds (default: 15)",
  "product_specific_variants": "int 1-5 (default: 3)",
  "general_brand_variants": "int 1-5 (default: 3)"
}
```

---

## Integration Guide

### From Python

```python
import httpx

API = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "my-key", "Content-Type": "application/json"}

# Create campaign
resp = httpx.post(f"{API}/campaigns", json={...}, headers=HEADERS)
campaign_id = resp.json()["id"]

# Poll until done
import time
while True:
    status = httpx.get(f"{API}/campaigns/{campaign_id}/status", headers=HEADERS).json()
    if status["status"] in ("completed", "failed"):
        break
    time.sleep(5)

# Get results
results = httpx.get(f"{API}/campaigns/{campaign_id}/results", headers=HEADERS).json()
for video in results["videos"]:
    print(video["video_type"], video["status"], video["quality_score"])
```

### From Node.js

```javascript
const API = 'http://localhost:8000/api/v1';
const headers = { 'X-API-Key': 'my-key', 'Content-Type': 'application/json' };

// Create campaign
const res = await fetch(`${API}/campaigns`, {
  method: 'POST', headers,
  body: JSON.stringify({ campaign_name: 'Test', brand_identity: {...}, products: [...] })
});
const { id } = await res.json();

// Poll status
const poll = async () => {
  const s = await fetch(`${API}/campaigns/${id}/status`, { headers }).then(r => r.json());
  if (['completed', 'failed'].includes(s.status)) return s;
  await new Promise(r => setTimeout(r, 5000));
  return poll();
};
await poll();

// Get results
const results = await fetch(`${API}/campaigns/${id}/results`, { headers }).then(r => r.json());
```

### From Go

```go
req, _ := http.NewRequest("POST", "http://localhost:8000/api/v1/campaigns", bytes.NewBuffer(jsonPayload))
req.Header.Set("X-API-Key", "my-key")
req.Header.Set("Content-Type", "application/json")
resp, _ := http.DefaultClient.Do(req)
```

See `docs/examples/integration_guide.py` for a complete runnable Python example with all endpoints.

---

## Project Structure

```
.
├── app/
│   ├── api/v1/
│   │   ├── endpoints/           # Route handlers
│   │   │   ├── campaigns.py     # Campaign CRUD + status + results
│   │   │   ├── templates.py     # Template list/detail
│   │   │   ├── projects.py      # Project-scoped queries
│   │   │   └── health.py        # Health/readiness probes
│   │   └── router.py            # Aggregated router
│   ├── core/
│   │   ├── config.py            # Pydantic settings (all env vars)
│   │   ├── enums.py             # Domain enums (30+ enums)
│   │   ├── logging.py           # Structured logging (structlog)
│   │   └── security.py          # JWT + API key auth
│   ├── db/
│   │   └── session.py           # Async SQLAlchemy engine + session
│   ├── models/
│   │   └── campaign.py          # ORM models (5 tables)
│   ├── schemas/
│   │   ├── brand.py             # Brand identity + market research
│   │   ├── campaign.py          # Campaign request/response models
│   │   ├── product.py           # Product input/output models
│   │   └── template.py          # Template models
│   ├── services/
│   │   ├── strategy/
│   │   │   ├── decision_matrices.py  # Deterministic lookup tables
│   │   │   ├── engine.py             # Strategy generation orchestrator
│   │   │   ├── platform_specs.py     # Platform export specifications
│   │   │   └── template_selector.py  # Template scoring + selection
│   │   ├── asset/
│   │   │   └── processor.py     # Image download, bg removal, upscale
│   │   ├── video/
│   │   │   └── generator.py     # Video creation (FFmpeg + AI)
│   │   ├── export/
│   │   │   └── encoder.py       # Platform-specific encoding
│   │   ├── qa/
│   │   │   └── validator.py     # Automated quality checks
│   │   ├── storage/
│   │   │   └── s3.py            # S3-compatible storage client
│   │   └── campaign_service.py  # Campaign lifecycle orchestration
│   ├── workers/
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── progress.py          # Redis-based progress tracking
│   │   └── tasks.py             # Celery task definitions
│   ├── utils/
│   │   ├── ffmpeg.py            # FFmpeg CLI wrapper (20+ operations)
│   │   ├── image.py             # Pillow image processing utilities
│   │   └── file_utils.py        # Path/directory helpers
│   └── main.py                  # FastAPI app factory
├── alembic/                     # Database migrations
├── tests/
│   ├── unit/                    # 46 unit tests
│   └── integration/             # Integration test stubs
├── scripts/
│   └── seed_templates.py        # Seed 108 video templates
├── docs/examples/
│   └── integration_guide.py     # Runnable integration example
├── docker-compose.yml           # Full dev stack
├── Dockerfile                   # Multi-stage build
├── requirements.txt             # Pinned dependencies
└── .env.example                 # All configuration options
```

---

## Configuration

All settings are environment variables. Copy `.env.example` to `.env` and customise:

| Variable | Default | Description |
|----------|---------|-------------|
| **Feature Flags** | | |
| `USE_CELERY` | `false` | `true` = Celery workers (requires Redis) |
| `REDIS_ENABLED` | `false` | `true` = Redis for rate-limit & progress |
| `STORAGE_BACKEND` | `local` | `local` = filesystem, `s3` = S3-compatible |
| **Core** | | |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB connection |
| `DATABASE_SYNC_URL` | `postgresql+psycopg2://...` | Sync DB (for workers) |
| `JWT_SECRET_KEY` | `change-me` | JWT signing secret |
| **Local Storage** | | |
| `LOCAL_STORAGE_ROOT` | `./output` | Where videos are saved locally |
| `LOCAL_STORAGE_URL_PREFIX` | `http://localhost:8000/static` | URL prefix for downloads |
| **Redis** (when enabled) | | |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | Celery broker |
| **S3** (when enabled) | | |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | S3-compatible endpoint |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `minioadmin` | S3 credentials |
| **Other** | | |
| `MAX_PRODUCTS_PER_CAMPAIGN` | `500` | Product limit |
| `GPU_DEVICES` | `0` | Comma-separated GPU IDs |
| `SDXL_MODEL_PATH` | `/models/...` | Path to SDXL weights |

---

## How It Works

### 1. Strategy Generation (Deterministic, No AI)

When a campaign is created, the **Strategy Engine** makes every creative decision using lookup tables:

- **Market saturation + Competitive edge** → Visual style (bold, elegant, minimalist, etc.)
- **Campaign goal** → Message angle priority (benefit, social proof, urgency)
- **Visual style** → Pacing (fast/medium/slow)
- **Product category** → Video style (hero, lifestyle, kinetic text)
- **Product tags** → Primary message ("Just Dropped", "Fan Favorite", etc.)
- **Goal** → CTA text ("Shop Now", "Discover", "Visit Site")
- **Product count** → Layout type for brand videos (carousel, grid, hero+supporting)

### 2. Video Generation Pipeline

For each video variant, the pipeline runs:

1. **Asset Prep**: Download image → Remove background (rembg) → Upscale (Real-ESRGAN) → Generate background → Composite
2. **Video Gen**: Create base video → Apply motion (zoom, pan) → Colour grade → Add text overlays → Fade transitions
3. **QA**: Probe video → Check resolution, duration, FPS, codec, file size, clarity → Score 0-100
4. **Export**: Encode for each platform (Instagram 1:1, TikTok 9:16, etc.) → Extract thumbnails → Write metadata

### 3. Parallel Processing

- Each product's videos run as an independent Celery task
- General brand videos run as a separate task
- All tasks execute in parallel across available workers
- Progress tracked in Redis, queryable via status endpoint

---

## AI Models

### OpenAI GPT-5.1 (Cloud API -- recommended)

All ad-copy text (headlines, secondary messages, CTAs) is generated by `gpt-5.1-chat-latest`.
Just set `OPENAI_API_KEY` in your `.env`. No local GPU, no model downloads, works on any machine.

When the key is not set, the engine uses built-in template text (still professional, just less personalised).

### Open-Source Models (Optional -- GPU required)

These enhance visual quality but are **not required**. Every one has a graceful fallback:

| Model | Purpose | RAM/VRAM | Fallback (what runs on M1 8GB) |
|-------|---------|----------|-------------------------------|
| SDXL | Background/scene generation | 8GB+ VRAM | Gradient backgrounds (Pillow) |
| AnimateDiff v3 | Product animation | 12GB+ VRAM | FFmpeg zoom/pan effects |
| SVD | Simple animation | 8GB+ VRAM | FFmpeg effects |
| rembg (U2-Net) | Background removal | 2GB RAM | Uses original image as-is |
| Real-ESRGAN | Image upscaling | 2GB RAM | Pillow LANCZOS resize |

**M1 8GB**: Skip these entirely. Use `requirements-lite.txt`. The engine produces complete, professional videos with FFmpeg + Pillow + OpenAI.

**GPU server (16GB+ VRAM)**: Install full `requirements.txt` and download model weights:

```bash
# Example: download SDXL
python -c "from huggingface_hub import snapshot_download; snapshot_download('stabilityai/stable-diffusion-xl-base-1.0', local_dir='./models/stable-diffusion-xl-base-1.0')"
```

---

## Testing

```bash
# Run all unit tests
python3 -m pytest tests/unit/ -v

# Run with coverage
python3 -m pytest tests/ --cov=app --cov-report=html

# Run specific test file
python3 -m pytest tests/unit/test_strategy_engine.py -v
```

---

## Deployment

### Docker Compose (Development)

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_templates.py
```

### Production

1. **API**: Deploy behind NGINX/ALB with `gunicorn -k uvicorn.workers.UvicornWorker`
2. **Workers**: Scale independently: `docker compose up --scale worker=4`
3. **Database**: Use managed PostgreSQL (RDS, Cloud SQL)
4. **Redis**: Use managed Redis (ElastiCache, Memorystore)
5. **Storage**: Use AWS S3 / DigitalOcean Spaces / GCS
6. **GPU Workers**: Deploy on GPU instances with NVIDIA Container Toolkit

### Scaling

| Component | Scale Strategy |
|-----------|---------------|
| API | Horizontal (add instances behind LB) |
| Workers | Horizontal (add GPU nodes) |
| PostgreSQL | Vertical + read replicas |
| Redis | Cluster mode |
| Storage | S3 auto-scales |

---

## License

MIT
