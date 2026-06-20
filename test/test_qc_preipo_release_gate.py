#!/usr/bin/env python3
import importlib.util
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'qc_preipo_release_gate.py'
spec = importlib.util.spec_from_file_location('qc_preipo_release_gate', SCRIPT)
qc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qc)

class ReleaseGateHelperTest(unittest.TestCase):
    def test_scan_forbidden_terms_reports_context_and_ignores_allowed_internal_endpoint(self):
        text = '{"ok":true,"snapshotPublisher":"publish_preipo_snapshot.py","path":"/Users/mac/x"}'
        hits = qc.scan_forbidden_terms('/api/state', text)
        terms = {h['term'] for h in hits}
        self.assertIn('.py', terms)
        self.assertIn('/Users/mac', terms)
        self.assertTrue(all('context' in h and h['context'] for h in hits))

    def test_assert_path_returns_nested_values(self):
        data = {'dashboard': {'total': 104}, 'queue': {'summary': {'actNow': 15}}}
        self.assertEqual(qc.get_path(data, 'dashboard.total'), 104)
        self.assertEqual(qc.get_path(data, 'queue.summary.actNow'), 15)
        self.assertIsNone(qc.get_path(data, 'missing.value'))

    def test_validate_company_payload_requires_memo_scores_claims_and_funding(self):
        good = {
            'company': {'name': 'Databricks'},
            'memo': {'sections': [{'title': '01 投资结论'}] * 11},
            'fundingRounds': [{'id': 'r1'}],
            'claims': [{'id': 'c1'}] * 4,
            'scores': [{'scoreType': 'ic_readiness'}] * 8,
        }
        errors = []
        qc.validate_company_payload('/api/company/databricks', good, errors)
        self.assertEqual(errors, [])
        bad = {'company': {'name': 'X'}, 'memo': {'sections': []}, 'fundingRounds': [], 'claims': [], 'scores': []}
        qc.validate_company_payload('/api/company/x', bad, errors)
        self.assertTrue(any('memo sections' in e['message'] for e in errors))

    def test_sqlite_count_rules_detect_missing_tables(self):
        with tempfile.NamedTemporaryFile(suffix='.sqlite') as f:
            errors = []
            qc.validate_sqlite_counts(pathlib.Path(f.name), expected_companies=104, errors=errors)
            self.assertTrue(any('missing sqlite table' in e['message'] for e in errors))

if __name__ == '__main__':
    unittest.main()
