"""add_detection_status_batch_fields

Revision ID: 23d0aa4374b2
Revises: d644506c97bc
Create Date: 2026-03-29 21:54:22.167249

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23d0aa4374b2'
down_revision: Union[str, Sequence[str], None] = 'd644506c97bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('detection_results', sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'"), nullable=False, comment='pending | processing | completed | failed'))
    op.add_column('detection_results', sa.Column('error_message', sa.Text(), nullable=True, comment='Error details when status is failed'))
    op.add_column('detection_results', sa.Column('batch_id', sa.String(length=36), nullable=True, comment='UUID of the batch this belongs to'))
    op.create_index(op.f('ix_detection_results_batch_id'), 'detection_results', ['batch_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_detection_results_batch_id'), table_name='detection_results')
    op.drop_column('detection_results', 'batch_id')
    op.drop_column('detection_results', 'error_message')
    op.drop_column('detection_results', 'status')
