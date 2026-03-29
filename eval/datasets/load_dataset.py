"""
将种子评测样本加载到 PostgreSQL eval_samples 表。

用法:
    python -m eval.datasets.load_dataset [--db-url URL] [--version v1.0]
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
from typing import Optional

from eval.datasets.seed_samples import generate_all_samples, SeedSample

logger = logging.getLogger(__name__)

DEFAULT_DB_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/scholarguard"
)


async def load_samples_to_db(
    db_url: Optional[str] = None,
    dataset_version: str = "v1.0",
    seed: int = 42,
    *,
    replace_existing: bool = False,
) -> dict:
    """
    生成种子样本并写入 eval_samples 表。

    Args:
        db_url: 数据库连接URL，默认从环境变量 DATABASE_URL 读取
        dataset_version: 数据集版本标识
        seed: 随机种子
        replace_existing: 若为 True 则先删除同版本旧数据再插入

    Returns:
        包含 inserted / skipped / errors 计数的字典
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    url = db_url or os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

    engine = create_async_engine(url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    samples = generate_all_samples(seed=seed)
    logger.info("Generated %d seed samples (version=%s)", len(samples), dataset_version)

    stats = {"inserted": 0, "skipped": 0, "errors": 0}

    async with session_factory() as session:
        try:
            # 如果要求替换，先清除旧版本数据
            if replace_existing:
                delete_result = await session.execute(
                    text(
                        "DELETE FROM eval_samples WHERE dataset_version = :ver"
                    ),
                    {"ver": dataset_version},
                )
                deleted = delete_result.rowcount
                logger.info("Deleted %d existing samples for version %s", deleted, dataset_version)

            # 检查已有哈希，避免重复插入
            existing_result = await session.execute(
                text(
                    "SELECT text_hash FROM eval_samples "
                    "WHERE dataset_version = :ver"
                ),
                {"ver": dataset_version},
            )
            existing_hashes = {row[0] for row in existing_result.fetchall()}

            for sample in samples:
                if sample.text_hash in existing_hashes:
                    stats["skipped"] += 1
                    continue

                try:
                    await session.execute(
                        text("""
                            INSERT INTO eval_samples (
                                text_content, text_hash, source_type,
                                discipline, language, word_count,
                                ground_truth_label, annotation_confidence,
                                dataset_version
                            ) VALUES (
                                :text_content, :text_hash, :source_type,
                                :discipline, :language, :word_count,
                                :ground_truth_label, :annotation_confidence,
                                :dataset_version
                            )
                        """),
                        {
                            "text_content": sample.text_content,
                            "text_hash": sample.text_hash,
                            "source_type": sample.source_type,
                            "discipline": sample.discipline,
                            "language": "zh",
                            "word_count": len(sample.text_content),
                            "ground_truth_label": sample.ground_truth_label,
                            "annotation_confidence": sample.annotation_confidence,
                            "dataset_version": dataset_version,
                        },
                    )
                    stats["inserted"] += 1
                except Exception as exc:
                    logger.warning("Failed to insert sample (hash=%s): %s", sample.text_hash[:12], exc)
                    stats["errors"] += 1

            await session.commit()
            logger.info(
                "Load complete: inserted=%d, skipped=%d, errors=%d",
                stats["inserted"], stats["skipped"], stats["errors"],
            )
        except Exception:
            await session.rollback()
            raise
        finally:
            await engine.dispose()

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load seed samples into PostgreSQL")
    parser.add_argument(
        "--db-url",
        default=None,
        help="Database URL (default: $DATABASE_URL or built-in default)",
    )
    parser.add_argument("--version", default="v1.0", help="Dataset version tag")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--replace", action="store_true", help="Delete existing samples for this version first"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    result = asyncio.run(
        load_samples_to_db(
            db_url=args.db_url,
            dataset_version=args.version,
            seed=args.seed,
            replace_existing=args.replace,
        )
    )
    print(f"Done: {result}")
