"""Run with PYTHONPATH=src python script/smoke_checkpoint2.py."""
import pandas as pd

from core.config import load_settings
from core.utils import read_json
from evaluation.testset import load_or_create_test_set
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    df = pd.DataFrame(read_json(settings.paths.clean_json))
    benchmark = load_or_create_test_set(df, settings.paths.eval_testset)
    assert len(benchmark.samples) == 5
    index = LocalEmbeddingIndex(settings)
    count = index.build_from_clean()
    assert count == df['paper_id'].nunique()
    assert index.build_from_clean() == count
    assert index.collection.count() == count
    results = index.semantic_search(df.iloc[0]['title'], top_k=2)
    assert len(results) == min(2, count)
    assert df.iloc[0]['paper_id'] in [r['paper_id'] for r in results]
    reopened = LocalEmbeddingIndex(settings)
    assert reopened.collection.count() == count
    assert reopened.semantic_search(df.iloc[0]['title'])[0]['paper_id'] == results[0]['paper_id']
    print(f'PASS: {len(benchmark.samples)} benchmark samples; {count} documents indexed; idempotence, persistence and semantic search verified.')
    for result in results:
        print(result['paper_id'], f"distance={result['distance']:.4f}")


if __name__ == '__main__':
    main()
