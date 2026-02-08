"""Add campaign_static_ads table for static ad image generation.

Revision ID: 002
Revises: 001
Create Date: 2026-02-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── campaign_static_ads ───────────────────────────────
    op.create_table(
        "campaign_static_ads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaign_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Type and variant
        sa.Column("ad_type", sa.String(32), nullable=False),
        sa.Column("variant_id", sa.Integer, nullable=False),
        sa.Column("variant_type", sa.String(32), nullable=False),
        sa.Column("message_angle", sa.String(32), nullable=False),
        # Template reference
        sa.Column("static_template_id", sa.String(128), nullable=True),
        sa.Column("static_template_name", sa.String(256), nullable=True),
        # Messaging
        sa.Column("headline", sa.String(512), nullable=True),
        sa.Column("subheading", sa.String(512), nullable=True),
        sa.Column("cta_text", sa.String(128), nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        # User-provided image
        sa.Column("image_url", sa.Text, nullable=True),
        # Status and output
        sa.Column("status", sa.String(32), server_default="queued"),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("thumbnail_path", sa.Text, nullable=True),
        sa.Column("file_size_mb", sa.Float, nullable=True),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        # Template config and metadata
        sa.Column("template_config", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_static_ads_campaign", "campaign_static_ads", ["campaign_id"])
    op.create_index("ix_campaign_static_ads_product", "campaign_static_ads", ["product_id"])
    op.create_index("ix_campaign_static_ads_status", "campaign_static_ads", ["status"])


def downgrade() -> None:
    op.drop_table("campaign_static_ads")
