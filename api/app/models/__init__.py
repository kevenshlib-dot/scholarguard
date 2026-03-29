"""ScholarGuard ORM models package.

Imports every model so that ``Base.metadata`` sees all tables and
Alembic autogenerate works out of the box.
"""

from app.models.base import (
    Base,
    close_db,
    get_async_session,
    init_db,
)
from app.models.dataset import EvalSample
from app.models.detection import DetectionResult
from app.models.document import Document
from app.models.review import (
    AppealRecord,
    AppealStatus,
    Feedback,
    FeedbackType,
    ReviewLabel,
    ReviewRecord,
)
from app.models.system import (
    AuditLog,
    FormulaParam,
    ModelConfig,
    PromptVersion,
    UsageStat,
    Webhook,
)
from app.models.user import Organization, User, UserRole

__all__ = [
    # base
    "Base",
    "init_db",
    "close_db",
    "get_async_session",
    # user
    "Organization",
    "User",
    "UserRole",
    # document
    "Document",
    # detection
    "DetectionResult",
    # review
    "ReviewRecord",
    "ReviewLabel",
    "AppealRecord",
    "AppealStatus",
    "Feedback",
    "FeedbackType",
    # system
    "ModelConfig",
    "UsageStat",
    "AuditLog",
    "PromptVersion",
    "FormulaParam",
    "Webhook",
    # dataset
    "EvalSample",
]
