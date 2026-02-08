"""Add product image URL lists for static ad rotation.

Revision ID: 003
Revises: 002
Create Date: 2026-02-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaign_products", sa.Column("product_image_urls", JSONB, nullable=True))
    op.add_column("campaign_products", sa.Column("image_urls", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("campaign_products", "image_urls")
    op.drop_column("campaign_products", "product_image_urls")
