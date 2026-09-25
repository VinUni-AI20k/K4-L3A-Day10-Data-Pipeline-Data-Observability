from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .metrics import EvaluationBundle, JudgeVerdict, evaluate_pipeline
    from .testset import BenchmarkTestSet, build_test_set, load_or_create_test_set

__all__ = [
    "BenchmarkTestSet",
    "EvaluationBundle",
    "JudgeVerdict",
    "build_test_set",
    "evaluate_pipeline",
    "load_or_create_test_set",
]


def __getattr__(name: str):
    if name in {"EvaluationBundle", "JudgeVerdict", "evaluate_pipeline"}:
        from . import metrics

        return getattr(metrics, name)
    if name in {"BenchmarkTestSet", "build_test_set", "load_or_create_test_set"}:
        from . import testset

        return getattr(testset, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
