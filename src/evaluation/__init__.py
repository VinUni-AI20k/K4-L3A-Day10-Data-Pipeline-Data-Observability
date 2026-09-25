<<<<<<< HEAD
from .testset import BenchmarkTestSet, build_test_set, load_or_create_test_set

__all__ = [
    "build_test_set",
    "load_or_create_test_set",
    "BenchmarkTestSet",
    "EvaluationBundle",
    "JudgeVerdict",
    "evaluate_pipeline",
]


def __getattr__(name):
    """Avoid loading the optional PyArrow/Ragas stack for test-set creation."""
    if name in {"EvaluationBundle", "JudgeVerdict", "evaluate_pipeline"}:
        from . import metrics

        return getattr(metrics, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
=======
"""Load public exports lazily so indexing does not require LLM providers."""

from importlib import import_module

_EXPORTS = {'EvaluationBundle': 'metrics', 'JudgeVerdict': 'metrics', 'evaluate_pipeline': 'metrics', 'BenchmarkTestSet': 'testset', 'build_test_set': 'testset', 'load_or_create_test_set': 'testset'}
__all__ = list(_EXPORTS)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{_EXPORTS[name]}"), name)
    globals()[name] = value
    return value
>>>>>>> a42a52f (feat: complete Day 10 data pipeline, observability and repair flow)
