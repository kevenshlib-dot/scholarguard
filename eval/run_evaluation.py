"""
ScholarGuard 评测运行器

从 seed_samples 加载样本，通过 DetectionEngine 检测，
计算指标（eval/metrics.py），并将结果保存到 eval/results/。

用法:
    python -m eval.run_evaluation
    python -m eval.run_evaluation --sample-count 50
    python -m eval.run_evaluation --dry-run
    python -m eval.run_evaluation --threshold 0.6 --output eval/results/custom.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Ensure the project root is on sys.path so both `eval.*` and `api.*` imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from eval.datasets.seed_samples import generate_all_samples, SeedSample
from eval.metrics import EvalResult, compute_metrics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Detection wrapper
# ---------------------------------------------------------------------------

async def _detect_single(
    engine,
    sample: SeedSample,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Run detection on a single sample with concurrency control."""
    async with semaphore:
        try:
            result = await engine.detect(
                text=sample.text_content,
                granularity="document",
                language="zh",
                discipline=sample.discipline,
            )
            risk_score = result.get("risk_score", result.get("score", 0.0))
            return {
                "ground_truth": sample.ground_truth_label,
                "risk_score": risk_score,
                "discipline": sample.discipline,
                "source_type": sample.source_type,
                "text_hash": sample.text_hash,
                "raw_result": result,
                "error": None,
            }
        except Exception as exc:
            logger.warning(
                "Detection failed for sample %s: %s", sample.text_hash[:12], exc
            )
            return {
                "ground_truth": sample.ground_truth_label,
                "risk_score": 0.0,
                "discipline": sample.discipline,
                "source_type": sample.source_type,
                "text_hash": sample.text_hash,
                "raw_result": None,
                "error": str(exc),
            }


async def _detect_batch(
    engine,
    samples: list[SeedSample],
    concurrency: int = 5,
) -> list[dict]:
    """Run detection on all samples with bounded concurrency."""
    sem = asyncio.Semaphore(concurrency)
    tasks = [_detect_single(engine, s, sem) for s in samples]
    return await asyncio.gather(*tasks)


def _build_engine():
    """
    Attempt to build a DetectionEngine. Falls back gracefully if
    the API dependencies are not available (e.g. missing env vars).
    """
    try:
        from api.app.services.detection.engine import DetectionEngine
        from api.app.services.detection.fusion import FormulaParams
        from api.app.services.llm_gateway.client import LLMClient

        llm_client = LLMClient()
        engine = DetectionEngine(llm_client=llm_client)
        return engine
    except Exception as exc:
        logger.error("Could not initialise DetectionEngine: %s", exc)
        raise RuntimeError(
            "DetectionEngine unavailable. Ensure API dependencies are installed "
            "and environment variables (LLM API keys, etc.) are configured. "
            f"Original error: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Dry-run mode: assign synthetic scores based on source_type
# ---------------------------------------------------------------------------

def _dry_run_predictions(samples: list[SeedSample]) -> list[dict]:
    """
    Generate synthetic predictions for dry-run mode.
    Human samples get low scores, AI samples get high scores,
    with some noise to simulate realistic imperfection.
    """
    import random

    rng = random.Random(123)
    predictions = []

    score_ranges = {
        "human_original":       (0.05, 0.30),
        "ai_generated":         (0.70, 0.98),
        "ai_human_edited":      (0.40, 0.80),
        "humanizer_processed":  (0.30, 0.70),
    }

    for sample in samples:
        lo, hi = score_ranges.get(sample.source_type, (0.3, 0.7))
        score = rng.uniform(lo, hi)
        predictions.append({
            "ground_truth": sample.ground_truth_label,
            "risk_score": round(score, 4),
            "discipline": sample.discipline,
            "source_type": sample.source_type,
            "text_hash": sample.text_hash,
            "raw_result": None,
            "error": None,
        })

    return predictions


# ---------------------------------------------------------------------------
# Main evaluation flow
# ---------------------------------------------------------------------------

async def run_evaluation(
    sample_count: Optional[int] = None,
    dry_run: bool = False,
    threshold: float = 0.5,
    concurrency: int = 5,
    seed: int = 42,
    output_path: Optional[str] = None,
) -> EvalResult:
    """
    Execute a full evaluation run.

    Args:
        sample_count: If set, randomly subsample to this count
        dry_run: Use synthetic scores instead of real detection
        threshold: Risk-score threshold for AI classification
        concurrency: Max concurrent detection requests
        seed: Random seed for sample generation
        output_path: Where to save the JSON result

    Returns:
        EvalResult dataclass with all metrics
    """
    import random

    # 1. Generate / load samples
    logger.info("Generating seed samples (seed=%d)...", seed)
    all_samples = generate_all_samples(seed=seed)

    if sample_count and sample_count < len(all_samples):
        rng = random.Random(seed)
        samples = rng.sample(all_samples, sample_count)
        logger.info("Subsampled to %d samples", len(samples))
    else:
        samples = all_samples

    logger.info("Evaluation on %d samples (dry_run=%s, threshold=%.2f)",
                len(samples), dry_run, threshold)

    # 2. Run detection
    start = time.time()

    if dry_run:
        predictions = _dry_run_predictions(samples)
    else:
        engine = _build_engine()
        predictions = await _detect_batch(engine, samples, concurrency)

    elapsed = time.time() - start
    error_count = sum(1 for p in predictions if p["error"] is not None)
    logger.info(
        "Detection complete: %.1fs elapsed, %d errors out of %d samples",
        elapsed, error_count, len(predictions),
    )

    # 3. Compute metrics
    metrics = compute_metrics(predictions, threshold=threshold)

    # 4. Build EvalResult
    eval_id = f"eval_{uuid.uuid4().hex[:12]}"
    result = EvalResult(
        eval_id=eval_id,
        dataset_version="v1.0",
        formula_version="v1.0",
        param_version="default",
        model_version="dry_run" if dry_run else "live",
        prompt_version="v1.0",
        total_samples=metrics["total_samples"],
        precision=metrics["overall"]["precision"],
        recall=metrics["overall"]["recall"],
        f1=metrics["overall"]["f1"],
        false_positive_rate=metrics["overall"]["false_positive_rate"],
        false_negative_rate=metrics["overall"]["false_negative_rate"],
        discipline_metrics=metrics["by_discipline"],
        source_type_metrics=metrics["by_source_type"],
        confusion_matrix=metrics["confusion_matrix"],
    )

    # 5. Save results
    if output_path is None:
        results_dir = Path(__file__).resolve().parent / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        mode_tag = "dryrun" if dry_run else "live"
        output_path = str(results_dir / f"{eval_id}_{mode_tag}_{timestamp}.json")

    result.save(output_path)
    logger.info("Results saved to %s", output_path)

    # Also save raw predictions alongside the metrics
    raw_path = output_path.replace(".json", "_predictions.json")
    serializable_preds = []
    for p in predictions:
        entry = {k: v for k, v in p.items() if k != "raw_result"}
        serializable_preds.append(entry)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(serializable_preds, f, ensure_ascii=False, indent=2)
    logger.info("Raw predictions saved to %s", raw_path)

    # 6. Print summary
    _print_summary(result, elapsed, error_count)

    return result


def _print_summary(result: EvalResult, elapsed: float, errors: int) -> None:
    """Print a human-readable evaluation summary to stdout."""
    print("\n" + "=" * 60)
    print(f"  ScholarGuard Evaluation Report: {result.eval_id}")
    print("=" * 60)
    print(f"  Samples:    {result.total_samples}")
    print(f"  Model:      {result.model_version}")
    print(f"  Time:       {elapsed:.1f}s")
    print(f"  Errors:     {errors}")
    print()
    print("  Overall Metrics:")
    print(f"    Precision:  {result.precision:.4f}")
    print(f"    Recall:     {result.recall:.4f}")
    print(f"    F1:         {result.f1:.4f}")
    print(f"    FPR:        {result.false_positive_rate:.4f}")
    print(f"    FNR:        {result.false_negative_rate:.4f}")

    if result.discipline_metrics:
        print()
        print("  By Discipline:")
        for disc, m in sorted(result.discipline_metrics.items()):
            print(f"    {disc:8s}  P={m['precision']:.3f}  R={m['recall']:.3f}  "
                  f"F1={m['f1']:.3f}  n={m['samples']}")

    if result.source_type_metrics:
        print()
        print("  By Source Type:")
        for src, m in sorted(result.source_type_metrics.items()):
            print(f"    {src:24s}  P={m['precision']:.3f}  R={m['recall']:.3f}  "
                  f"F1={m['f1']:.3f}  n={m['samples']}")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ScholarGuard evaluation runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m eval.run_evaluation --dry-run
  python -m eval.run_evaluation --sample-count 100 --threshold 0.6
  python -m eval.run_evaluation --output eval/results/my_run.json
        """,
    )
    parser.add_argument(
        "--sample-count", "-n",
        type=int,
        default=None,
        help="Number of samples to evaluate (default: all 550)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use synthetic scores instead of running real detection",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.5,
        help="Risk-score threshold for AI classification (default: 0.5)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=5,
        help="Max concurrent detection requests (default: 5)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sample generation (default: 42)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output path for results JSON",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(
        run_evaluation(
            sample_count=args.sample_count,
            dry_run=args.dry_run,
            threshold=args.threshold,
            concurrency=args.concurrency,
            seed=args.seed,
            output_path=args.output,
        )
    )


if __name__ == "__main__":
    main()
