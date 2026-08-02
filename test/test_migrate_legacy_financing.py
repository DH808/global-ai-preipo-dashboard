import copy
import json
import os
import tempfile
import unittest
from unittest import mock
from datetime import date
from pathlib import Path

from scripts import migrate_legacy_financing as migration
from scripts.migrate_legacy_financing import (
    MigrationError, RECEIPT_META_KEY, business_state_digest, digest, execute,
)


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "state.json"
MANIFEST = ROOT / "data" / "migrations" / "legacy_financing_20260802.reviewed.json"
CLOCK = date(2026, 8, 2)
ALLOWED = {"latestFinancing", "sourceVintage", "privateStatusBoundary", "evidence"}


class LegacyFinancingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state_path = self.root / "state.json"
        self.manifest_path = self.root / "manifest.json"
        self.receipt_path = self.root / "receipt.json"
        # Build an independent pre-migration fixture from the checked-in result;
        # hashes remain compare-and-swap guards for every test mutation.
        state = json.loads(STATE.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        state.get("meta", {}).pop(RECEIPT_META_KEY, None)
        for record in manifest["records"]:
            company = next(item for item in state["companies"] if item["id"] == record["id"])
            for field in ("latestFinancing", "sourceVintage", "privateStatusBoundary"):
                company.pop(field, None)
            record["expected"]["companySha256"] = digest(company)
        self.write(self.state_path, state)
        self.write(self.manifest_path, manifest)
        self.base_state_bytes = self.state_path.read_bytes()
        self.base_manifest_bytes = self.manifest_path.read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def read(self, path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def company(self, state, company_id):
        return next(item for item in state["companies"] if item["id"] == company_id)

    def set_expected_hash(self, manifest, state, company_id):
        record = next(item for item in manifest["records"] if item["id"] == company_id)
        record["expected"]["companySha256"] = digest(self.company(state, company_id))

    def migrate(self, apply=False):
        return execute(self.state_path, self.manifest_path, self.receipt_path, apply, CLOCK)

    def prepare_replacement(self, amount="$349m"):
        state = self.read(self.state_path)
        previous = state["meta"][RECEIPT_META_KEY][-1]
        manifest = self.read(self.manifest_path)
        for item in manifest["records"]:
            item.pop("replacement", None)
        record = next(item for item in manifest["records"] if item["id"] == "alphasense")
        old_financing = copy.deepcopy(record["latestFinancing"])
        record["latestFinancing"]["amountDisplay"] = amount
        record["replacement"] = {"expectedOldLatestFinancing": old_financing}
        manifest["replacesReceipt"] = {
            "manifestSha256": previous["manifestSha256"],
            "receiptSha256": previous["receiptSha256"],
            "stateAfterBusinessSha256": previous["stateAfterBusinessSha256"],
        }
        self.write(self.manifest_path, manifest)
        return previous

    def assert_rejected(self, expected_code):
        before = self.state_path.read_bytes()
        with self.assertRaises(MigrationError) as raised:
            self.migrate(apply=True)
        self.assertEqual(raised.exception.code, expected_code)
        self.assertEqual(self.state_path.read_bytes(), before)
        self.assertFalse(self.receipt_path.exists())

    def test_preview_apply_receipt_and_replay_are_safe_and_idempotent(self):
        original = self.read(self.state_path)
        original_bytes = self.state_path.read_bytes()
        preview = self.migrate()
        self.assertEqual(preview["status"], "ready")
        self.assertFalse(preview["applied"])
        self.assertEqual(self.state_path.read_bytes(), original_bytes)
        self.assertFalse(self.receipt_path.exists())

        applied = self.migrate(apply=True)
        self.assertEqual(applied["status"], "applied")
        migrated = self.read(self.state_path)
        receipt = self.read(self.receipt_path)
        embedded = migrated["meta"][RECEIPT_META_KEY]
        self.assertEqual(embedded, [receipt])
        self.assertEqual(receipt["recordCount"], 8)
        self.assertEqual(receipt["receiptSha256"], applied["receiptSha256"])
        self.assertEqual(digest({k: v for k, v in receipt.items() if k != "receiptSha256"}), receipt["receiptSha256"])
        self.assertEqual(receipt["stateAfterBusinessSha256"], business_state_digest(migrated))
        self.assertNotEqual(receipt["stateAfterBusinessSha256"], digest(migrated))
        manifest = self.read(self.manifest_path)
        for record in manifest["records"]:
            before = self.company(original, record["id"])
            after = self.company(migrated, record["id"])
            self.assertEqual({k: v for k, v in before.items() if k not in ALLOWED},
                             {k: v for k, v in after.items() if k not in ALLOWED})
            self.assertEqual(after["latestFinancing"], record["latestFinancing"])
            self.assertEqual(after["sourceVintage"], record["sourceVintage"])
            self.assertEqual(after["privateStatusBoundary"], record["privateStatusBoundary"])
            bound = [item for item in after["evidence"] if item.get("url") == record["evidence"]["url"]]
            self.assertEqual(len(bound), 1)
            for key, value in record["evidence"].items():
                self.assertEqual(bound[0][key], value)

        state_mtime = self.state_path.stat().st_mtime_ns
        receipt_mtime = self.receipt_path.stat().st_mtime_ns
        replay = self.migrate(apply=True)
        self.assertEqual(replay["status"], "noop")
        self.assertEqual(self.state_path.stat().st_mtime_ns, state_mtime)
        self.assertEqual(self.receipt_path.stat().st_mtime_ns, receipt_mtime)

    def test_external_receipt_write_failure_recovers_from_authoritative_state_receipt(self):
        real_atomic_write = migration.atomic_write
        calls = 0

        def fail_second_write(path, payload, mode=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected receipt materialization failure")
            return real_atomic_write(path, payload, mode)

        with mock.patch.object(migration, "atomic_write", side_effect=fail_second_write):
            with self.assertRaisesRegex(OSError, "injected receipt"):
                self.migrate(apply=True)

        interrupted = self.read(self.state_path)
        self.assertEqual(len(interrupted["meta"][RECEIPT_META_KEY]), 1)
        self.assertFalse(self.receipt_path.exists())
        state_bytes = self.state_path.read_bytes()

        recovered = self.migrate(apply=True)
        self.assertEqual(recovered["status"], "noop")
        self.assertTrue(recovered["receiptMaterialized"])
        self.assertEqual(self.state_path.read_bytes(), state_bytes)
        self.assertEqual(self.read(self.receipt_path), interrupted["meta"][RECEIPT_META_KEY][0])

    def test_future_exact_replacement_uses_business_digest_and_extends_receipt_chain(self):
        self.migrate(apply=True)
        previous = self.prepare_replacement()

        replaced = self.migrate(apply=True)
        self.assertEqual(replaced["status"], "applied")
        state = self.read(self.state_path)
        receipts = state["meta"][RECEIPT_META_KEY]
        self.assertEqual(len(receipts), 2)
        self.assertEqual(receipts[-1]["previousReceiptSha256"], previous["receiptSha256"])
        self.assertEqual(receipts[-1]["stateBeforeBusinessSha256"], previous["stateAfterBusinessSha256"])
        self.assertEqual(receipts[-1]["stateAfterBusinessSha256"], business_state_digest(state))

        replay = self.migrate(apply=True)
        self.assertEqual(replay["status"], "noop")
        self.assertEqual(len(self.read(self.state_path)["meta"][RECEIPT_META_KEY]), 2)

    def test_replacement_rejects_any_unrelated_business_state_change(self):
        for mutate in (
            lambda state: self.company(state, "rebellions").update(status="public"),
            lambda state: state["meta"].update(unrelatedMigrationMarker="changed"),
        ):
            with self.subTest(mutate=mutate):
                self.state_path.write_bytes(self.base_state_bytes)
                self.manifest_path.write_bytes(self.base_manifest_bytes)
                self.receipt_path.unlink(missing_ok=True)
                self.migrate(apply=True)
                self.prepare_replacement()
                state = self.read(self.state_path)
                mutate(state)
                self.write(self.state_path, state)
                with self.assertRaises(MigrationError) as raised:
                    self.migrate(apply=True)
                self.assertEqual(raised.exception.code, "STATE_CHANGED")

    def test_authoritative_receipt_tamper_removal_and_insertion_fail_chain_validation(self):
        mutations = (
            lambda receipts: receipts[0].update(recordCount=7),
            lambda receipts: receipts.clear(),
            lambda receipts: receipts.append(copy.deepcopy(receipts[0])),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.state_path.write_bytes(self.base_state_bytes)
                self.manifest_path.write_bytes(self.base_manifest_bytes)
                self.receipt_path.unlink(missing_ok=True)
                self.migrate(apply=True)
                state = self.read(self.state_path)
                mutate(state["meta"][RECEIPT_META_KEY])
                self.write(self.state_path, state)
                with self.assertRaises(MigrationError) as raised:
                    self.migrate(apply=True)
                self.assertEqual(raised.exception.code, "RECEIPT_CHAIN_INVALID")

    def test_removed_receipt_cannot_be_used_as_external_only_replacement_lineage(self):
        self.migrate(apply=True)
        self.prepare_replacement()
        state = self.read(self.state_path)
        state["meta"][RECEIPT_META_KEY].clear()
        self.write(self.state_path, state)
        with self.assertRaises(MigrationError) as raised:
            self.migrate(apply=True)
        self.assertEqual(raised.exception.code, "RECEIPT_CHAIN_INVALID")

    def test_exact_identity_missing_and_changed_targets_fail_closed(self):
        for mutation, code in (
            (lambda state: self.company(state, "alphasense").update(name="Alpha Sense"), "TARGET_MISSING_OR_IDENTITY_MISMATCH"),
            (lambda state: state["companies"].remove(self.company(state, "alphasense")), "TARGET_MISSING_OR_IDENTITY_MISMATCH"),
            (lambda state: self.company(state, "alphasense").update(status="public"), "TARGET_CHANGED"),
        ):
            with self.subTest(code=code):
                state = self.read(self.state_path)
                mutation(state); self.write(self.state_path, state)
                self.assert_rejected(code)
                self.state_path.write_bytes(self.base_state_bytes)

    def test_manifest_shape_review_hash_and_old_value_fail_closed(self):
        cases = []
        manifest = self.read(self.manifest_path); manifest["review"]["status"] = "draft"; cases.append((manifest, "REVIEW_APPROVAL_REQUIRED"))
        manifest = self.read(self.manifest_path); manifest["records"][0]["valuation"] = "$1B"; cases.append((manifest, "MANIFEST_SHAPE_INVALID"))
        manifest = self.read(self.manifest_path); manifest["records"] = manifest["records"][:-1]; cases.append((manifest, "RECORD_COUNT_INVALID"))
        manifest = self.read(self.manifest_path); manifest["records"][0]["expected"]["oldLatestFunding"] = "changed"; cases.append((manifest, "EXPECTED_OLD_VALUE_MISMATCH"))
        for manifest, code in cases:
            with self.subTest(code=code):
                self.write(self.manifest_path, manifest)
                self.assert_rejected(code)
                self.manifest_path.write_bytes(self.base_manifest_bytes)

    def test_source_binding_freshness_url_amount_round_and_type_fail_closed(self):
        mutations = (
            (lambda r: r["evidence"].update(date="2026-06-02"), "SOURCE_DATE_BINDING_MISMATCH"),
            (lambda r: [r[part].update(sourceUrl="https://example.com/") for part in ("latestFinancing", "privateStatusBoundary")]
                       + [r["evidence"].update(url="https://example.com/")], "GENERIC_HOMEPAGE_SOURCE"),
            (lambda r: [r[part].update(sourceUrl="https://www.crunchbase.com/organization/test") for part in ("latestFinancing", "privateStatusBoundary")]
                       + [r["evidence"].update(url="https://www.crunchbase.com/organization/test")], "AGGREGATOR_SOURCE_FORBIDDEN"),
            (lambda r: [r[part].update(**({"announcedDate": "2023-01-01"} if part == "latestFinancing" else {"asOf": "2023-01-01"})) for part in ("latestFinancing", "privateStatusBoundary")]
                       + [r.update(sourceVintage="2023-01-01"), r["evidence"].update(date="2023-01-01")], "SOURCE_DATE_OUT_OF_RANGE"),
            (lambda r: r["latestFinancing"].update(amountDisplay="a lot"), "AMOUNT_INVALID"),
            (lambda r: r["latestFinancing"].update(roundType="valuation round"), "VALUATION_FIELDS_FORBIDDEN"),
            (lambda r: r["latestFinancing"].update(financingType="grant"), "FINANCING_TYPE_INVALID"),
            (lambda r: r["evidence"].update(rightsProfile="internal_only"), "PUBLIC_PROVENANCE_INVALID"),
        )
        for mutation, code in mutations:
            with self.subTest(code=code):
                manifest = json.loads(self.base_manifest_bytes)
                mutation(manifest["records"][1]); self.write(self.manifest_path, manifest)
                self.assert_rejected(code)
                self.manifest_path.write_bytes(self.base_manifest_bytes)

    def test_existing_duplicate_or_conflicting_financing_requires_exact_replacement(self):
        state = self.read(self.state_path)
        manifest = self.read(self.manifest_path)
        company = self.company(state, "alphasense")
        old = {"roundType": "Series X", "amountDisplay": "$1m", "announcedDate": "2026-01-01",
               "financingType": "equity", "sourceUrl": "https://example.com/news/round"}
        company["latestFinancing"] = old
        self.set_expected_hash(manifest, state, "alphasense")
        self.write(self.state_path, state); self.write(self.manifest_path, manifest)
        self.assert_rejected("EXISTING_FINANCING_CONFLICT")

        manifest["records"][1]["replacement"] = {"expectedOldLatestFinancing": copy.deepcopy(old)}
        self.write(self.manifest_path, manifest)
        result = self.migrate(apply=True)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(self.company(self.read(self.state_path), "alphasense")["latestFinancing"], manifest["records"][1]["latestFinancing"])

    def test_duplicate_and_conflicting_financing_evidence_fail_closed(self):
        for conflict, code in ((False, "DUPLICATE_FINANCING_EVIDENCE"), (True, "CONFLICTING_FINANCING_EVIDENCE")):
            with self.subTest(code=code):
                state = json.loads(self.base_state_bytes)
                manifest = json.loads(self.base_manifest_bytes)
                company = self.company(state, "alphasense")
                if conflict:
                    company["evidence"].append({"claimType": "latest_financing", "url": "https://example.com/news/other"})
                else:
                    company["evidence"].append(copy.deepcopy(company["evidence"][0]))
                self.set_expected_hash(manifest, state, "alphasense")
                self.write(self.state_path, state); self.write(self.manifest_path, manifest)
                self.assert_rejected(code)
                self.state_path.write_bytes(self.base_state_bytes); self.manifest_path.write_bytes(self.base_manifest_bytes)

    def test_changed_applied_target_is_not_treated_as_replay(self):
        self.migrate(apply=True)
        state = self.read(self.state_path)
        self.company(state, "alphasense")["latestFinancing"]["amountDisplay"] = "$351m"
        self.write(self.state_path, state)
        with self.assertRaises(MigrationError) as raised:
            self.migrate(apply=True)
        self.assertEqual(raised.exception.code, "STATE_CHANGED")


if __name__ == "__main__":
    unittest.main()
