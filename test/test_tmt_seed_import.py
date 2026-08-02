import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.import_tmt_seed import canonical_hash, run


def valid_seed():
    return {
        "schemaVersion": "1.0.0",
        "asOf": "2026-08-01",
        "review": {"status": "approved", "reviewedBy": "Test Reviewer", "reviewedAt": "2026-08-02T00:00:00Z"},
        "records": [{
            "name": "Example Test Systems", "aliases": ["Example Systems"], "headquartersCountry": "United States",
            "tmtVertical": "Enterprise Software", "businessModel": "SaaS", "customerType": "B2B",
            "monetization": ["Subscription"], "lifecycleStage": "series_a_b", "sourceVintage": "2026-07-01",
            "sources": [{"url": "https://example.com/company/status", "date": "2026-07-01", "type": "official", "confidence": "high"}],
            "confidence": "high",
            "privateStatusBoundary": {"status": "private", "asOf": "2026-07-01", "sourceUrl": "https://example.com/company/status", "confidence": "high"},
            "investabilityAccessLane": "relationship_development"
        }]
    }


class TmtSeedImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.seed_path = self.root / "seed.json"
        self.state_path = self.root / "state.json"
        self.state_path.write_text(json.dumps({"meta": {}, "companies": []}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_seed(self, seed):
        self.seed_path.write_text(json.dumps(seed), encoding="utf-8")

    def execute_import(self, apply=False, replace_manifest_path=None):
        return run(self.seed_path, self.state_path, apply=apply, as_of_override=date(2026, 8, 2),
                   replace_manifest_path=replace_manifest_path)

    def test_preview_default_apply_and_idempotency(self):
        self.write_seed(valid_seed())
        before = self.state_path.read_bytes()
        preview = self.execute_import()
        self.assertEqual(preview["status"], "valid")
        self.assertTrue(preview["dryRun"])
        self.assertFalse(preview["mutated"])
        self.assertEqual(self.state_path.read_bytes(), before)
        applied = self.execute_import(apply=True)
        self.assertEqual(applied["afterCompanyCount"], 1)
        first_apply = self.state_path.read_bytes()
        self.seed_path.write_text(json.dumps(valid_seed(), indent=2, sort_keys=True), encoding="utf-8")
        repeated = self.execute_import(apply=True)
        self.assertTrue(repeated["summary"]["alreadyApplied"])
        self.assertFalse(repeated["mutated"])
        self.assertEqual(self.state_path.read_bytes(), first_apply)
        company = json.loads(first_apply)["companies"][0]
        self.assertNotIn("latestValuation", company)
        self.assertEqual(company["tmtVertical"], "Enterprise Software")
        applied_state = json.loads(first_apply)
        self.assertEqual(applied_state["meta"]["asOf"], "2026-08-01")
        self.assertEqual(applied_state["meta"]["updatedAt"], "2026-08-02T00:00:00Z")

    def test_duplicate_names_and_aliases_are_rejected(self):
        seed = valid_seed()
        duplicate = copy.deepcopy(seed["records"][0])
        duplicate["name"] = "Second Test Company"
        duplicate["aliases"] = ["EXAMPLE-SYSTEMS"]
        seed["records"].append(duplicate)
        self.write_seed(seed)
        result = self.execute_import()
        self.assertEqual(result["status"], "invalid")
        self.assertIn("DUPLICATE_NAME_OR_ALIAS", {e["code"] for e in result["errors"]})

    def test_duplicate_json_keys_fail_without_touching_state(self):
        before = self.state_path.read_bytes()
        self.seed_path.write_text('{"schemaVersion":"1.0.0","schemaVersion":"1.0.0"}', encoding="utf-8")
        result = self.execute_import(apply=True)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["errors"][0]["code"], "DUPLICATE_JSON_KEY")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_invalid_stale_unverified_and_valuation_records_are_rejected(self):
        cases = []
        invalid_url = valid_seed(); invalid_url["records"][0]["sources"][0]["url"] = "file:///private/source"; cases.append((invalid_url, "SOURCE_INVALID"))
        stale = valid_seed(); stale["records"][0]["sourceVintage"] = "2023-01-01"; stale["records"][0]["sources"][0]["date"] = "2023-01-01"; stale["records"][0]["privateStatusBoundary"]["asOf"] = "2023-01-01"; cases.append((stale, "SOURCE_STALE"))
        unverified = valid_seed(); unverified["records"][0]["privateStatusBoundary"]["confidence"] = "low"; cases.append((unverified, "PRIVATE_STATUS_UNVERIFIED"))
        valuation = valid_seed(); valuation["records"][0]["latestValuation"] = "$1B"; cases.append((valuation, "VALUATION_FIELDS_FORBIDDEN"))
        for index, (seed, expected) in enumerate(cases):
            with self.subTest(case=index):
                self.write_seed(seed)
                result = self.execute_import()
                self.assertEqual(result["status"], "invalid")
                self.assertIn(expected, {e["code"] for e in result["errors"]})

    def test_stronger_existing_evidence_is_not_overwritten(self):
        seed = valid_seed()
        seed["records"][0]["tmtVertical"] = "Data/Analytics"
        self.write_seed(seed)
        existing = {
            "id": "example-test-systems", "name": "Example Test Systems", "status": "private",
            "tmtVertical": "Enterprise Software", "evidence": [],
            "tmtFieldEvidence": {"tmtVertical": {"confidence": "high", "sourceDate": "2026-07-15", "seedSha256": "prior"}}
        }
        self.state_path.write_text(json.dumps({"meta": {}, "companies": [existing]}), encoding="utf-8")
        result = self.execute_import(apply=True)
        self.assertEqual(result["status"], "valid")
        company = json.loads(self.state_path.read_text())["companies"][0]
        self.assertEqual(company["tmtVertical"], "Enterprise Software")

    def test_ambiguous_existing_alias_match_is_rejected(self):
        self.write_seed(valid_seed())
        state = {"meta": {}, "companies": [
            {"id": "one", "name": "Example Test Systems", "status": "private"},
            {"id": "two", "name": "Another", "aliases": ["Example Systems"], "status": "private"},
        ]}
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        result = self.execute_import()
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["errors"][0]["code"], "AMBIGUOUS_EXISTING_MATCH")

    def test_existing_private_boundary_conflicts_fail_closed_even_when_status_is_private(self):
        boundary_conflicts = [
            {"privateStatus": "public"},
            {"privateStatus": "unknown"},
            {"privateStatusAsOf": "2026-06-30"},
            {"privateStatusConfidence": "medium"},
            {"isListed": True},
            {"ticker": "TEST"},
            {"privateStatusBoundary": {"status": "acquired", "asOf": "2026-07-01", "confidence": "high"}},
        ]
        self.write_seed(valid_seed())
        for fields in boundary_conflicts:
            with self.subTest(fields=fields):
                company = {"id": "example-test-systems", "name": "Example Test Systems", "status": "private", **fields}
                self.state_path.write_text(json.dumps({"meta": {}, "companies": [company]}), encoding="utf-8")
                before = self.state_path.read_bytes()
                result = self.execute_import(apply=True)
                self.assertEqual(result["status"], "invalid")
                self.assertEqual(result["errors"][0]["code"], "EXISTING_PRIVATE_STATUS_CONFLICT")
                self.assertEqual(self.state_path.read_bytes(), before)

    def test_generic_homepage_and_misaligned_boundary_vintage_are_rejected(self):
        homepage = valid_seed()
        homepage["records"][0]["sources"][0]["url"] = "https://example.com/"
        homepage["records"][0]["privateStatusBoundary"]["sourceUrl"] = "https://example.com/"
        self.write_seed(homepage)
        self.assertIn("GENERIC_HOMEPAGE_SOURCE", {e["code"] for e in self.execute_import()["errors"]})

        mismatch = valid_seed()
        mismatch["records"][0]["sources"].append({
            "url": "https://example.com/company/newer-report", "date": "2026-07-02",
            "type": "reputable_media", "confidence": "high",
        })
        mismatch["records"][0]["sourceVintage"] = "2026-07-02"
        self.write_seed(mismatch)
        self.assertIn("PRIVATE_STATUS_INVALID", {e["code"] for e in self.execute_import()["errors"]})

    def replacement_fixture(self):
        old_seed = valid_seed()
        self.write_seed(old_seed)
        old_result = self.execute_import(apply=True)
        old_state = json.loads(self.state_path.read_text(encoding="utf-8"))
        old_company = old_state["companies"][0]
        receipt = old_state["meta"]["tmtSeedImports"][0]
        manifest_path = self.root / "replacement.json"
        manifest_path.write_text(json.dumps({
            "schemaVersion": "1.0.0", "operation": "replace-seed-import",
            "supersededReceipt": receipt,
            "expectedCompanies": [{"id": old_company["id"], "sha256": canonical_hash(old_company)}],
        }), encoding="utf-8")
        corrected = valid_seed()
        corrected["records"][0]["companyDescription"] = "Corrected dated-source record."
        self.write_seed(corrected)
        return old_result, manifest_path

    def test_atomic_verified_replacement_and_second_replay_are_idempotent(self):
        old_result, manifest_path = self.replacement_fixture()
        replaced = self.execute_import(apply=True, replace_manifest_path=manifest_path)
        self.assertEqual(replaced["status"], "valid")
        self.assertTrue(replaced["replacement"]["performed"])
        self.assertEqual(replaced["beforeCompanyCount"], 1)
        self.assertEqual(replaced["afterCompanyCount"], 1)
        self.assertEqual(replaced["summary"]["created"], 1)
        state_after = self.state_path.read_bytes()
        state = json.loads(state_after)
        receipts = state["meta"]["tmtSeedImports"]
        self.assertNotIn(old_result["inputSha256"], {item["sha256"] for item in receipts})
        self.assertEqual(len(receipts), 1)

        replay = self.execute_import(apply=True, replace_manifest_path=manifest_path)
        self.assertTrue(replay["replacement"]["alreadyReplaced"])
        self.assertTrue(replay["summary"]["alreadyApplied"])
        self.assertFalse(replay["mutated"])
        self.assertEqual(self.state_path.read_bytes(), state_after)

    def test_replacement_refuses_post_import_company_edits(self):
        _, manifest_path = self.replacement_fixture()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["companies"][0]["manualNote"] = "post-import edit"
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        before = self.state_path.read_bytes()
        result = self.execute_import(apply=True, replace_manifest_path=manifest_path)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["errors"][0]["code"], "SUPERSEDED_COMPANY_EDITED")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_replacement_refuses_post_import_references(self):
        _, manifest_path = self.replacement_fixture()
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["tasks"] = [{"id": "manual-task", "companyId": "example-test-systems"}]
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        before = self.state_path.read_bytes()
        result = self.execute_import(apply=True, replace_manifest_path=manifest_path)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["errors"][0]["code"], "SUPERSEDED_COMPANY_REFERENCED")
        self.assertEqual(self.state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
