"""Auto-Healing Pipeline — phát hiện vi phạm GX/Freshness và tự sửa chữa."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _needs_repair(quality: dict, freshness: dict) -> tuple[bool, list[str]]:
    reasons = []
    if not quality.get("success", True):
        failed = [
            r["expectation"] for r in quality.get("results", []) if not r["success"]
        ]
        reasons.append(f"GX violations: {', '.join(failed)}")
    if not freshness.get("is_fresh", True):
        reasons.append(
            f"Freshness SLA breach: stale_ratio={freshness.get('stale_ratio', 0):.1%}"
        )
    return bool(reasons), reasons


def main() -> None:
    settings = load_settings()
    run_date = datetime.now(timezone.utc)

    print("=== Auto-Healing Pipeline ===")
    print("Step 1: Loading current clean data...")

    if not settings.paths.clean_json.exists():
        print("  No clean data found — running full ingestion from raw snapshot.")
        raw = load_raw_records(settings.paths.raw_records_json)
        df = build_clean_dataframe(raw, run_date)
        write_csv(df, settings.paths.clean_csv)
        write_json(settings.paths.clean_json, df.to_dict(orient="records"))
    else:
        df = pd.read_json(settings.paths.clean_json)

    print(f"  Loaded {len(df)} rows.")

    print("Step 2: Running quality checks...")
    quality   = run_data_quality_checks(df, settings, "baseline_quality_report")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    needs_fix, reasons = _needs_repair(quality, freshness)

    if not needs_fix:
        print("  ✅ All checks pass — no repair needed.")
    else:
        print(f"  ❌ Issues detected:")
        for r in reasons:
            print(f"     • {r}")
        print()
        print("Step 3: Auto-repair triggered — rebuilding from raw snapshot...")

        raw = load_raw_records(settings.paths.raw_records_json)
        df  = build_clean_dataframe(raw, run_date)
        write_csv(df, settings.paths.clean_csv)
        write_json(settings.paths.clean_json, df.to_dict(orient="records"))
        print(f"  Rebuilt: {len(df)} rows from raw snapshot.")

        print("Step 4: Re-running quality checks post-repair...")
        quality   = run_data_quality_checks(df, settings, "baseline_quality_report")
        freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

        still_broken, remaining = _needs_repair(quality, freshness)
        if still_broken:
            print("  ⚠️  Issues persist after repair:")
            for r in remaining:
                print(f"     • {r}")
            print("  Manual investigation required.")
            sys.exit(1)
        else:
            print("  ✅ Repair successful — all checks pass.")

    print("Step 5: Rebuilding index and evaluating...")
    index = LocalEmbeddingIndex.build(df, settings, settings.paths.baseline_embeddings_json)
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    m = bundle.summary
    print(f"  hit_rate={m['retrieval_hit_rate']:.4f}  token_f1={m['mean_token_f1']:.4f}")

    generate_phase1_report(
        report_path=settings.paths.phase1_report,
        source_summary={"record_count": len(df), "source": "auto-heal pipeline"},
        metrics=m,
        quality=quality,
        freshness=freshness,
    )

    print(f"\nReport → {settings.paths.phase1_report}")
    print("=== Auto-Heal Complete ===")


if __name__ == "__main__":
    main()
