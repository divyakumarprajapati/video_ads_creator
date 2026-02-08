# Video & Static Ads Engine

A production-grade **Multi-Product Ad Generation Engine** that turns product catalogs into complete video and static image advertising campaigns automatically.

**Input**: Brand identity + Market research + Product images (1 to 100+)
**Output**: Product-specific videos (N x 3 variants) + General brand videos (3 variants) + **Static ad images (N x 3 variants) + General brand static ads (3 variants)**, exported for every social platform.

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

**Tech Stack**: Python 3.10+ · FastAPI · PostgreSQL · Pillow · FFmpeg · SDXL · AnimateDiff · Docker
**Optional**: Redis · Celery (for distributed workers) · S3 (for cloud storage)

---

## Quick Start

### Option A: Local Mode (Postgres only -- recommended for getting started)

The engine runs with **only PostgreSQL** as an external dependency. No Redis, no S3, no Celery needed. Videos are stored on the local filesystem and workers run in-process.

```bash
# 1. Clone and configure
git clone <this-repo>
cd video-ads-engine
cp .env.example .env

# 2. Start Postgres (via Docker or use your own)
docker compose -f docker-compose.local.yml up -d

# If you see "database \"video_ads\" does not exist", create it once:
# - Docker:
#   docker compose -f docker-compose.local.yml exec postgres psql -U postgres -d postgres -c "CREATE DATABASE video_ads;"
#   # (If you previously started Postgres with an existing `pgdata` volume, you may need: docker compose -f docker-compose.local.yml down -v)
# - Local Postgres:
#   psql -U postgres -d postgres -c "CREATE DATABASE video_ads;"

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Run database migrations
alembic upgrade head

# 5. Seed 108 video templates
python scripts/seed_templates.py

# 6. Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Generated videos are saved to `./output/` by default.

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

The same API call generates both **video ads** and **static ad images** automatically.

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
      {
        "product_name": "Vitamin C Serum",
        "product_image_url": "https://placehold.co/1024x1024/png",
        "product_category": "skincare",
        "tags": {"is_new": true},
        "image_url": "https://example.com/serum-lifestyle.jpg"
      },
      {
        "product_name": "Moisturizer",
        "product_image_url": "https://placehold.co/1024x1024/png",
        "product_category": "skincare",
        "tags": {"is_bestseller": true}
      }
    ],
    "campaign_goal": "awareness",
    "platforms": ["instagram_feed", "tiktok"],
    "duration_preference": 15
  }'
```

**Static Ad Image Support**: Each product can include an optional `image_url` field. When provided, this image is used as the hero image in static ad templates instead of the product image. If not provided, the `product_image_url` is used automatically.

### 6. Poll progress

```bash
curl http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/status \
  -H "X-API-Key: my-api-key"
```

The status response now includes static ad progress:

```json
{
  "campaign_id": "...",
  "status": "generating",
  "overall_progress": 45.0,
  "total_videos": 9,
  "completed_videos": 4,
  "total_static_ads": 9,
  "completed_static_ads": 6,
  "static_ads": [
    {
      "ad_id": "...",
      "ad_type": "product_specific",
      "product_name": "Vitamin C Serum",
      "variant_id": 1,
      "status": "completed",
      "quality_score": 90.0
    }
  ]
}
```

### 7. Get results

```bash
curl http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/results \
  -H "X-API-Key: my-api-key"
```

The results response includes both videos and static ads:

```json
{
  "campaign_id": "...",
  "campaign_name": "Summer Launch",
  "status": "completed",
  "products": [...],
  "videos": [...],
  "static_ads": [
    {
      "ad_id": "uuid",
      "ad_type": "product_specific",
      "product_name": "Vitamin C Serum",
      "variant_id": 1,
      "variant_type": "variant_a",
      "message_angle": "benefit",
      "headline": "Radiant Skin Starts Here",
      "subheading": "Vitamin C infused for natural glow",
      "cta_text": "Discover Now",
      "static_template_id": "hero_product_showcase_01",
      "static_template_name": "Classic Hero Product - Right Aligned",
      "status": "completed",
      "quality_score": 90.0,
      "file_path": "campaign_xxx/static_ads/product_specific/variant_1_benefit/static_ad_v1_hero_product_showcase_01.png",
      "thumbnail_path": "campaign_xxx/static_ads/product_specific/variant_1_benefit/thumb_static_ad_v1_hero_product_showcase_01.png",
      "file_size_mb": 0.45,
      "width": 1080,
      "height": 1080
    }
  ],
  "summary": {
    "total_products": 2,
    "total_videos": 9,
    "completed_videos": 9,
    "total_static_ads": 9,
    "completed_static_ads": 9,
    "average_quality_score": 92.5,
    "platforms": ["instagram_feed", "tiktok"]
  }
}
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
      "product_image_url": "string (required, used for videos + fallback for static ads)",
      "product_description": "string (optional)",
      "product_category": "string (optional)",
      "product_features": {"key": "value"},
      "price": 0.00,
      "tags": {"is_new": false, "is_bestseller": false},
      "image_url": "string (optional, hero image for static ads)"
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
│   │   ├── static_ad/
│   │   │   ├── template_registry.py  # Load/manage static ad templates
│   │   │   ├── template_selector.py  # Score + select templates for campaign
│   │   │   └── generator.py          # Generate static ad images (Pillow)
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
- **Goal + Industry + Category** → Static ad template selection (hero showcase, benefit grid, testimonial, etc.)

### 2. Video Generation Pipeline

For each video variant, the pipeline runs:

1. **Asset Prep**: Download image → Remove background (rembg) → Upscale (Real-ESRGAN) → Generate background → Composite
2. **Video Gen**: Create base video → Apply motion (zoom, pan) → Colour grade → Add text overlays → Fade transitions
3. **QA**: Probe video → Check resolution, duration, FPS, codec, file size, clarity → Score 0-100
4. **Export**: Encode for each platform (Instagram 1:1, TikTok 9:16, etc.) → Extract thumbnails → Write metadata

### 3. Static Ad Generation Pipeline

For each static ad variant, the pipeline runs:

1. **Template Selection**: Score all 50+ templates from `template.json` using campaign goal, message angle, industry, product category, and visual style
2. **Image Composition**: Using Pillow, compose the ad image following the template's visual structure:
   - Apply brand colors (primary, secondary, accent, background)
   - Place product/user-provided image according to template layout
   - Render headline, subheading, CTA text with proper typography
   - Add decorative elements (gradients, shapes, badges, dividers)
   - Apply brand name and logo where specified
3. **Output**: Save as high-quality PNG (1080x1080) with thumbnail generation

**15 Template Categories** with multiple variants each:

| Category | Templates | Best For |
|----------|-----------|----------|
| Hero Product Showcase | 5 | Product launches, e-commerce, premium goods |
| Benefit Grid | 5 | SaaS features, service offerings, subscriptions |
| Before/After | 4 | Transformation products, renovation, fitness |
| Testimonial Trust | 5 | Social proof, B2B, premium services |
| Urgency/Countdown | 5 | Flash sales, limited offers, enrollment deadlines |
| Lifestyle Context | 5 | Fashion, travel, fitness, food & beverage |
| Stat/Impact Dashboard | 5 | B2B SaaS, analytics, financial products |
| Minimalist Luxury | 5 | Luxury fashion, jewelry, premium cosmetics |
| Problem-Agitation-Solution | 5 | Pain-point products, cleaning, productivity |
| Social Proof Carousel | 5 | Enterprise B2B, startups with PR, trending products |
| Feature Highlight | 5 | SaaS updates, tech products, app features |
| Seasonal Campaign | 5 | Holiday sales, seasonal promotions, cultural events |
| Comparison Table | 4 | Competitive positioning, plan comparison |
| UGC Authenticity | 5 | Community brands, beauty, fitness, food |
| How It Works | 2 | Onboarding, services, complex products |

### 4. Parallel Processing

- Each product's videos run as an independent Celery task
- General brand videos run as a separate task
- Static ads are generated after video processing completes
- All tasks execute in parallel across available workers
- Progress tracked in Redis, queryable via status endpoint

---

## AI Models

The engine supports these open-source AI models (all optional with graceful fallback):

| Model | Purpose | VRAM | Fallback |
|-------|---------|------|----------|
| SDXL | Background/scene generation | 8GB+ | Gradient backgrounds |
| AnimateDiff v3 | Product animation | 12GB+ | FFmpeg zoom/pan |
| SVD | Simple animation | 8GB+ | FFmpeg effects |
| rembg (U2-Net) | Background removal | 2GB | No removal |
| Real-ESRGAN | Image upscaling | 2GB | Pillow LANCZOS |
| Mistral 7B | Message text generation | 6GB+ | Template messages |

**Without GPU**: The engine works fully with FFmpeg-based video generation. AI models enhance quality but are not required.

### Download models

```bash
# Example: download SDXL
python -c "from huggingface_hub import snapshot_download; snapshot_download('stabilityai/stable-diffusion-xl-base-1.0', local_dir='./models/stable-diffusion-xl-base-1.0')"
```

---

## Using Campaign Data After Update

The campaign API now returns both video ads and static ad images. Here's how to consume the updated data:

### Response Structure

After campaign completion, the results endpoint returns:

```json
{
  "videos": [...],        // Video ads (same as before)
  "static_ads": [...],    // NEW: Static ad images
  "summary": {
    "total_videos": 9,
    "completed_videos": 9,
    "total_static_ads": 9,     // NEW
    "completed_static_ads": 9  // NEW
  }
}
```

### Accessing Static Ad Images

Each static ad in the `static_ads` array contains:

| Field | Description |
|-------|-------------|
| `file_path` | Relative path to the generated PNG image |
| `thumbnail_path` | Relative path to a 300x300 thumbnail |
| `static_template_id` | The template used (e.g. `hero_product_showcase_01`) |
| `static_template_name` | Human-readable template name |
| `headline` | The headline text rendered on the image |
| `subheading` | The subheading text rendered |
| `cta_text` | The call-to-action text |
| `width` / `height` | Image dimensions (default 1080x1080) |
| `ad_type` | `product_specific` or `general_brand` |
| `image_url` | The user-provided image URL used (if any) |

### Download Static Ads

Static ad images are included in the campaign ZIP download:

```bash
# Download all campaign assets (videos + static ads)
curl -O http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/download \
  -H "X-API-Key: my-api-key"
```

Static ads are organized in the archive as:

```
campaign_{id}/
├── product_specific/          # Video exports
├── general_brand/             # Video exports
└── static_ads/                # NEW: Static ad images
    ├── product_specific/
    │   ├── variant_1_benefit/
    │   │   ├── static_ad_v1_hero_product_showcase_01.png
    │   │   └── thumb_static_ad_v1_hero_product_showcase_01.png
    │   ├── variant_2_social_proof/
    │   │   └── ...
    │   └── variant_3_urgency/
    │       └── ...
    └── general_brand/
        ├── variant_1_benefit/
        │   └── ...
        └── ...
```

### Serving Static Ad Images

Static ad images can be served via the existing assets endpoint:

```bash
# Serve a static ad image
GET /api/v1/assets/{file_path}
```

Where `file_path` is the relative path from the results response.

### Python Integration Example

```python
import httpx

API = "http://localhost:8000/api/v1"
HEADERS = {"X-API-Key": "my-key"}

# Get results
results = httpx.get(f"{API}/campaigns/{campaign_id}/results", headers=HEADERS).json()

# Process video ads (same as before)
for video in results["videos"]:
    print(f"Video: {video['video_type']} - {video['status']}")
    print(f"  File: {video['file_path']}")

# Process static ads (NEW)
for ad in results["static_ads"]:
    print(f"Static Ad: {ad['ad_type']} - {ad['status']}")
    print(f"  Template: {ad['static_template_name']}")
    print(f"  Headline: {ad['headline']}")
    print(f"  File: {ad['file_path']}")
    print(f"  Size: {ad['width']}x{ad['height']}")

    # Download the static ad image
    if ad["file_path"]:
        img_resp = httpx.get(f"{API}/assets/{ad['file_path']}", headers=HEADERS)
        with open(f"ad_{ad['variant_id']}.png", "wb") as f:
            f.write(img_resp.content)

# Summary includes both types
summary = results["summary"]
print(f"Total videos: {summary['total_videos']}, completed: {summary['completed_videos']}")
print(f"Total static ads: {summary['total_static_ads']}, completed: {summary['completed_static_ads']}")
```

### Node.js Integration Example

```javascript
const API = 'http://localhost:8000/api/v1';
const headers = { 'X-API-Key': 'my-key' };

const results = await fetch(`${API}/campaigns/${campaignId}/results`, { headers })
  .then(r => r.json());

// Video ads
results.videos.forEach(video => {
  console.log(`Video: ${video.video_type} [${video.status}]`);
});

// Static ads (NEW)
results.static_ads.forEach(ad => {
  console.log(`Static Ad: ${ad.static_template_name}`);
  console.log(`  Headline: ${ad.headline}`);
  console.log(`  File: ${ad.file_path}`);
  console.log(`  Dimensions: ${ad.width}x${ad.height}`);
});

// Summary
const { summary } = results;
console.log(`Videos: ${summary.completed_videos}/${summary.total_videos}`);
console.log(`Static Ads: ${summary.completed_static_ads}/${summary.total_static_ads}`);
```

### Using `image_url` for Custom Static Ad Images

You can provide a custom image for each product's static ads using the `image_url` field:

```json
{
  "products": [
    {
      "product_name": "Vitamin C Serum",
      "product_image_url": "https://cdn.example.com/serum-product-shot.png",
      "image_url": "https://cdn.example.com/serum-lifestyle-photo.jpg",
      "product_category": "skincare"
    }
  ]
}
```

| Field | Used For | Required |
|-------|----------|----------|
| `product_image_url` | Video ads (background removal, compositing) + fallback for static ads | Yes |
| `image_url` | Static ad hero image (lifestyle shots, marketing photos) | No |

When `image_url` is provided:
- Static ads use it as the primary image (great for lifestyle/marketing shots)
- Video ads continue using `product_image_url` (optimized for product isolation)

When `image_url` is **not** provided:
- Static ads fall back to using `product_image_url`
- Works perfectly with product-on-white-background shots

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
