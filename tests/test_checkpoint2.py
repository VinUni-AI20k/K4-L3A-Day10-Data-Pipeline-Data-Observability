import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from core.config import load_settings
from core.utils import write_json
from evaluation.testset import BenchmarkTestSet, build_test_set, load_or_create_test_set
from retrieval.index import LocalEmbeddingIndex


class Checkpoint2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        settings = load_settings()
        self.settings = replace(settings, paths=replace(settings.paths,
            chroma_dir=root / 'chroma', clean_json=root / 'clean.json',
            clean_csv=root / 'clean.csv', embeddings_json=root / 'embeddings.json'))
        self.path = root / 'test_set.json'
        self.df = pd.DataFrame([
            {'paper_id': '10.1/medical', 'title': 'Cancer diagnosis', 'summary': 'Clinical diagnosis of cancer using medical images.',
             'authors': ['Alice', 'Bob'], 'categories': ['Medicine'], 'published': '2026-01-15',
             'text_for_embedding': 'Cancer diagnosis. Clinical diagnosis of cancer using medical images.'},
            {'paper_id': '10.1/finance', 'title': 'Stock market prediction', 'summary': 'Forecasting stock market prices and financial investment returns.',
             'authors': ['Carol'], 'categories': ['Finance'], 'published': '2026-02-20',
             'text_for_embedding': 'Stock market prediction. Forecasting stock market prices and financial investment returns.'},
        ])

    def test_create_and_load_frozen_benchmark(self):
        benchmark = load_or_create_test_set(self.df, self.path)
        self.assertEqual(len(benchmark.samples), 5)
        self.assertEqual({s['type'] for s in benchmark.samples}, {'summary','authors','date','category','multi_hop'})
        self.assertEqual(benchmark.samples[-1]['ground_truth_doc_ids'], ['10.1/medical','10.1/finance'])
        self.assertEqual(benchmark.samples[2]['ground_truth'], '2026-01')
        before = self.path.read_bytes()
        self.assertEqual(load_or_create_test_set(pd.DataFrame(), self.path), benchmark)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(json.loads(before), benchmark.samples)

    def test_invalid_existing_file_is_not_replaced(self):
        self.path.write_text('[]')
        with self.assertRaises(ValueError):
            load_or_create_test_set(self.df, self.path)
        self.assertEqual(self.path.read_text(), '[]')
        with self.assertRaises(ValueError):
            build_test_set(self.df.head(1), self.path)

    def test_missing_categories_are_not_invented(self):
        samples = build_test_set(self.df.drop(columns='categories'), self.path)
        self.assertIn('not provided', samples[3]['ground_truth'])
        samples[-1]['ground_truth_doc_ids'] = ['10.1/medical']
        with self.assertRaises(ValueError):
            BenchmarkTestSet(samples)

    def test_real_minilm_chroma_persistence_upsert_and_search(self):
        write_json(self.settings.paths.clean_json, self.df.to_dict(orient='records'))
        index = LocalEmbeddingIndex(self.settings)
        self.assertEqual(index.semantic_search('cancer'), [])
        self.assertEqual(index.build_from_clean(), 2)
        self.assertEqual(index.build_from_clean(), 2)
        self.assertEqual(index.collection.count(), 2)
        results = index.semantic_search('diagnosing cancer in medical images', top_k=10)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['paper_id'], '10.1/medical')
        self.assertTrue({'paper_id','title','published','categories','authors'} <= results[0]['metadata'].keys())
        self.assertEqual(len(index.collection.get(include=['embeddings'])['embeddings'][0]), 384)
        loaded = LocalEmbeddingIndex.load(self.settings)
        self.assertEqual(loaded.semantic_search('financial investment stock prices')[0]['paper_id'], '10.1/finance')
        self.assertEqual(loaded.lookup('Cancer diagnosis')['paper_id'], '10.1/medical')
        self.assertEqual(loaded.search('cancer', 1)[0].paper_id, '10.1/medical')
        with self.assertRaises(ValueError): loaded.semantic_search('cancer', 0)
        with self.assertRaises(ValueError): loaded.semantic_search(' ')
        modified = pd.concat([self.df.head(1), self.df.head(1)], ignore_index=True)
        modified['title'] = 'Updated cancer diagnosis'
        write_json(self.settings.paths.clean_json, modified.to_dict(orient='records'))
        self.assertEqual(index.build_from_clean(), 1)
        self.assertEqual(index.collection.count(), 1)
        self.assertEqual(index.lookup('10.1/medical')['title'], 'Updated cancer diagnosis')
        self.settings.paths.clean_json.unlink()
        self.df.to_csv(self.settings.paths.clean_csv,index=False)
        self.assertEqual(index.build_from_clean(), 2)


if __name__ == '__main__':
    unittest.main()
