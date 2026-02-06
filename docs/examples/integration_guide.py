#!/usr/bin/env python3
"""
==========================================================================
 Video Ads Engine – Integration Guide
==========================================================================

This file shows how to call the Video Ads Engine from **any** backend
(Python, Node.js, Go, etc.) using plain HTTP requests.

Every example uses the `httpx` library (Python), but the request bodies
and URLs are standard REST – copy the JSON payloads into any language.

Prerequisites:
    1. Engine is running (docker compose up -d)
    2. Migrations applied  (docker compose exec api alembic upgrade head)
    3. Templates seeded    (docker compose exec api python scripts/seed_templates.py)

Run this file:
    pip install httpx
    python docs/examples/integration_guide.py
"""

from __future__ import annotations

import time
import json
import httpx

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000/api/v1"
API_KEY  = "my-secret-api-key"              # any non-empty string works in dev

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
}


# ────────────────────────────────────────────────────────────
# 1. Create a Campaign
# ────────────────────────────────────────────────────────────

def create_campaign() -> dict:
    """
    POST /api/v1/campaigns

    This single request is all you need.  It sends:
      - brand identity (colours, fonts, voice, tone)
      - market research (saturation, competitive edge, sentiment)
      - product list (images + metadata)
      - campaign goal + target platforms

    The engine will:
      1. Generate a creative strategy (deterministic, rule-based)
      2. Create product-specific video records (5 products × 3 variants = 15)
      3. Create general-brand video records (3 variants)
      4. Dispatch parallel workers to generate all 18 videos
      5. Return immediately with campaign ID + metadata
    """
    payload = {
        "campaign_name": "Summer Launch 2026",
        "project_id": "project-acme",

        "brand_identity": {
            "brand_name": "Glow Naturals",
            "tagline": "Nature meets science",
            "logo_url": "https://placehold.co/200x200/png?text=Logo",
            "colors": {
                "primary": "#2E8B57",
                "secondary": "#F0F8FF",
                "accent": "#FFD700",
                "background": "#FFFFFF",
                "text": "#1A1A1A"
            },
            "fonts": {
                "heading": "Playfair Display",
                "body": "Lato",
                "accent": "Dancing Script"
            },
            "voice": "warm",
            "tone": "confident",
            "industry": "skincare"
        },

        "market_research": {
            "saturation_percent": 72.0,
            "competitive_edge_percent": 78.0,
            "sentiment": "positive",
            "trending_keywords": ["clean beauty", "vegan skincare", "glass skin"],
            "target_audience_age_min": 22,
            "target_audience_age_max": 45,
            "target_audience_gender": "female"
        },

        "products": [
            {
                "product_name": "Vitamin C Serum",
                "product_image_url": "https://placehold.co/1024x1024/png?text=Vitamin+C+Serum",
                "product_description": "Brightening serum with 20% Vitamin C",
                "product_category": "skincare",
                "product_features": {"key_ingredient": "Vitamin C", "size": "30ml"},
                "price": 34.99,
                "tags": {"is_new": True, "is_bestseller": False}
            },
            {
                "product_name": "Hyaluronic Acid Moisturizer",
                "product_image_url": "https://placehold.co/1024x1024/png?text=HA+Moisturizer",
                "product_description": "Deep hydration for all skin types",
                "product_category": "skincare",
                "price": 42.00,
                "tags": {"is_new": False, "is_bestseller": True}
            },
            {
                "product_name": "Retinol Night Cream",
                "product_image_url": "https://placehold.co/1024x1024/png?text=Retinol+Cream",
                "product_category": "skincare",
                "price": 55.00,
                "tags": {"is_new": True, "is_bestseller": False}
            },
            {
                "product_name": "SPF 50 Sunscreen",
                "product_image_url": "https://placehold.co/1024x1024/png?text=SPF50",
                "product_category": "skincare",
                "price": 28.00,
                "tags": {"is_new": False, "is_bestseller": True}
            },
            {
                "product_name": "Rose Hip Facial Oil",
                "product_image_url": "https://placehold.co/1024x1024/png?text=Rose+Hip+Oil",
                "product_category": "skincare",
                "price": 38.50
            },
        ],

        "campaign_goal": "awareness",
        "platforms": ["instagram_feed", "instagram_story", "tiktok"],
        "duration_preference": 15,
        "product_specific_variants": 3,
        "general_brand_variants": 3,
    }

    resp = httpx.post(f"{BASE_URL}/campaigns", json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    print("=== Campaign Created ===")
    print(f"  Campaign ID    : {data['id']}")
    print(f"  Status         : {data['status']}")
    print(f"  Total products : {data['total_products']}")
    print(f"  Total videos   : {data['total_videos']}")
    print(f"  Platforms      : {data['platforms']}")
    print()
    return data


# ────────────────────────────────────────────────────────────
# 2. Poll Campaign Status
# ────────────────────────────────────────────────────────────

def poll_status(campaign_id: str) -> dict:
    """
    GET /api/v1/campaigns/{id}/status

    Call this every few seconds to get real-time progress.
    """
    resp = httpx.get(
        f"{BASE_URL}/campaigns/{campaign_id}/status",
        headers=HEADERS, timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    print(f"  Status: {data['status']}  |  "
          f"Progress: {data['overall_progress']:.0f}%  |  "
          f"Completed: {data['completed_videos']}/{data['total_videos']}")
    return data


def wait_for_completion(campaign_id: str, timeout: int = 600):
    """Poll until campaign is done or timeout reached."""
    print("=== Waiting for Generation ===")
    start = time.time()
    while time.time() - start < timeout:
        status = poll_status(campaign_id)
        if status["status"] in ("completed", "failed"):
            print()
            return status
        time.sleep(5)
    print("  TIMEOUT – campaign still running")
    return None


# ────────────────────────────────────────────────────────────
# 3. Retrieve Results
# ────────────────────────────────────────────────────────────

def get_results(campaign_id: str) -> dict:
    """
    GET /api/v1/campaigns/{id}/results

    Returns every video, its platform exports, quality scores,
    file paths / download URLs, and campaign summary.
    """
    resp = httpx.get(
        f"{BASE_URL}/campaigns/{campaign_id}/results",
        headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    print("=== Campaign Results ===")
    print(f"  Campaign       : {data['campaign_name']}")
    print(f"  Status         : {data['status']}")
    print(f"  Total videos   : {data['summary']['total_videos']}")
    print(f"  Completed      : {data['summary']['completed_videos']}")
    print(f"  Avg quality    : {data['summary']['average_quality_score']}")
    print()

    # Show product-specific videos
    product_vids = [v for v in data["videos"] if v["video_type"] == "product_specific"]
    brand_vids   = [v for v in data["videos"] if v["video_type"] == "general_brand"]

    print(f"  Product-specific videos: {len(product_vids)}")
    for v in product_vids[:5]:  # show first 5
        print(f"    - {v['product_name']} variant {v['variant_id']}  "
              f"[{v['status']}]  quality={v.get('quality_score', 'N/A')}  "
              f"angle={v['message_angle']}")
        for exp in v.get("exports", []):
            print(f"      {exp['platform']}: {exp['resolution']}  "
                  f"({exp.get('file_size_mb', 0):.1f} MB)")
    if len(product_vids) > 5:
        print(f"    ... and {len(product_vids) - 5} more")

    print(f"\n  General-brand videos: {len(brand_vids)}")
    for v in brand_vids:
        print(f"    - Variant {v['variant_id']}  [{v['status']}]  "
              f"layout={v.get('layout_type', 'N/A')}  "
              f"quality={v.get('quality_score', 'N/A')}")

    print()
    return data


# ────────────────────────────────────────────────────────────
# 4. Regenerate Failed Videos (optional)
# ────────────────────────────────────────────────────────────

def regenerate_failed(campaign_id: str, results: dict):
    """
    POST /api/v1/campaigns/{id}/regenerate

    Send a list of video IDs to re-generate.
    """
    failed_ids = [
        v["video_id"] for v in results.get("videos", [])
        if v["status"] == "failed"
    ]
    if not failed_ids:
        print("  No failed videos to regenerate.")
        return

    resp = httpx.post(
        f"{BASE_URL}/campaigns/{campaign_id}/regenerate",
        json={"video_ids": failed_ids},
        headers=HEADERS, timeout=10,
    )
    resp.raise_for_status()
    print(f"  Regenerating {len(failed_ids)} videos: {resp.json()}")


# ────────────────────────────────────────────────────────────
# 5. List Templates
# ────────────────────────────────────────────────────────────

def list_templates():
    """
    GET /api/v1/templates

    Browse available templates.  Filter by category, style, industry.
    """
    resp = httpx.get(
        f"{BASE_URL}/templates",
        params={"category": "product_hero", "limit": 5},
        headers=HEADERS, timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"=== Templates (showing 5 of {data['total']}) ===")
    for t in data["templates"][:5]:
        print(f"  {t['name']}  |  {t['category']}  |  "
              f"score={t['performance_score']}")
    print()


# ────────────────────────────────────────────────────────────
# 6. List Campaigns for a Project
# ────────────────────────────────────────────────────────────

def list_project_campaigns(project_id: str = "project-acme"):
    """
    GET /api/v1/projects/{project_id}/campaigns

    Retrieve all campaigns belonging to a project.
    """
    resp = httpx.get(
        f"{BASE_URL}/projects/{project_id}/campaigns",
        headers=HEADERS, timeout=10,
    )
    resp.raise_for_status()
    campaigns = resp.json()
    print(f"=== Campaigns for {project_id} ({len(campaigns)} total) ===")
    for c in campaigns:
        print(f"  {c['campaign_name']}  |  {c['status']}  |  "
              f"videos={c['total_videos']}  progress={c['overall_progress']:.0f}%")
    print()


# ────────────────────────────────────────────────────────────
# cURL equivalents (for non-Python backends)
# ────────────────────────────────────────────────────────────

CURL_EXAMPLES = """
==========================================================================
 cURL EXAMPLES (copy-paste for any backend)
==========================================================================

# 1. Create campaign
curl -X POST http://localhost:8000/api/v1/campaigns \\
  -H "X-API-Key: my-secret-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "campaign_name": "Summer Launch 2026",
    "project_id": "project-acme",
    "brand_identity": {
      "brand_name": "Glow Naturals",
      "colors": { "primary": "#2E8B57", "secondary": "#F0F8FF", "background": "#FFFFFF", "text": "#1A1A1A" },
      "fonts": { "heading": "Playfair Display", "body": "Lato" },
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
      { "product_name": "Vitamin C Serum", "product_image_url": "https://example.com/serum.png", "product_category": "skincare", "price": 34.99, "tags": {"is_new": true} },
      { "product_name": "Moisturizer", "product_image_url": "https://example.com/moisturizer.png", "product_category": "skincare" }
    ],
    "campaign_goal": "awareness",
    "platforms": ["instagram_feed", "tiktok"],
    "duration_preference": 15
  }'

# 2. Poll status
curl http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/status \\
  -H "X-API-Key: my-secret-api-key"

# 3. Get results
curl http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/results \\
  -H "X-API-Key: my-secret-api-key"

# 4. Regenerate failed videos
curl -X POST http://localhost:8000/api/v1/campaigns/{CAMPAIGN_ID}/regenerate \\
  -H "X-API-Key: my-secret-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{"video_ids": ["VIDEO_ID_1", "VIDEO_ID_2"]}'

# 5. List templates
curl 'http://localhost:8000/api/v1/templates?category=product_hero&limit=10' \\
  -H "X-API-Key: my-secret-api-key"

# 6. List project campaigns
curl http://localhost:8000/api/v1/projects/project-acme/campaigns \\
  -H "X-API-Key: my-secret-api-key"
"""


# ────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(CURL_EXAMPLES)
    print()
    print("Running Python integration example...")
    print("=" * 60)

    try:
        # Step 1 – create campaign
        campaign = create_campaign()
        cid = campaign["id"]

        # Step 2 – poll until done
        wait_for_completion(cid, timeout=600)

        # Step 3 – get results
        results = get_results(cid)

        # Step 4 – regenerate any failures
        regenerate_failed(cid, results)

        # Step 5 – list templates
        list_templates()

        # Step 6 – list project campaigns
        list_project_campaigns()

    except httpx.ConnectError:
        print("\nERROR: Cannot connect to API at", BASE_URL)
        print("Make sure the engine is running: docker compose up -d")
    except httpx.HTTPStatusError as e:
        print(f"\nHTTP Error: {e.response.status_code} – {e.response.text}")
