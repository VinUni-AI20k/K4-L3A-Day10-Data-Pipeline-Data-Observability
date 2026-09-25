"""Dashboard integration checks, without invoking the real pipeline or any API."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

spec = importlib.util.spec_from_file_location('dashboard', Path(__file__).parents[1] / 'script/run_ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)

class DashboardTests(unittest.TestCase):
    def test_missing_and_malformed_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIsNone(ui.snapshot(root)['states']['baseline']['metrics'])
            target = root / 'data/results/baseline_metrics.json'
            target.parent.mkdir(parents=True)
            target.write_text('{unfinished', encoding='utf-8')
            result = ui.snapshot(root)
            self.assertIsNone(result['states']['baseline']['metrics'])
            self.assertEqual(len(result['errors']), 1)
            target.write_text('{"retrieval_hit_rate": 0.75}', encoding='utf-8')
            self.assertEqual(ui.snapshot(root)['states']['baseline']['metrics']['retrieval_hit_rate'], 0.75)

    def test_http_assets_auth_and_job_lock(self):
        server = ui.ThreadingHTTPServer(('127.0.0.1', 0), ui.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/') as response:
                self.assertIn(b'Pipeline Observatory', response.read())
            for asset in ('app.js', 'style.css', 'api/snapshot'):
                with urlopen(base + '/' + asset) as response:
                    self.assertEqual(response.status, 200)
            for path in ('/.env', '/../src/core/config.py'):
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path)
                self.assertEqual(error.exception.code, 404)
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base + '/api/run/baseline', method='POST'))
            self.assertEqual(error.exception.code, 403)
            with patch.object(ui, 'run_pipeline') as runner:
                request = Request(base + '/api/run/baseline', method='POST', headers={'X-UI-Token': ui.TOKEN})
                with urlopen(request) as response:
                    self.assertEqual(response.status, 202)
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, 409)
                self.assertEqual(runner.call_count, 1)
        finally:
            server.shutdown()
            server.server_close()
            ui.JOB.update(status='idle', phase=None, exit_code=None)

if __name__ == '__main__':
    unittest.main()
