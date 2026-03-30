"""add nhpr columns

Revision ID: a1b2c3d4e5f6
Revises: d742e87f5a1f
Create Date: 2026-03-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd742e87f5a1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('detection_results', sa.Column('nhpr_score', sa.Float(), nullable=True, server_default='0.0', comment='Non-Human Pattern Ratio score (0-1)'))
    op.add_column('detection_results', sa.Column('nhpr_level', sa.String(length=20), nullable=True, server_default="low", comment='NHPR risk classification: low/medium/high/critical'))


def downgrade() -> None:
    op.drop_column('detection_results', 'nhpr_level')
    op.drop_column('detection_results', 'nhpr_score')
