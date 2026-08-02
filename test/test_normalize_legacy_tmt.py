import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.normalize_legacy_tmt import deterministic_profile, run

ROOT = Path(__file__).resolve().parents[1]


class NormalizeLegacyTmtTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp.name) / "state.json"
        self.receipt_path = Path(self.temp.name) / "receipt.json"
        self.reviewed = {
            "id": "reviewed", "name": "Reviewed", "sector": "AI software", "subSector": "Workflow",
            "companyDescription": "Enterprise software", "tmtVertical": "Digital Health", "businessModel": "Services",
            "customerType": "B2G", "monetization": ["Services"],
            "tmtFieldEvidence": {field: {"seedSha256": "reviewed-digest"} for field in
                                 ("tmtVertical", "businessModel", "customerType", "monetization")},
        }
        self.legacy = {"id": "legacy", "name": "Legacy", "sector": "TMT / Cybersecurity",
                       "subSector": "Enterprise identity SaaS", "companyDescription": "Security software for businesses"}
        self.state_path.write_text(json.dumps({"meta": {}, "companies": [self.reviewed, self.legacy]}))

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_apply_receipt_and_idempotency(self):
        before = self.state_path.read_bytes()
        preview = run(self.state_path, receipt_path=self.receipt_path, expected_legacy_count=1)
        self.assertTrue(preview["dryRun"])
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertEqual(json.loads(self.receipt_path.read_text())["status"], "valid")
        applied = run(self.state_path, apply=True, expected_legacy_count=1)
        self.assertTrue(applied["mutated"])
        after = self.state_path.read_bytes()
        replay = run(self.state_path, apply=True, expected_legacy_count=1)
        self.assertTrue(replay["receipt"]["alreadyApplied"])
        self.assertFalse(replay["mutated"])
        self.assertEqual(self.state_path.read_bytes(), after)
        companies = {c["id"]: c for c in json.loads(after)["companies"]}
        self.assertEqual(companies["reviewed"], self.reviewed)
        self.assertEqual(companies["legacy"]["tmtVertical"], "Cybersecurity/Identity")
        self.assertEqual(companies["legacy"]["classificationConfidence"], "derived")

    def test_unknown_is_canonical_other(self):
        profile = deterministic_profile({"sector": "Unclassified", "subSector": "", "companyDescription": ""})
        self.assertEqual(profile["tmtVertical"], "Other")
        self.assertEqual(profile["businessModel"], "Other")
        self.assertEqual(profile["customerType"], "Other")
        self.assertEqual(profile["monetization"], ["Other"])

    def test_boundaries_precedence_and_audited_overrides(self):
        cases = {
            "legora": ("TMT / AI workplace tools", "AI workspace for legal work", "Enterprise Software"),
            "climax-technology": ("AI hardware", "LEO satellite / security connectivity", "Space/Communications"),
            "rebellions": ("AI silicon / accelerator", "Data-center inference accelerator", "AI/Cloud/Semiconductor Infrastructure"),
            "furiosaai": ("AI silicon / accelerator", "Data-center AI accelerator", "AI/Cloud/Semiconductor Infrastructure"),
            "deepx": ("AI cloud / power / cooling operator", "Edge AI NPU", "AI/Cloud/Semiconductor Infrastructure"),
            "trendyol": ("TMT / E-commerce marketplace", "logistics/payments ecosystem", "Commerce/Marketplaces"),
            "infobip": ("TMT / Cloud communications", "messaging and authentication", "Space/Communications"),
        }
        for company_id, (sector, sub_sector, expected) in cases.items():
            with self.subTest(company=company_id):
                profile = deterministic_profile({"id": company_id, "sector": sector, "subSector": sub_sector})
                self.assertEqual(profile["tmtVertical"], expected)
        self.assertEqual(
            deterministic_profile({"sector": "AI workplace tools", "subSector": "Legal workspace"})["tmtVertical"],
            "Enterprise Software",
        )

    def test_count_guard_is_fail_closed_and_atomic(self):
        before = self.state_path.read_bytes()
        result = run(self.state_path, apply=True, expected_legacy_count=2)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["errors"][0]["code"], "LEGACY_COUNT_MISMATCH")
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_repository_state_has_complete_guarded_normalization(self):
        state = json.loads((ROOT / "data" / "state.json").read_text(encoding="utf-8"))
        legacy = [c for c in state["companies"] if c.get("classificationMethod") == "deterministic_legacy_mapping"]
        reviewed = [c for c in state["companies"] if c.get("id") in {
            r["id"] for r in json.loads((ROOT / "data" / "connectors" / "tmt_seed_20260802_batch1.json").read_text())["records"]
        }]
        self.assertEqual(len(state["companies"]), 154)
        self.assertEqual(len(legacy), 143)
        self.assertEqual(len(reviewed), 11)
        self.assertTrue(all(c.get("classificationConfidence") == "derived" for c in legacy))
        self.assertTrue(all(
            all(c.get(field) == deterministic_profile(c)[field] for field in (
                "tmtVertical", "businessModel", "customerType", "monetization",
                "classificationMethod", "classificationConfidence",
            ))
            for c in legacy
        ), "all 143 stored legacy profiles must equal the audited deterministic output")
        self.assertTrue(all(all(field in c for field in ("tmtVertical", "businessModel", "customerType", "monetization")) for c in state["companies"]))
        self.assertTrue(all(c.get("classificationMethod") != "deterministic_legacy_mapping" for c in reviewed))


if __name__ == "__main__":
    unittest.main()
