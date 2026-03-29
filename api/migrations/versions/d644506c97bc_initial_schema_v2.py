"""initial_schema_v2

Revision ID: d644506c97bc
Revises:
Create Date: 2026-03-29 19:58:26.629658

ScholarGuard Version 2 initial database schema.
14 tables covering: users, organizations, documents, detection results,
review/appeal/feedback, system config, prompt versions, formula params,
usage stats, audit logs, eval samples, webhooks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd644506c97bc'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all Version 2 tables."""

    # Use Base.metadata.create_all logic via op.
    # We generate the tables using the ORM models.
    from app.models.base import Base
    from app.models import user, document, detection, review, system, dataset  # noqa

    # Create all tables respecting FK order
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    # Create additional indexes not in the ORM
    op.create_index('idx_detection_risk_created', 'detection_results', ['risk_level', 'created_at'])
    op.create_index('idx_feedback_unprocessed', 'feedbacks', ['processed'],
                    postgresql_where=sa.text('processed = false'))
    op.create_index('idx_appeal_status', 'appeal_records', ['status'])
    op.create_index('idx_eval_samples_version_source', 'eval_samples', ['dataset_version', 'source_type'])
    op.create_index('idx_usage_user_month', 'usage_stats', ['user_id', 'created_at'])
    op.create_index('idx_audit_user_time', 'audit_logs', ['user_id', 'created_at'])

    # Seed default formula params
    op.execute(
        sa.text("""
            INSERT INTO formula_params (id, version, params, description, is_active, created_at)
            VALUES (
                gen_random_uuid(),
                'v1.1',
                '{"w1": 0.70, "w2": 0.20, "w3": 0.00, "w4": 0.00, "w5": 0.10, "a": 0.50, "b": 0.30, "c": 0.20, "threshold_low": 0.30, "threshold_medium": 0.50, "threshold_high": 0.70}',
                'Phase 1 默认参数：LLM权重0.70，统计权重0.20，人工信用0.10',
                true,
                now()
            )
        """)
    )


def downgrade() -> None:
    """Drop all Version 2 tables in reverse FK order."""
    tables = [
        'webhooks', 'prompt_versions', 'formula_params',
        'audit_logs', 'usage_stats', 'model_configs',
        'eval_samples', 'feedbacks', 'appeal_records',
        'review_records', 'detection_results', 'documents',
        'users', 'organizations',
    ]
    for table in tables:
        op.drop_table(table)
