import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload, parse_crossref_response
from ingestion.cleaning import build_clean_dataframe
from observability.quality import build_freshness_report, run_data_quality_checks


class Checkpoint1Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        settings = load_settings()
        self.settings = replace(settings, refresh_source=False, paths=replace(
            settings.paths, raw_api_response=self.root / 'response.json',
            raw_records_json=self.root / 'records.json', quality_dir=self.root / 'quality',
        ))
        self.item = {
            'DOI': ' HTTPS://DOI.ORG/10.1234/ABC ', 'title': ['  A\n study '],
            'abstract': '<jats:sec><jats:p>Research on <b>quality</b> &amp; observability.</jats:p><jats:p>More evidence.</jats:p></jats:sec>',
            'author': [{'given': ' An ', 'family': ' Nguyen '}, {'name': 'Lab'}],
            'subject': [' AI ', 'Data'], 'published-print': {'date-parts': [[2026, 1, 2]]},
        }
        self.payload = {'message': {'items': [self.item]}}
        self.settings.paths.raw_api_response.write_text(json.dumps(self.payload))

    def test_parse_item(self):
        result = parse_crossref_payload(self.item)
        self.assertEqual(result['paper_id'], '10.1234/abc')
        self.assertEqual(result['title'], 'A study')
        self.assertEqual(result['summary'], 'Research on quality & observability. More evidence.')
        self.assertEqual(result['authors'], 'An Nguyen, Lab')
        self.assertEqual(result['categories'], 'AI, Data')
        self.assertEqual(result['published'], '2026-01-02')
        self.assertIsNone(parse_crossref_payload({'title': ['No DOI']}))
        self.assertEqual(parse_crossref_payload({'DOI': '10.1/x'})['authors'], 'Unknown')

    def test_dates(self):
        for parts, expected in [([2024], '2024-01-01'), ([2024, 2], '2024-02-01'),
                                ([2024, 2, 29], '2024-02-29'), ([2024, 2, 30], '')]:
            item = {'DOI': '10.1/x', 'issued': {'date-parts': [parts]}}
            self.assertEqual(parse_crossref_payload(item)['published'], expected)
        item = dict(self.item, **{'published-print': {'date-parts': [[2026, 2, 30]]},
                                'published-online': {'date-parts': [[2026, 3, 1]]}})
        self.assertEqual(parse_crossref_payload(item)['published'], '2026-03-01')

    def test_offline_never_calls_network(self):
        with patch('ingestion.crossref.requests.get') as get:
            records = fetch_source_records(self.settings)
            get.assert_not_called()
        self.assertEqual(records, load_raw_records(self.settings.paths.raw_records_json))

    def test_live_failure_preserves_snapshot(self):
        settings = replace(self.settings, refresh_source=True)
        before = settings.paths.raw_api_response.read_bytes()
        response = Mock(status_code=429)
        response.raise_for_status.side_effect = requests.HTTPError('429')
        for kwargs in [{'return_value': response}, {'side_effect': requests.ConnectionError('offline')}]:
            with patch('ingestion.crossref.requests.get', **kwargs) as get:
                records = fetch_source_records(settings)
                self.assertEqual(len(records), 1)
                self.assertEqual(get.call_count, 1)
            self.assertEqual(settings.paths.raw_api_response.read_bytes(), before)

    def test_live_success_and_missing_fallback(self):
        settings = replace(self.settings, refresh_source=True)
        payload = {'message': {'items': [dict(self.item, DOI='10.1234/new')]}}
        response = Mock(status_code=200)
        response.json.return_value = payload
        with patch('ingestion.crossref.requests.get', return_value=response):
            self.assertEqual(fetch_source_records(settings)[0].paper_id, '10.1234/new')
        self.assertEqual(json.loads(settings.paths.raw_api_response.read_text()), payload)
        settings.paths.raw_api_response.unlink()
        with patch('ingestion.crossref.requests.get', side_effect=requests.Timeout):
            with self.assertRaisesRegex(RuntimeError, 'snapshot missing'):
                fetch_source_records(settings)

    def test_clean_calendar_age_and_contracts(self):
        item = parse_crossref_payload(self.item)
        run = datetime(2026, 1, 3, 0, 30, tzinfo=timezone(timedelta(hours=7)))
        df = build_clean_dataframe([item, item], run)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0].age_days, 1)
        self.assertEqual(df.iloc[0].text_for_embedding,
                         'Title: A study\nAuthors: An Nguyen, Lab\nPublished: 2026-01-02\nCategories: AI, Data\nSummary: Research on quality & observability. More evidence.')
        pd.testing.assert_frame_equal(df, build_clean_dataframe(parse_crossref_response(self.payload), run))
        self.assertTrue(build_clean_dataframe([], run).empty)

    def test_quality_and_freshness(self):
        records = [parse_crossref_payload(dict(self.item, DOI=f'10.1234/{i}')) for i in range(8)]
        df = build_clean_dataframe(records, datetime(2026, 2, 1))
        before = df.copy(deep=True)
        self.assertTrue(run_data_quality_checks(df, self.settings, 'good')['gate_passed'])
        pd.testing.assert_frame_equal(before, df)
        bad = df.copy()
        bad.loc[1, 'paper_id'] = bad.loc[0, 'paper_id']
        bad.loc[2, 'title'] = ' '
        bad.loc[3, 'text_for_embedding'] = None
        bad.loc[4, 'summary'] = 'short'
        result = run_data_quality_checks(bad, self.settings, 'bad')
        self.assertFalse(result['success'])
        self.assertEqual(sum(not r['success'] for r in result['results']), 4)
        self.assertFalse(run_data_quality_checks(df.head(4), self.settings, 'small')['success'])
        for count, expected in [(2, True), (3, False)]:
            stale = df.copy()
            stale['age_days'] = 180
            stale.loc[:count - 1, 'age_days'] = 181
            self.assertEqual(build_freshness_report(stale, self.settings, self.root / 'fresh.json')['is_fresh'], expected)
        self.assertFalse(build_freshness_report(df.iloc[:0], self.settings, self.root / 'empty.json')['is_fresh'])


if __name__ == '__main__':
    unittest.main()
