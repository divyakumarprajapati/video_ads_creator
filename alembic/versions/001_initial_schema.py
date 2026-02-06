"""Initial schema – all core tables.

Revision ID: 001
Revises: None
Create Date: 2026-02-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── video_templates ────────────────────────────────────
    op.create_table(
        "video_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("subcategory", sa.String(64), nullable=True),
        sa.Column("template_spec", JSONB, server_default="{}"),
        sa.Column("compatible_visual_styles", JSONB, server_default="[]"),
        sa.Column("compatible_video_styles", JSONB, server_default="[]"),
        sa.Column("compatible_industries", JSONB, server_default="[]"),
        sa.Column("requires_product_image", sa.Boolean, server_default="true"),
        sa.Column("requires_background", sa.Boolean, server_default="false"),
        sa.Column("min_duration", sa.Integer, server_default="5"),
        sa.Column("max_duration", sa.Integer, server_default="30"),
        sa.Column("supported_aspect_ratios", JSONB, server_default='["1:1","9:16"]'),
        sa.Column("performance_score", sa.Float, server_default="50.0"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_video_templates_category", "video_templates", ["category"])

    # ── campaigns ──────────────────────────────────────────
    op.create_table(
        "campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("campaign_name", sa.String(256), nullable=False),
        sa.Column("campaign_goal", sa.String(32), server_default="awareness"),
        sa.Column("platforms", JSONB, server_default="[]"),
        sa.Column("duration_preference", sa.Integer, server_default="15"),
        sa.Column("brand_identity", JSONB, server_default="{}"),
        sa.Column("market_research", JSONB, server_default="{}"),
        sa.Column("product_specific_variants", sa.Integer, server_default="3"),
        sa.Column("general_brand_variants", sa.Integer, server_default="3"),
        sa.Column("strategy_plan", JSONB, nullable=True),
        sa.Column("status", sa.String(32), server_default="draft"),
        sa.Column("overall_progress", sa.Float, server_default="0"),
        sa.Column("estimated_completion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_campaigns_project_id", "campaigns", ["project_id"])
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"])
    op.create_index("ix_campaigns_status", "campaigns", ["status"])
    op.create_index("ix_campaigns_created_at", "campaigns", ["created_at"])

    # ── campaign_products ──────────────────────────────────
    op.create_table(
        "campaign_products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_name", sa.String(256), nullable=False),
        sa.Column("product_image_url", sa.Text, nullable=False),
        sa.Column("product_description", sa.Text, nullable=True),
        sa.Column("product_category", sa.String(128), nullable=True),
        sa.Column("product_features", JSONB, nullable=True),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("creative_plan", JSONB, nullable=True),
        sa.Column("generation_status", sa.String(32), server_default="pending"),
        sa.Column("progress", sa.Float, server_default="0"),
        sa.Column("processed_image_path", sa.Text, nullable=True),
        sa.Column("background_removed_path", sa.Text, nullable=True),
        sa.Column("upscaled_image_path", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_products_campaign", "campaign_products", ["campaign_id"])

    # ── campaign_videos ────────────────────────────────────
    op.create_table(
        "campaign_videos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("campaign_products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("video_type", sa.String(32), nullable=False),
        sa.Column("variant_id", sa.Integer, nullable=False),
        sa.Column("variant_type", sa.String(32), nullable=False),
        sa.Column("message_angle", sa.String(32), nullable=False),
        sa.Column("primary_message", sa.String(512), nullable=True),
        sa.Column("secondary_message", sa.String(512), nullable=True),
        sa.Column("cta_text", sa.String(128), nullable=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("video_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("layout_type", sa.String(32), nullable=True),
        sa.Column("products_shown", JSONB, nullable=True),
        sa.Column("status", sa.String(32), server_default="queued"),
        sa.Column("generation_progress", sa.Float, server_default="0"),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_size_mb", sa.Float, nullable=True),
        sa.Column("thumbnail_path", sa.Text, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_videos_campaign", "campaign_videos", ["campaign_id"])
    op.create_index("ix_campaign_videos_product", "campaign_videos", ["product_id"])
    op.create_index("ix_campaign_videos_status", "campaign_videos", ["status"])

    # ── campaign_platform_exports ──────────────────────────
    op.create_table(
        "campaign_platform_exports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", UUID(as_uuid=True), sa.ForeignKey("campaign_videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("file_size_mb", sa.Float, nullable=True),
        sa.Column("resolution", sa.String(32), nullable=True),
        sa.Column("aspect_ratio", sa.String(16), nullable=True),
        sa.Column("public_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("campaign_platform_exports")
    op.drop_table("campaign_videos")
    op.drop_table("campaign_products")
    op.drop_table("campaigns")
    op.drop_table("video_templates")
