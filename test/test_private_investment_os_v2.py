from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "state.json"
IMPORTER = ROOT / "scripts" / "import_legacy_state_v2.py"
MIGRATOR = ROOT / "scripts" / "run_migrations_v2.py"
PREVIEW = ROOT / "scripts" / "preview_manual_import_v2.py"


def run_json(*args: str, expected: int = 0) -> dict:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != expected:
        raise AssertionError(f"command failed ({result.returncode}): {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


class PrivateInvestmentOsV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="private-investment-v2-")
        cls.tmp = Path(cls.temp.name)
        cls.db = cls.tmp / "pipeline_v2.sqlite"
        cls.receipt = cls.tmp / "receipt.json"
        cls.first_receipt = run_json("python3", str(IMPORTER), "--state-file", str(STATE), "--db", str(cls.db), "--receipt", str(cls.receipt))

        cls.api_env = os.environ.copy()
        cls.api_env.update({"PIPELINE_V2_DB_FILE": str(cls.db), "NODE_ENV": "production", "ENABLE_WRITES": "false"})

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def http(cls, path: str, method: str = "GET", body: bytes | None = None):
        request = {"path": path, "method": method, "body": body.decode() if body else ""}
        result = subprocess.run(["node", "test/api_contract_runner_v2.js", json.dumps(request)], cwd=ROOT, env=cls.api_env, text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        parsed = json.loads(result.stdout)
        return parsed["status"], parsed["payload"]

    def test_01_migration_is_idempotent(self):
        db = self.tmp / "migration_only.sqlite"
        first = run_json("python3", str(MIGRATOR), "--db", str(db))
        second = run_json("python3", str(MIGRATOR), "--db", str(db))
        self.assertEqual(first["applied"], ["001"])
        self.assertEqual(second["skipped"], ["001"])
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 1)

    def test_01a_failing_migration_rolls_back_schema_and_record(self):
        migrations = self.tmp / "failing-migrations"
        migrations.mkdir()
        (migrations / "001_failure.sql").write_text(
            "CREATE TABLE should_roll_back(id INTEGER PRIMARY KEY);\n"
            "INSERT INTO table_that_does_not_exist VALUES(1);\n",
            encoding="utf-8",
        )
        db = self.tmp / "failing-migration.sqlite"
        result = subprocess.run(
            ["python3", str(MIGRATOR), "--db", str(db), "--migrations-dir", str(migrations)],
            cwd=ROOT, text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        with sqlite3.connect(db) as conn:
            self.assertIsNone(conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='should_roll_back'"
            ).fetchone())
            self.assertEqual(conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 0)

    def test_02_importer_preserves_counts_and_is_idempotent(self):
        counts = self.first_receipt["tableCounts"]
        self.assertEqual({k: counts[k] for k in ("companies", "fundingRounds", "investors", "evidenceItems", "claims", "tasks")},
                         {"companies": 143, "fundingRounds": 185, "investors": 402, "evidenceItems": 387, "claims": 572, "tasks": 180})
        replay = run_json("python3", str(IMPORTER), "--state-file", str(STATE), "--db", str(self.db), "--receipt", str(self.tmp / "receipt-2.json"))
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["tableCounts"], counts)

    def test_02a_migration_is_additive_on_legacy_database_copy(self):
        legacy_copy = self.tmp / "legacy_pipeline_copy.sqlite"
        shutil.copy2(ROOT / "data" / "pipeline.sqlite", legacy_copy)
        result = run_json("python3", str(MIGRATOR), "--db", str(legacy_copy), "--backup", str(self.tmp / "legacy_pipeline_copy.before.sqlite"))
        self.assertEqual(result["integrityCheck"], "ok")
        self.assertEqual(result["foreignKeyViolations"], 0)
        with sqlite3.connect(legacy_copy) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM companies").fetchone()[0], 143)
            self.assertEqual(conn.execute("SELECT count(*) FROM funding_rounds").fetchone()[0], 185)
            self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='raw_records'").fetchone())

    def test_03_raw_record_hash_dedupe_and_provider_neutral_columns(self):
        with sqlite3.connect(self.db) as conn:
            raw_count = conn.execute("SELECT count(*) FROM raw_records").fetchone()[0]
            unique_count = conn.execute("SELECT count(*) FROM (SELECT source_id,provider_object_type,provider_object_id,payload_sha256 FROM raw_records GROUP BY 1,2,3,4)").fetchone()[0]
            self.assertEqual(raw_count, unique_count)
            canonical_tables = ["organizations", "canonical_funding_rounds", "metric_observations", "opportunities", "canonical_evidence_items", "canonical_claims"]
            columns = [row[1].lower() for table in canonical_tables for row in conn.execute(f"PRAGMA table_info({table})")]
            self.assertFalse(any(prefix in column for prefix in ("crunchbase", "dealroom", "pitchbook") for column in columns))

    def test_03a_raw_record_object_types_match_envelope_contract(self):
        schema = json.loads((ROOT / "schemas" / "raw-envelope.schema.json").read_text(encoding="utf-8"))
        allowed = set(schema["properties"]["objectType"]["enum"])
        with sqlite3.connect(self.db) as conn:
            actual = {row[0] for row in conn.execute("SELECT DISTINCT provider_object_type FROM raw_records")}
        self.assertTrue(actual <= allowed, actual - allowed)
        self.assertIn("organization", actual)
        self.assertIn("interaction", allowed)
        self.assertIn("source_registry_entry", allowed)

    def test_03b_generic_legacy_evidence_does_not_fabricate_claim_links(self):
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM canonical_claim_evidence").fetchone()[0], 0)
            statuses = {row[0] for row in conn.execute("SELECT DISTINCT status FROM canonical_claims")}
        self.assertEqual(statuses, {"unverified"})

    def test_04_preview_does_not_mutate_canonical_tables(self):
        input_file = self.tmp / "preview.json"
        input_file.write_text(json.dumps([{"recordType": "organization", "companyId": "newco", "name": "NewCo"}, {"recordType": "funding_round", "companyId": "databricks", "date": "2026-08-01", "round": "Secondary"}, {"recordType": "metric", "companyId": "databricks", "metricName": "arr", "value": "10"}]))
        with sqlite3.connect(self.db) as conn: before = conn.execute("SELECT count(*) FROM organizations").fetchone()[0]
        result = run_json("python3", str(PREVIEW), "--input", str(input_file), "--db", str(self.db))
        with sqlite3.connect(self.db) as conn: after = conn.execute("SELECT count(*) FROM organizations").fetchone()[0]
        self.assertEqual(result["status"], "valid")
        self.assertFalse(result["mutatedCanonicalTables"])
        self.assertEqual(before, after)

    def test_05_v2_pagination_filters_and_error_envelope(self):
        status, page = self.http("/api/v2/companies?limit=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(page["data"]), 2)
        self.assertTrue(page["page"]["nextCursor"])
        _, page2 = self.http("/api/v2/companies?limit=2&cursor=" + page["page"]["nextCursor"])
        self.assertNotEqual(page["data"][0]["id"], page2["data"][0]["id"])
        _, filtered = self.http("/api/v2/companies?limit=5&q=Databricks&region=US&status=private")
        self.assertTrue(any(x["legacySlug"] == "databricks" for x in filtered["data"]))
        status, error = self.http("/api/v2/companies?limit=999")
        self.assertEqual(status, 400)
        self.assertEqual(set(error["error"]), {"code", "message", "details", "requestId"})

    def test_06_lineage_is_redacted_and_company_dto_is_provider_neutral(self):
        status, lineage = self.http("/api/v2/companies/databricks/lineage")
        self.assertEqual(status, 200)
        self.assertEqual(lineage["data"]["redaction"], {"rawPayloadsExposed": False, "localPathsExposed": False, "licensedLocatorsExposed": False})
        serialized = json.dumps(lineage).lower()
        self.assertNotIn("payload_json", serialized)
        self.assertNotIn("/users/", serialized)
        _, company = self.http("/api/v2/companies/databricks")
        keys = json.dumps(company).lower()
        self.assertNotIn("crunchbase_", keys)
        self.assertNotIn("dealroom_", keys)
        self.assertNotIn("pitchbook_", keys)

    def test_06a_public_evidence_requires_eligibility_and_redistributable_rights(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("""INSERT INTO ingestion_runs(
                id,source_id,connector_version,started_at,status,request_fingerprint
              ) VALUES('run_test_internal','pitchbook_csv_v1','test','2026-08-02T00:00:00Z','completed','test-internal-rights')""")
            conn.execute("""INSERT INTO raw_records(
                id,source_id,ingestion_run_id,provider_object_type,provider_object_id,
                ingested_at,payload_json,payload_sha256,rights_profile_id
              ) VALUES('raw_test_internal','pitchbook_csv_v1','run_test_internal','evidence','private-note',
                '2026-08-02T00:00:00Z','{}',?,'internal_only')""", ("a" * 64,))
            conn.execute("""INSERT INTO canonical_evidence_items VALUES(
                'evidence_test_internal','org_databricks','licensed','DO NOT EXPOSE LICENSED NOTE',NULL,NULL,
                'high','raw_test_internal',1)""")
            legacy_raw = conn.execute(
                "SELECT id FROM raw_records WHERE source_id='legacy_state_json' LIMIT 1"
            ).fetchone()[0]
            conn.execute("""INSERT INTO canonical_evidence_items VALUES(
                'evidence_test_ineligible','org_databricks','manual','DO NOT EXPOSE INELIGIBLE NOTE',NULL,NULL,
                'low',?,0)""", (legacy_raw,))
            conn.commit()
        status, evidence = self.http("/api/v2/companies/databricks/evidence")
        self.assertEqual(status, 200)
        serialized = json.dumps(evidence)
        self.assertNotIn("DO NOT EXPOSE", serialized)
        self.assertTrue(all(item["publicationEligible"] == 1 for item in evidence["data"]))

    def test_07_connector_statuses_and_quality(self):
        _, sources = self.http("/api/v2/sources")
        by_id = {row["id"]: row for row in sources["data"]}
        self.assertEqual(by_id["crunchbase_v1"]["status"], "missing_credential")
        self.assertEqual(by_id["dealroom_v1"]["status"], "missing_credential")
        self.assertEqual(by_id["pitchbook_csv_v1"]["status"], "not_imported")
        self.assertNotIn("credentialEnvVar", json.dumps(sources))
        _, quality = self.http("/api/v2/data-quality")
        self.assertIn("missingLineage", quality["summary"])

    def test_08_v1_contract_and_read_only_guard(self):
        for path in ("/api/state", "/api/pipeline", "/api/company/databricks", "/api/ops"):
            status, payload = self.http(path)
            self.assertEqual(status, 200, path)
            self.assertIsInstance(payload, dict)
        status, payload = self.http("/api/company/databricks", "POST", b"{}")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "READ_ONLY_DEPLOYMENT")
        status, payload = self.http("/api/v2/imports/preview", "POST", b"{}")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "READ_ONLY_DEPLOYMENT")

    def test_09_sqlite_integrity_and_foreign_keys(self):
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_10_changed_snapshot_updates_current_rows_and_lineage(self):
        db = self.tmp / "changed-snapshot.sqlite"
        receipt = self.tmp / "changed-snapshot-first.json"
        first = run_json("python3", str(IMPORTER), "--state-file", str(STATE), "--db", str(db), "--receipt", str(receipt))
        changed_state = json.loads(STATE.read_text(encoding="utf-8"))
        company = next(row for row in changed_state["companies"] if row["id"] == "databricks")
        company.update({
            "name": "Databricks Updated",
            "website": "https://updated.example",
            "dealStage": "updated-stage",
            "whyInTrack": "Updated thesis",
            "nextAction": "Updated next action",
            "relationshipRoute": "Updated broker route",
            "latestAvailableValuation": "$135B explicitly supported",
            "keyMetrics": ["Updated metric one", "Updated metric two"],
        })
        company["evidence"][0].update({"note": "Updated explicit valuation support", "claimType": "valuation"})
        funding = next(row for row in changed_state["fundingRounds"] if row.get("companyId") == "databricks")
        funding.update({"amount": "$5B", "sourceType": "official", "url": "https://updated.example/funding"})
        task = next(row for row in changed_state["tasks"] if row.get("companyId") == "databricks")
        task["title"] = "Updated task title"
        changed_file = self.tmp / "changed-state.json"
        changed_file.write_text(json.dumps(changed_state, ensure_ascii=False), encoding="utf-8")
        changed = run_json("python3", str(IMPORTER), "--state-file", str(changed_file), "--db", str(db), "--receipt", str(self.tmp / "changed-snapshot-second.json"))
        self.assertFalse(changed["idempotentReplay"])
        for key in ("companies", "fundingRounds", "investors", "evidenceItems", "claims", "tasks", "relationships", "metricObservations"):
            self.assertEqual(changed["tableCounts"][key], first["tableCounts"][key], key)
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            org = conn.execute("SELECT * FROM organizations WHERE id='org_databricks'").fetchone()
            self.assertEqual((org["canonical_name"], org["website"]), ("Databricks Updated", "https://updated.example"))
            opportunity = conn.execute("SELECT * FROM opportunities WHERE id='opp_databricks_legacy'").fetchone()
            self.assertEqual((opportunity["stage"], opportunity["thesis"], opportunity["next_action"]),
                             ("updated-stage", "Updated thesis", "Updated next action"))
            relationship = conn.execute("SELECT * FROM canonical_relationships WHERE organization_id='org_databricks'").fetchall()
            self.assertEqual(len(relationship), 1)
            self.assertEqual(relationship[0]["route_description"], "Updated broker route")
            evidence = conn.execute("SELECT * FROM canonical_evidence_items WHERE id='evidence_databricks_1'").fetchone()
            self.assertEqual(evidence["note"], "Updated explicit valuation support")
            claim = conn.execute("SELECT * FROM canonical_claims WHERE id='claim_databricks_valuation'").fetchone()
            self.assertEqual((claim["status"], claim["confidence"]), ("partially_supported", "medium"))
            self.assertEqual(conn.execute("SELECT count(*) FROM canonical_claim_evidence WHERE claim_id=?", (claim["id"],)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM canonical_claim_evidence").fetchone()[0], 1)
            metric_values = [row[0] for row in conn.execute(
                "SELECT value_text FROM metric_observations WHERE organization_id='org_databricks' ORDER BY value_text"
            )]
            self.assertEqual(metric_values, ["Updated metric one", "Updated metric two"])
            round_row = conn.execute("SELECT * FROM canonical_funding_rounds WHERE id=?", ("round_" + funding["id"],)).fetchone()
            self.assertEqual(round_row["amount_display"], "$5B")
            sources = conn.execute("SELECT * FROM funding_round_sources WHERE funding_round_id=?", (round_row["id"],)).fetchall()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]["source_record_id"], round_row["selected_source_record_id"])
            task_row = conn.execute("SELECT * FROM canonical_tasks WHERE id=?", (task["id"],)).fetchone()
            self.assertEqual(task_row["title"], "Updated task title")
            selected_name = conn.execute("SELECT selected_value_json,selected_source_record_id FROM canonical_field_decisions WHERE organization_id='org_databricks' AND field_path='identity.canonicalName'").fetchone()
            self.assertEqual(json.loads(selected_name[0]), "Databricks Updated")
            self.assertEqual(selected_name[1], org["source_record_id"])
            self.assertEqual(conn.execute("SELECT status FROM readiness_gates WHERE organization_id='org_databricks' AND gate_type='evidence_readiness'").fetchone()[0], "ready")
            self.assertEqual(evidence["source_record_id"], conn.execute("SELECT id FROM raw_records WHERE provider_object_type='evidence' AND provider_object_id='databricks:1' ORDER BY rowid DESC LIMIT 1").fetchone()[0])
            self.assertIsNotNone(conn.execute("SELECT supersedes_raw_record_id FROM raw_records WHERE id=?", (evidence["source_record_id"],)).fetchone()[0])
        replay = run_json("python3", str(IMPORTER), "--state-file", str(changed_file), "--db", str(db), "--receipt", str(self.tmp / "changed-snapshot-third.json"))
        self.assertTrue(replay["idempotentReplay"])


if __name__ == "__main__":
    unittest.main()
