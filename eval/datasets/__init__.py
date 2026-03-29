"""
ScholarGuard evaluation dataset package.

Provides seed sample generation and database loading utilities
for calibrating the AI detection system.
"""

from .seed_samples import generate_all_samples, DISCIPLINES, SOURCE_TYPES
from .load_dataset import load_samples_to_db

__all__ = [
    "generate_all_samples",
    "load_samples_to_db",
    "DISCIPLINES",
    "SOURCE_TYPES",
]
