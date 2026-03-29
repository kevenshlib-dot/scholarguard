"""add_heatmap_fields

Revision ID: d742e87f5a1f
Revises: 23d0aa4374b2
Create Date: 2026-03-29 23:24:25.510146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd742e87f5a1f'
down_revision: Union[str, Sequence[str], None] = '23d0aa4374b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('detection_results', sa.Column('paragraph_heatmap', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='Paragraph-level risk heatmap data'))
    op.add_column('detection_results', sa.Column('heatmap_status', sa.String(length=20), server_default=sa.text("'not_requested'"), nullable=True, comment='not_requested | pending | completed'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('detection_results', 'heatmap_status')
    op.drop_column('detection_results', 'paragraph_heatmap')
