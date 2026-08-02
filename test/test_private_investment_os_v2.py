from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode, urlparse

from scripts.import_legacy_state_v2 import expanded_funding_rounds
from scripts.import_tmt_seed import canonical_hash, identity

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "state.json"
IMPORTER = ROOT / "scripts" / "import_legacy_state_v2.py"
MIGRATOR = ROOT / "scripts" / "run_migrations_v2.py"
PREVIEW = ROOT / "scripts" / "preview_manual_import_v2.py"
PUBLIC_BUILD = ROOT / "scripts" / "build_public_v2_db.py"
TMT_SEED = ROOT / "data" / "connectors" / "tmt_seed_20260802_batch1.json"
BATCH2_SEED = ROOT / "data" / "connectors" / "tmt_seed_20260802_batch2.json"
BATCH2_REPLACEMENT = ROOT / "data" / "connectors" / "tmt_seed_20260802_batch2_financing_replacement.json"
BATCH3_SEED = ROOT / "data" / "connectors" / "tmt_seed_20260802_batch3.json"


def run_json(*args: str, expected: int = 0) -> dict:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != expected:
        raise AssertionError(f"command failed ({result.returncode}): {result.stderr}\n{result.stdout}")
    return json.loads(result.stdout)


def as_list(value):
    return value if isinstance(value, list) else ([value] if value else [])


def release_identity_union(state: dict) -> set[str]:
    """Return canonical IDs in the normalization baseline plus every seed batch."""
    seed_files = sorted((ROOT / "data" / "connectors").glob("tmt_seed_20260802_batch[0-9].json"))
    seed_batches = [json.loads(path.read_text(encoding="utf-8"))["records"] for path in seed_files]
    legacy_ids = {
        company["id"] for company in state["companies"]
        if company.get("classificationMethod") == "deterministic_legacy_mapping"
    }
    baseline_ids = legacy_ids | {record["id"] for record in seed_batches[0]}
    seed_ids = {record["id"] for records in seed_batches for record in records}
    return baseline_ids | seed_ids


def importer_expected_counts(state: dict) -> dict[str, int]:
    """Derive canonical row counts from the legacy importer's input contract."""
    companies = as_list(state.get("companies"))
    company_ids = [str(row.get("id") or "").strip() for row in companies]
    self_names = [str(row.get("name") or "").strip() for row in companies]
    if not all(company_ids) or not all(self_names) or len(set(company_ids)) != len(company_ids):
        raise AssertionError("test input must contain unique, identified companies")

    valid_company_ids = set(company_ids)
    rounds = expanded_funding_rounds(state)
    valid_rounds = [row for row in rounds if str(row.get("companyId") or "").strip() in valid_company_ids]
    if len(valid_rounds) != len(rounds):
        raise AssertionError("test input contains a funding round without a canonical company")

    investor_ids = {
        re.sub(r"[^a-z0-9]+", "-", str(name).strip().rstrip(",").lower()).strip("-") or "item"
        for company in companies for name in as_list(company.get("investors")) if str(name).strip().rstrip(",")
    }
    tasks = as_list(state.get("tasks"))
    if any(not str(row.get("id") or "").strip() for row in tasks):
        raise AssertionError("current test input must use stable task IDs")
    if len({row["id"] for row in tasks}) != len(tasks):
        raise AssertionError("current test input contains duplicate task IDs")

    company_evidence = sum(len(as_list(company.get("evidence"))) for company in companies)
    return {
        "companies": len(companies),
        "fundingRounds": len(valid_rounds),
        "investors": len(investor_ids),
        "evidenceItems": company_evidence + len(valid_rounds),
        "claims": 4 * len(companies),
        "tasks": len(tasks),
        "relationships": len(companies),
        "rawRecords": (
            len(companies) + company_evidence + len(valid_rounds) + len(tasks)
            + len(as_list(state.get("interactions"))) + len(as_list(state.get("sourceRegistry")))
        ),
    }


class PrivateInvestmentOsV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="private-investment-v2-")
        cls.tmp = Path(cls.temp.name)
        cls.db = cls.tmp / "pipeline_v2.sqlite"
        cls.receipt = cls.tmp / "receipt.json"
        cls.first_receipt = run_json("python3", str(IMPORTER), "--state-file", str(STATE), "--db", str(cls.db), "--receipt", str(cls.receipt))
        cls.public_state = cls.tmp / "public-state.json"
        cls.public_db = cls.tmp / "pipeline-v2-public.sqlite"
        cls.public_build_receipt = run_json(
            "python3", str(PUBLIC_BUILD), "--state-file", str(STATE),
            "--public-state-file", str(cls.public_state), "--db", str(cls.public_db),
        )

        cls.api_env = os.environ.copy()
        cls.api_env.update({
            "PIPELINE_V2_DB_FILE": str(cls.db), "PUBLIC_STATE_FILE": str(cls.public_state),
            "NODE_ENV": "production", "ENABLE_WRITES": "false",
        })

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
        self.assertEqual(first["applied"], ["001", "002"])
        self.assertEqual(second["skipped"], ["001", "002"])
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0], 2)

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
        state = json.loads(STATE.read_text(encoding="utf-8"))
        expected = importer_expected_counts(state)
        counts = self.first_receipt["tableCounts"]
        self.assertEqual({key: counts[key] for key in expected}, expected)
        self.assertEqual(self.first_receipt["rejects"], [])
        self.assertEqual(self.first_receipt["qc"]["status"], "pass")
        self.assertEqual(self.first_receipt["qc"]["minimumCounts"], {
            key: expected[key] for key in (
                "companies", "fundingRounds", "evidenceItems", "investors", "claims", "tasks", "relationships"
            )
        })
        replay = run_json("python3", str(IMPORTER), "--state-file", str(STATE), "--db", str(self.db), "--receipt", str(self.tmp / "receipt-2.json"))
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["tableCounts"], counts)
        with sqlite3.connect(self.db) as conn:
            run = conn.execute(
                "SELECT records_seen,records_inserted FROM ingestion_runs WHERE id=?",
                (self.first_receipt["ingestionRunId"],),
            ).fetchone()
            self.assertEqual(conn.execute("SELECT count(*) FROM ingestion_runs WHERE id=?", (self.first_receipt["ingestionRunId"],)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT count(*) FROM import_idempotency_keys WHERE idempotency_key=?", (self.first_receipt["idempotencyKey"],)).fetchone()[0], 1)
            claim_distribution = conn.execute("""
                SELECT min(n),max(n) FROM (
                  SELECT organization_id,count(*) n FROM canonical_claims GROUP BY organization_id
                )
            """).fetchone()
            self.assertEqual(claim_distribution, (4, 4))
        source_rows_seen = sum(len(state.get(key, [])) for key in (
            "companies", "fundingRounds", "tasks", "interactions", "sourceRegistry"
        ))
        self.assertEqual(run[0], source_rows_seen)
        self.assertEqual(run[1], expected["rawRecords"])
        self.assertNotEqual(run[0], run[1])

    def test_02f_expanded_tmt_release_survives_public_build_and_v1_v2_apis(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        seed = json.loads(TMT_SEED.read_text(encoding="utf-8"))
        snapshot = json.loads(self.public_state.read_text(encoding="utf-8"))
        seed_records = seed["records"]
        seed_ids = {record["id"] for record in seed_records}
        self.assertEqual(seed["review"]["status"], "approved")
        self.assertEqual(len(seed_records), 11)
        self.assertEqual(len(seed_ids), len(seed_records))

        state_by_id = {company["id"]: company for company in state["companies"]}
        public_by_id = {company["id"]: company for company in snapshot["companies"]}
        self.assertEqual(len(state_by_id), len(state["companies"]))
        self.assertEqual(len(public_by_id), len(snapshot["companies"]))
        self.assertTrue(seed_ids <= state_by_id.keys())
        self.assertTrue(seed_ids <= public_by_id.keys())
        for record in seed_records:
            source_company = state_by_id[record["id"]]
            public_company = public_by_id[record["id"]]
            self.assertEqual(source_company["name"], record["name"])
            self.assertEqual(source_company["tmtVertical"], record["tmtVertical"])
            self.assertEqual(source_company["lifecycleStage"], record["lifecycleStage"])
            self.assertEqual(public_company["name"], record["name"])
            self.assertEqual(public_company["tmtVertical"], record["tmtVertical"])
            self.assertEqual(len(record["sources"]), 1)
            dated_source = record["sources"][0]
            self.assertNotIn(urlparse(dated_source["url"]).path, ("", "/"))
            self.assertEqual(record["sourceVintage"], dated_source["date"])
            self.assertEqual(record["privateStatusBoundary"]["asOf"], dated_source["date"])
            self.assertEqual(record["privateStatusBoundary"]["sourceUrl"], dated_source["url"])
            self.assertEqual(source_company["sourceVintage"], dated_source["date"])
            self.assertEqual(source_company["privateStatusAsOf"], dated_source["date"])
            self.assertEqual(source_company["evidence"], [dated_source])
            self.assertEqual(public_company["evidence"], [dated_source])
            self.assertEqual(source_company["latestFinancing"], record["latestFinancing"])
            self.assertEqual(public_company["latestFinancing"], record["latestFinancing"])
            self.assertEqual(set(public_company["latestFinancing"]), {"roundType", "amountDisplay", "announcedDate", "financingType", "sourceUrl"})
            self.assertEqual(public_company["latestFinancing"]["sourceUrl"], dated_source["url"])
            self.assertNotIn("valuation", public_company["latestFinancing"])
            self.assertNotIn("aliases", public_company)
            self.assertNotIn("tmtFieldEvidence", public_company)
            self.assertEqual(set(public_company["completeness"]), {
                "classification", "businessModel", "customerType", "monetization", "financing",
                "investors", "revenue", "evidence", "sourceVintage",
            })

        self.assertEqual(state_by_id["candid-health"]["sourceVintage"], "2026-07-22")
        self.assertEqual(state_by_id["stoke-space"]["evidence"][0]["url"],
                         "https://www.geekwire.com/2026/stoke-space-350m-added-funding/")

        expected_public_count = len(state["companies"])
        self.assertEqual(len(snapshot["companies"]), expected_public_count)
        self.assertEqual(snapshot["meta"]["publicCompanyCount"], expected_public_count)
        self.assertEqual(self.public_build_receipt["publicCompanyCount"], expected_public_count)
        with sqlite3.connect(self.public_db) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM organizations WHERE organization_type='company'").fetchone()[0], expected_public_count)
            seed_evidence = conn.execute(
                "SELECT source_locator,as_of FROM canonical_evidence_items WHERE id NOT LIKE 'evidence_funding_%%' AND organization_id IN (%s)" %
                ",".join("?" for _ in seed_ids), [f"org_{company_id}" for company_id in sorted(seed_ids)]
            ).fetchall()
            self.assertEqual(len(seed_evidence), 11)
            self.assertIn(("https://www.mobihealthnews.com/news/candid-health-raises-120m-ai-revenue-cycle-management-platform", "2026-07-22"), seed_evidence)
            self.assertIn(("https://www.geekwire.com/2026/stoke-space-350m-added-funding/", "2026-02-10"), seed_evidence)
            self.assertFalse(any(urlparse(url).path in ("", "/") for url, _ in seed_evidence))
            latest_rounds = conn.execute(
                "SELECT announced_date,round_type,amount_display,valuation_display,metadata_json "
                "FROM canonical_funding_rounds WHERE organization_id IN (%s)" %
                ",".join("?" for _ in seed_ids), [f"org_{company_id}" for company_id in sorted(seed_ids)]
            ).fetchall()
            structured = [row for row in latest_rounds if json.loads(row[4] or "{}").get("financingType")]
            self.assertEqual(len(structured), 11)
            self.assertTrue(all(row[3] is None for row in structured))

        status, v1_state = self.http("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(v1_state["dashboard"]["total"], expected_public_count)
        self.assertEqual({company["id"] for company in v1_state["companies"]}, set(state_by_id))
        for vertical in {record["tmtVertical"] for record in seed_records}:
            status, filtered = self.http("/api/state?" + urlencode({"tmtVertical": vertical}))
            self.assertEqual(status, 200)
            expected_seed_ids = {record["id"] for record in seed_records if record["tmtVertical"] == vertical}
            self.assertTrue(expected_seed_ids <= {company["id"] for company in filtered["companies"]})
            self.assertTrue(all(company["tmtVertical"] == vertical for company in filtered["companies"]))
            self.assertEqual(filtered["dashboard"]["total"], len(filtered["companies"]))

        status, v2_meta = self.http("/api/v2/meta")
        self.assertEqual(status, 200)
        self.assertEqual(v2_meta["counts"]["companies"], expected_public_count)
        v2_payloads = []
        for record in seed_records:
            status, listing = self.http("/api/v2/companies?" + urlencode({"q": record["name"], "limit": 100}))
            self.assertEqual(status, 200)
            self.assertIn(record["id"], {company["legacySlug"] for company in listing["data"]})
            status, detail = self.http("/api/v2/companies/" + record["id"])
            self.assertEqual(status, 200)
            self.assertEqual(detail["data"]["identity"]["name"], record["name"])
            self.assertEqual(detail["data"]["latestFunding"]["announcedDate"], record["latestFinancing"]["announcedDate"])
            self.assertEqual(detail["data"]["latestFunding"]["amountDisplay"], record["latestFinancing"]["amountDisplay"])
            self.assertEqual(detail["data"]["latestFunding"]["financingType"], record["latestFinancing"]["financingType"])
            self.assertNotIn("valuationDisplay", detail["data"]["latestFunding"])
            # The detail alias is the public legacy slug, not a private seed alias.
            self.assertEqual(detail["data"]["aliases"], [record["id"]])
            v2_payloads.append(detail)

        private_markers = {
            "tmtFieldEvidence", "tmtSeedImports", "seedSha256", "privateStatusBoundary",
            "reviewedBy", seed["review"]["reviewedBy"], state["meta"]["tmtSeedImports"][0]["sha256"],
        }
        public_surfaces = json.dumps({"snapshot": snapshot, "v1": v1_state, "v2": v2_payloads}, ensure_ascii=False)
        for marker in private_markers:
            self.assertNotIn(marker, public_surfaces)
        with sqlite3.connect(self.public_db) as conn:
            public_raw = "\n".join(row[0] for row in conn.execute("SELECT payload_json FROM raw_records"))
        for marker in private_markers:
            self.assertNotIn(marker, public_raw)

    def test_02g_batch2_release_survives_seed_v1_v2_and_schema_002_end_to_end(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        seed = json.loads(BATCH2_SEED.read_text(encoding="utf-8"))
        snapshot = json.loads(self.public_state.read_text(encoding="utf-8"))
        records = seed["records"]
        seed_ids = {record["id"] for record in records}
        financing_ids = seed_ids

        self.assertEqual(seed["review"]["status"], "approved")
        self.assertEqual(seed_ids, {"bestow", "chapter", "federato", "harper", "mercury", "plaid", "rain", "substack"})
        self.assertEqual(len(records), len(seed_ids))
        records_by_id = {record["id"]: record for record in records}
        self.assertEqual(records_by_id["chapter"]["latestFinancing"], {
            "roundType": "funding round", "amountDisplay": "$75m", "announcedDate": "2025-04-16",
            "financingType": "equity",
            "sourceUrl": "https://techcrunch.com/2025/04/16/chapter-a-medicare-startup-with-links-to-vance-thiel-and-ramaswamy-just-raised-a-round-at-1-5b-valuation/",
        })
        self.assertEqual(records_by_id["federato"]["latestFinancing"]["roundType"], "financing")
        for company_id in ("federato", "mercury", "plaid", "substack"):
            self.assertEqual(records_by_id[company_id]["monetization"], ["Other"])
        self.assertEqual(records_by_id["plaid"]["businessModel"], "Other")
        self.assertEqual(records_by_id["plaid"]["customerType"], "B2B")
        self.assertEqual(records_by_id["substack"]["businessModel"], "Other")
        self.assertEqual(records_by_id["substack"]["customerType"], "Other")

        state_by_id = {company["id"]: company for company in state["companies"]}
        public_by_id = {company["id"]: company for company in snapshot["companies"]}
        self.assertEqual(len(state_by_id), len(state["companies"]))
        self.assertEqual(len(public_by_id), len(snapshot["companies"]))
        self.assertTrue(seed_ids <= state_by_id.keys())
        self.assertTrue(seed_ids <= public_by_id.keys())

        identity_owners = {}
        for company in state["companies"]:
            for value in [company.get("name"), company.get("legalName"), *as_list(company.get("aliases"))]:
                if isinstance(value, str) and identity(value):
                    identity_owners.setdefault(identity(value), set()).add(company["id"])

        for record in records:
            company_id = record["id"]
            source_company = state_by_id[company_id]
            public_company = public_by_id[company_id]
            source = record["sources"][0]
            self.assertEqual(len(record["sources"]), 1)
            self.assertNotIn(urlparse(source["url"]).path, ("", "/"))
            self.assertEqual(record["sourceVintage"], source["date"])
            self.assertEqual(record["privateStatusBoundary"], {
                "status": "private", "asOf": source["date"], "sourceUrl": source["url"],
                "confidence": source["confidence"],
            })
            self.assertEqual(source_company["status"], "private")
            self.assertEqual(source_company["privateStatus"], "private")
            self.assertEqual(source_company["privateStatusAsOf"], source["date"])
            self.assertEqual(source_company["privateStatusConfidence"], source["confidence"])
            self.assertEqual(source_company["evidence"], [source])
            self.assertEqual(public_company["evidence"], [source])
            for value in [record["name"], *record["aliases"]]:
                self.assertEqual(identity_owners[identity(value)], {company_id})

            self.assertEqual(source_company["latestFinancing"], record["latestFinancing"])
            self.assertEqual(public_company["latestFinancing"], record["latestFinancing"])
            self.assertEqual(public_company["completeness"]["financing"], "present")
            self.assertNotIn("valuation", public_company["latestFinancing"])

        expected_release_count = len(release_identity_union(state))
        self.assertEqual(len(state["companies"]), expected_release_count)
        self.assertEqual(len(snapshot["companies"]), expected_release_count)
        self.assertEqual(snapshot["meta"]["publicCompanyCount"], expected_release_count)
        self.assertEqual(self.public_build_receipt["publicCompanyCount"], expected_release_count)

        status, v1_state = self.http("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(v1_state["dashboard"]["total"], expected_release_count)
        self.assertTrue(seed_ids <= {company["id"] for company in v1_state["companies"]})
        for vertical in {record["tmtVertical"] for record in records}:
            status, filtered = self.http("/api/state?" + urlencode({"tmtVertical": vertical}))
            self.assertEqual(status, 200)
            expected_ids = {record["id"] for record in records if record["tmtVertical"] == vertical}
            self.assertTrue(expected_ids <= {company["id"] for company in filtered["companies"]})
            self.assertTrue(all(company["tmtVertical"] == vertical for company in filtered["companies"]))

        status, v2_meta = self.http("/api/v2/meta")
        self.assertEqual(status, 200)
        self.assertEqual(v2_meta["counts"]["companies"], expected_release_count)
        v2_payloads = []
        for record in records:
            status, listing = self.http("/api/v2/companies?" + urlencode({"q": record["name"], "limit": 100}))
            self.assertEqual(status, 200)
            self.assertIn(record["id"], {company["legacySlug"] for company in listing["data"]})
            status, detail = self.http("/api/v2/companies/" + record["id"])
            self.assertEqual(status, 200)
            self.assertEqual(detail["data"]["identity"]["name"], record["name"])
            status, funding = self.http(f"/api/v2/companies/{record['id']}/funding-rounds")
            self.assertEqual(status, 200)
            self.assertEqual(detail["data"]["latestFunding"]["roundType"], record["latestFinancing"]["roundType"])
            self.assertEqual(detail["data"]["latestFunding"]["amountDisplay"], record["latestFinancing"]["amountDisplay"])
            self.assertEqual(detail["data"]["latestFunding"]["announcedDate"], record["latestFinancing"]["announcedDate"])
            self.assertEqual(detail["data"]["latestFunding"]["financingType"], record["latestFinancing"]["financingType"])
            self.assertEqual(funding["data"], [detail["data"]["latestFunding"]])
            self.assertNotIn("valuationDisplay", detail["data"]["latestFunding"])
            v2_payloads.extend((detail, funding))

        placeholders = ",".join("?" for _ in seed_ids)
        with sqlite3.connect(self.public_db) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            rounds = conn.execute(
                "SELECT organization_id,valuation_display,post_money_value,metadata_json "
                f"FROM canonical_funding_rounds WHERE organization_id IN ({placeholders})",
                [f"org_{company_id}" for company_id in sorted(seed_ids)],
            ).fetchall()
            structured = [row for row in rounds if json.loads(row[3] or "{}").get("financingType")]
            self.assertEqual(len(structured), 8)
            self.assertEqual({row[0].removeprefix("org_") for row in structured}, financing_ids)
            self.assertTrue(all(row[1] is None and row[2] is None for row in structured))
            public_raw = "\n".join(row[0] for row in conn.execute("SELECT payload_json FROM raw_records"))

        current_receipt = next(item for item in state["meta"]["tmtSeedImports"] if item["sha256"] == canonical_hash(seed))
        private_markers = {
            "tmtFieldEvidence", "tmtSeedImports", "seedSha256", "privateStatusBoundary",
            "reviewedBy", seed["review"]["reviewedBy"], current_receipt["sha256"],
        }
        public_surfaces = json.dumps({"snapshot": snapshot, "v1": v1_state, "v2": v2_payloads}, ensure_ascii=False)
        for marker in private_markers:
            self.assertNotIn(marker, public_surfaces)
            self.assertNotIn(marker, public_raw)

        replay_state = self.tmp / "batch2-replay-state.json"
        replay_state.write_bytes(STATE.read_bytes())
        before_replay = replay_state.read_bytes()
        replay = run_json(
            "python3", str(ROOT / "scripts" / "import_tmt_seed.py"), "--input", str(BATCH2_SEED),
            "--state", str(replay_state), "--as-of", "2026-08-02", "--apply",
            "--replace-manifest", str(BATCH2_REPLACEMENT),
        )
        self.assertTrue(replay["summary"]["alreadyApplied"])
        self.assertTrue(replay["replacement"]["alreadyReplaced"])
        self.assertFalse(replay["mutated"])
        self.assertEqual(replay_state.read_bytes(), before_replay)

    def test_02h_batch3_matches_merge_safely_and_survives_public_end_to_end(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        seed = json.loads(BATCH3_SEED.read_text(encoding="utf-8"))
        snapshot = json.loads(self.public_state.read_text(encoding="utf-8"))
        records = seed["records"]
        records_by_id = {record["id"]: record for record in records}
        seed_ids = set(records_by_id)
        matched_ids = {"clay", "glean", "sierra"}
        created_ids = seed_ids - matched_ids

        self.assertEqual(seed["review"]["status"], "approved")
        self.assertEqual(created_ids, {"cyera", "grafana-labs", "island", "linear", "supabase"})
        self.assertEqual(len(records), len(seed_ids))
        self.assertEqual({
            company_id: (record["latestFinancing"]["roundType"], record["latestFinancing"]["amountDisplay"])
            for company_id, record in records_by_id.items()
        }, {
            "clay": ("Series C", "$100m"),
            "cyera": ("Series F", "$400m"),
            "glean": ("Series F", "$150m"),
            "grafana-labs": ("Series D extension", "$270m"),
            "island": ("Series E", "$250m"),
            "linear": ("Series C", "$82m"),
            "sierra": ("financing", "$950m"),
            "supabase": ("Series F", "$500m"),
        })

        state_by_id = {company["id"]: company for company in state["companies"]}
        public_by_id = {company["id"]: company for company in snapshot["companies"]}
        self.assertEqual(len(state_by_id), len(state["companies"]))
        self.assertEqual(len(public_by_id), len(snapshot["companies"]))
        self.assertTrue(seed_ids <= state_by_id.keys())
        self.assertTrue(seed_ids <= public_by_id.keys())

        identity_owners = {}
        for company in state["companies"]:
            for value in [company.get("name"), company.get("legalName"), *as_list(company.get("aliases"))]:
                if isinstance(value, str) and identity(value):
                    identity_owners.setdefault(identity(value), set()).add(company["id"])
        self.assertTrue(identity_owners)
        self.assertTrue(all(len(owners) == 1 for owners in identity_owners.values()))

        for record in records:
            company_id = record["id"]
            source_company = state_by_id[company_id]
            public_company = public_by_id[company_id]
            self.assertEqual(len(record["sources"]), 1)
            source = record["sources"][0]
            self.assertNotIn(urlparse(source["url"]).path, ("", "/"))
            self.assertEqual(record["sourceVintage"], source["date"])
            self.assertEqual(record["privateStatusBoundary"], {
                "status": "private", "asOf": source["date"], "sourceUrl": source["url"],
                "confidence": source["confidence"],
            })
            self.assertEqual(source_company["privateStatus"], "private")
            self.assertEqual(source_company["privateStatusAsOf"], source["date"])
            self.assertEqual(source_company["privateStatusConfidence"], source["confidence"])
            self.assertIn(source, source_company["evidence"])
            self.assertIn(source, public_company["evidence"])
            self.assertEqual(source_company["latestFinancing"], record["latestFinancing"])
            self.assertEqual(public_company["latestFinancing"], record["latestFinancing"])
            self.assertNotIn("valuation", public_company["latestFinancing"])
            for value in [record["name"], *record["aliases"]]:
                self.assertEqual(identity_owners[identity(value)], {company_id})

        # These fields predate batch3, carry stronger unrelated legacy context,
        # and must survive while the dated source and financing are appended.
        legacy_expectations = {
            "glean": {
                "sector": "AI application / workflow layer",
                "subSector": "Enterprise search / work AI",
                "latestValuation": "Reuters: ~$7.2B valuation; official ARR $200M",
                "relationshipRoute": "投资人线：Sequoia/Lightspeed/general growth investors - verify",
            },
            "sierra": {
                "sector": "AI application / workflow layer",
                "subSector": "Customer-service AI agents",
                "latestFunding": "2025 $350M round",
                "relationshipRoute": "Greenoaks, General Catalyst/Sierra management, enterprise customer references.",
            },
            "clay": {
                "sector": "AI application / workflow layer",
                "subSector": "AI GTM / sales automation platform",
                "latestValuation": "Media: $3.1B",
                "relationshipRoute": "CapitalG Clay team; GTM/adtech network.",
            },
        }
        for company_id, expected_fields in legacy_expectations.items():
            for field, expected in expected_fields.items():
                self.assertEqual(state_by_id[company_id][field], expected)
            self.assertGreaterEqual(len(state_by_id[company_id]["evidence"]), 2)

        expected_release_ids = release_identity_union(state)
        expected_release_count = len(expected_release_ids)
        self.assertEqual(set(state_by_id), expected_release_ids)
        self.assertEqual(len(snapshot["companies"]), expected_release_count)
        self.assertEqual(snapshot["meta"]["publicCompanyCount"], expected_release_count)
        self.assertEqual(self.public_build_receipt["publicCompanyCount"], expected_release_count)

        status, v1_state = self.http("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(v1_state["dashboard"]["total"], expected_release_count)
        self.assertTrue(seed_ids <= {company["id"] for company in v1_state["companies"]})
        for vertical in {record["tmtVertical"] for record in records}:
            status, filtered = self.http("/api/state?" + urlencode({"tmtVertical": vertical}))
            self.assertEqual(status, 200)
            expected_ids = {record["id"] for record in records if record["tmtVertical"] == vertical}
            self.assertTrue(expected_ids <= {company["id"] for company in filtered["companies"]})
            self.assertTrue(all(company["tmtVertical"] == vertical for company in filtered["companies"]))

        status, v2_meta = self.http("/api/v2/meta")
        self.assertEqual(status, 200)
        self.assertEqual(v2_meta["counts"]["companies"], expected_release_count)
        v2_payloads = []
        for record in records:
            status, listing = self.http("/api/v2/companies?" + urlencode({"q": record["name"], "limit": 100}))
            self.assertEqual(status, 200)
            self.assertIn(record["id"], {company["legacySlug"] for company in listing["data"]})
            status, detail = self.http("/api/v2/companies/" + record["id"])
            self.assertEqual(status, 200)
            status, funding = self.http(f"/api/v2/companies/{record['id']}/funding-rounds")
            self.assertEqual(status, 200)
            batch_rounds = [row for row in funding["data"] if (
                row.get("roundType") == record["latestFinancing"]["roundType"]
                and row.get("amountDisplay") == record["latestFinancing"]["amountDisplay"]
                and row.get("announcedDate") == record["latestFinancing"]["announcedDate"]
                and row.get("financingType") == record["latestFinancing"]["financingType"]
            )]
            self.assertEqual(len(batch_rounds), 1)
            self.assertNotIn("valuationDisplay", batch_rounds[0])
            v2_payloads.extend((detail, funding))

        placeholders = ",".join("?" for _ in seed_ids)
        with sqlite3.connect(self.public_db) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            rounds = conn.execute(
                "SELECT organization_id,valuation_display,post_money_value,metadata_json "
                f"FROM canonical_funding_rounds WHERE organization_id IN ({placeholders})",
                [f"org_{company_id}" for company_id in sorted(seed_ids)],
            ).fetchall()
            structured = [row for row in rounds if json.loads(row[3] or "{}").get("financingType")]
            self.assertEqual(len(structured), len(records))
            self.assertEqual({row[0].removeprefix("org_") for row in structured}, seed_ids)
            self.assertTrue(all(row[1] is None and row[2] is None for row in structured))
            public_raw = "\n".join(row[0] for row in conn.execute("SELECT payload_json FROM raw_records"))

        current_receipt = next(item for item in state["meta"]["tmtSeedImports"] if item["sha256"] == canonical_hash(seed))
        private_markers = {
            "tmtFieldEvidence", "tmtSeedImports", "seedSha256", "privateStatusBoundary",
            "reviewedBy", seed["review"]["reviewedBy"], current_receipt["sha256"],
        }
        public_surfaces = json.dumps({"snapshot": snapshot, "v1": v1_state, "v2": v2_payloads}, ensure_ascii=False)
        for marker in private_markers:
            self.assertNotIn(marker, public_surfaces)
            self.assertNotIn(marker, public_raw)

        replay_state = self.tmp / "batch3-replay-state.json"
        before_batch3 = json.loads(STATE.read_text(encoding="utf-8"))
        before_batch3["companies"] = [
            company for company in before_batch3["companies"] if company["id"] not in created_ids
        ]
        before_batch3["meta"]["tmtSeedImports"] = [
            receipt for receipt in before_batch3["meta"]["tmtSeedImports"]
            if receipt["sha256"] != canonical_hash(seed)
        ]
        replay_state.write_text(json.dumps(before_batch3, ensure_ascii=False), encoding="utf-8")
        applied = run_json(
            "python3", str(ROOT / "scripts" / "import_tmt_seed.py"), "--input", str(BATCH3_SEED),
            "--state", str(replay_state), "--as-of", "2026-08-02", "--apply",
        )
        self.assertEqual(applied["summary"]["created"], len(created_ids))
        self.assertEqual(applied["summary"]["matched"], len(matched_ids))
        self.assertEqual(applied["afterCompanyCount"], expected_release_count)
        applied_bytes = replay_state.read_bytes()
        replay = run_json(
            "python3", str(ROOT / "scripts" / "import_tmt_seed.py"), "--input", str(BATCH3_SEED),
            "--state", str(replay_state), "--as-of", "2026-08-02", "--apply",
        )
        self.assertTrue(replay["summary"]["alreadyApplied"])
        self.assertFalse(replay["mutated"])
        self.assertEqual(replay_state.read_bytes(), applied_bytes)

    def test_02a_migration_is_additive_on_legacy_database_copy(self):
        legacy_copy = self.tmp / "legacy_pipeline_copy.sqlite"
        shutil.copy2(ROOT / "data" / "pipeline.sqlite", legacy_copy)
        with sqlite3.connect(legacy_copy) as conn:
            legacy_counts = {
                "companies": conn.execute("SELECT count(*) FROM companies").fetchone()[0],
                "fundingRounds": conn.execute("SELECT count(*) FROM funding_rounds").fetchone()[0],
            }
        result = run_json("python3", str(MIGRATOR), "--db", str(legacy_copy), "--backup", str(self.tmp / "legacy_pipeline_copy.before.sqlite"))
        self.assertEqual(result["integrityCheck"], "ok")
        self.assertEqual(result["foreignKeyViolations"], 0)
        with sqlite3.connect(legacy_copy) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM companies").fetchone()[0], legacy_counts["companies"])
            self.assertEqual(conn.execute("SELECT count(*) FROM funding_rounds").fetchone()[0], legacy_counts["fundingRounds"])
            self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='raw_records'").fetchone())

    def test_02b_sqlite_backup_captures_committed_wal_pages(self):
        db = self.tmp / "active-wal.sqlite"
        backup = self.tmp / "active-wal.backup.sqlite"
        writer = sqlite3.connect(db)
        try:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("CREATE TABLE live_rows(id INTEGER PRIMARY KEY, value TEXT)")
            writer.executemany("INSERT INTO live_rows(value) VALUES(?)", [(f"row-{i}",) for i in range(37)])
            writer.commit()
            self.assertTrue(Path(str(db) + "-wal").exists())
            run_json("python3", str(MIGRATOR), "--db", str(db), "--backup", str(backup))
            with sqlite3.connect(backup) as copied:
                self.assertEqual(copied.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(copied.execute("SELECT count(*) FROM live_rows").fetchone()[0], 37)
        finally:
            writer.close()

    def test_02c_public_build_count_gate_scales_with_legitimate_additions(self):
        changed = json.loads(STATE.read_text(encoding="utf-8"))
        original_count = len(changed["companies"])
        changed["companies"].append({
            "id": "legitimate-new-public-company", "name": "Legitimate New Public Company",
            "status": "private", "country": "US", "region": "US", "sector": "AI Software",
            "stage": "seed", "companyDescription": "Public company profile for count-gate regression.",
        })
        changed_file = self.tmp / "public-build-added-company.json"
        public_file = self.tmp / "public-build-added-company.public.json"
        db = self.tmp / "public-build-added-company.sqlite"
        changed_file.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        result = run_json("python3", str(PUBLIC_BUILD), "--state-file", str(changed_file),
                          "--public-state-file", str(public_file), "--db", str(db))
        self.assertEqual(result["publicCompanyCount"], original_count + 1)
        public = json.loads(public_file.read_text(encoding="utf-8"))
        self.assertEqual(public["meta"]["publicCompanyCount"], original_count + 1)
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM canonical_tasks").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT count(*) FROM canonical_relationships").fetchone()[0], 0)
            self.assertEqual({row[0] for row in conn.execute("SELECT DISTINCT provider_object_type FROM raw_records")},
                             {"organization", "funding_round", "evidence"})

    def test_02d_public_build_removes_evidence_prose_metadata_coverage_and_operational_asks(self):
        changed = json.loads(STATE.read_text(encoding="utf-8"))
        markers = ("Diligence ask", "Ask for BOARD_PACK_NEXT_ACTION_7f91", "NEXT_ACTION_INSTRUCTION_7f91")
        changed["meta"]["coverage"] = "Diligence ask: Ask for COVERAGE_NEXT_ACTION_7f91"
        changed["companies"][0]["nextAction"] = markers[2]
        changed["companies"][0]["evidence"][0]["note"] = f"{markers[0]}: {markers[1]}"
        changed["companies"][0]["latestFinancing"] = {
            "roundType": "Series Z", "amountDisplay": "$1m", "announcedDate": changed["companies"][0]["evidence"][0].get("date"),
            "financingType": "equity", "valuation": "VALUATION_MUST_NOT_LEAK_7f91",
        }
        source = self.tmp / "adversarial-public-build.json"
        public_file = self.tmp / "adversarial-public-build.public.json"
        db = self.tmp / "adversarial-public-build.sqlite"
        source.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        run_json("python3", str(PUBLIC_BUILD), "--state-file", str(source),
                 "--public-state-file", str(public_file), "--db", str(db))
        snapshot_text = public_file.read_text(encoding="utf-8")
        for marker in markers:
            self.assertNotIn(marker, snapshot_text)
        self.assertNotIn("VALUATION_MUST_NOT_LEAK_7f91", snapshot_text)
        with sqlite3.connect(db) as conn:
            raw_payloads = [json.loads(row[0]) for row in conn.execute("SELECT payload_json FROM raw_records")]
        raw_text = json.dumps(raw_payloads, ensure_ascii=False)
        for marker in markers:
            self.assertNotIn(marker, raw_text)
        self.assertFalse(any(key in {"note", "coverage"}
                             for payload in raw_payloads
                             for _, key, _ in self._walk(payload)))

    def test_02e_python_public_build_rejects_exact_standalone_secret_classes(self):
        samples = [
            "Bearer abcdefghijklmnopqrstuvwxyz012345", "AKIAABCDEFGHIJKLMNOP",
            "eyJabcdefghi.abcdefghijkl.abcdefghijkl", "sk-abcdefghijklmnopqrstuvwxyz123456",
            "sk-proj-abcdefghijklmnopqrstuvwxyz123456", "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "github_pat_11AAabcdefghijklmnopqrstuvwxyz123456", "xox" + "b-" + "a" * 40,
            "AIzaSyDabcdefghijklmnopqrstuvwxyz123456", "sk_" + "live_" + "a" * 32,
            "pk_" + "live_" + "a" * 32, "-----BEGIN OPENSSH PRIVATE KEY-----",
        ]
        code = (
            "import json,sys;sys.path.insert(0,sys.argv[1]);"
            "from build_public_v2_db import SENSITIVE;"
            "print(json.dumps([bool(SENSITIVE.search(x)) for x in json.loads(sys.argv[2])]))"
        )
        result = subprocess.run(["python3", "-c", code, str(ROOT / "scripts"), json.dumps(samples)],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), [True] * len(samples))

    @staticmethod
    def _walk(value, path="$"):
        if isinstance(value, dict):
            for key, child in value.items():
                yield f"{path}.{key}", key, child
                yield from PrivateInvestmentOsV2Tests._walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from PrivateInvestmentOsV2Tests._walk(child, f"{path}[{index}]")

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
        self.assertEqual(lineage["data"]["publicationStatus"], "public_projection")
        self.assertTrue(all(value is False for value in lineage["data"]["redaction"].values()))
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
        self.assertTrue(all(set(item) <= {"type", "url", "asOf", "confidence"} for item in evidence["data"]))

    def test_06b_internal_only_values_are_removed_from_all_public_v2_projections(self):
        timestamp = "2026-08-02T00:00:00Z"
        with sqlite3.connect(self.db) as conn:
            conn.execute("""INSERT INTO ingestion_runs(
                id,source_id,connector_version,started_at,status,request_fingerprint
              ) VALUES('run_rights_projection','pitchbook_csv_v1','test',?,'completed','test-rights-projection')""",
                (timestamp,))
            conn.execute("""INSERT INTO raw_records(
                id,source_id,ingestion_run_id,provider_object_type,provider_object_id,
                ingested_at,payload_json,payload_sha256,rights_profile_id
              ) VALUES('raw_rights_projection','pitchbook_csv_v1','run_rights_projection','organization','rights-test',
                ?, '{}', ?, 'internal_only')""", (timestamp, "b" * 64))
            conn.execute("""INSERT INTO organizations(
                id,canonical_name,legal_name,organization_type,status,country,region,hq_location,website,
                description,source_record_id,created_at,updated_at
              ) VALUES('org_rights_test','SECRET COMPANY','SECRET LEGAL','company','private','SECRET COUNTRY',
                'SECRET REGION','SECRET HQ','https://secret.invalid','SECRET DESCRIPTION','raw_rights_projection',?,?)""",
                (timestamp, timestamp))
            conn.execute("""INSERT INTO organization_aliases VALUES(
                'alias_rights_test','org_rights_test','SECRET ALIAS','provider_name',NULL,
                'raw_rights_projection','high')""")
            conn.execute("""INSERT INTO opportunities(
                id,organization_id,opportunity_type,stage,status,owner,thesis,next_action,created_at,updated_at
              ) VALUES(
                'opp_rights_test','org_rights_test','direct','SECRET STAGE','open','SECRET OWNER',
                'SECRET THESIS','SECRET ACTION',?,?)""", (timestamp, timestamp))
            conn.execute("""INSERT INTO canonical_field_decisions VALUES(
                'decision_rights_test','org_rights_test','identity.canonicalName','\"SECRET DECISION\"',
                'raw_rights_projection','provider_selected','test',?)""", (timestamp,))
            conn.execute("""INSERT INTO canonical_funding_rounds(
                id,organization_id,announced_date,round_type,amount_value,amount_currency,amount_display,
                post_money_value,valuation_currency,valuation_display,status,canonical_confidence,
                selected_source_record_id,created_at,updated_at
              ) VALUES('round_rights_test','org_rights_test','2026-01-01','SECRET ROUND',999,'USD','$999 SECRET',
                9999,'USD','$9999 SECRET','confirmed','high','raw_rights_projection',?,?)""", (timestamp, timestamp))
            metric_definition = conn.execute("SELECT id FROM metric_definitions LIMIT 1").fetchone()[0]
            conn.execute("""INSERT INTO metric_observations(
                id,organization_id,metric_definition_id,value_numeric,value_text,source_record_id,confidence,is_canonical
              ) VALUES('metric_rights_test','org_rights_test',?,123,'SECRET METRIC','raw_rights_projection','high',1)""",
                (metric_definition,))
            conn.commit()

        paths = (
            "/api/v2/companies/org_rights_test",
            "/api/v2/companies/org_rights_test/funding-rounds",
            "/api/v2/companies/org_rights_test/metrics",
            "/api/v2/companies/org_rights_test/lineage",
        )
        responses = []
        for path in paths:
            status, payload = self.http(path)
            self.assertEqual(status, 404, path)
            responses.append(payload)
        serialized = json.dumps(responses)
        self.assertNotIn("SECRET", serialized)
        self.assertTrue(all(item["error"]["code"] == "NOT_FOUND" for item in responses))
        _, search = self.http("/api/v2/companies?q=SECRET")
        self.assertEqual(search["data"], [])

    def test_07_connector_statuses_and_quality(self):
        _, sources = self.http("/api/v2/sources")
        serialized = json.dumps(sources).lower()
        self.assertNotIn("crunchbase", serialized)
        self.assertNotIn("dealroom", serialized)
        self.assertNotIn("pitchbook", serialized)
        self.assertTrue(all(set(row) == {"sourceClass", "status", "accessMode"} for row in sources["data"]))
        _, quality = self.http("/api/v2/data-quality")
        self.assertEqual(set(quality["summary"]), {"publicCoverageGaps"})

    def test_06d_restricted_aliases_and_external_ids_do_not_resolve_visible_companies(self):
        timestamp = "2026-08-02T00:00:00Z"
        with sqlite3.connect(self.db) as conn:
            conn.execute("""INSERT INTO ingestion_runs(
              id,source_id,connector_version,started_at,status,request_fingerprint)
              VALUES('run_restricted_identifier','pitchbook_csv_v1','test',?,'completed','restricted-id')""", (timestamp,))
            conn.execute("""INSERT INTO raw_records(
              id,source_id,ingestion_run_id,provider_object_type,provider_object_id,ingested_at,
              payload_json,payload_sha256,rights_profile_id)
              VALUES('raw_restricted_identifier','pitchbook_csv_v1','run_restricted_identifier','organization',
              'restricted-id',?,'{}',?,'internal_only')""", (timestamp, "d" * 64))
            conn.execute("""INSERT INTO organization_aliases VALUES(
              'alias_restricted_identifier','org_databricks','TOP_SECRET_ALIAS','licensed_name',NULL,
              'raw_restricted_identifier','high')""")
            conn.execute("""INSERT INTO external_ids VALUES(
              'ext_restricted_identifier','org_databricks','pitchbook_csv_v1','company','TOP_SECRET_EXTERNAL',
              0,'raw_restricted_identifier')""")
            conn.commit()
        for identifier in ("TOP_SECRET_ALIAS", "TOP_SECRET_EXTERNAL"):
            status, payload = self.http("/api/v2/companies/" + identifier)
            self.assertEqual(status, 404)
            self.assertEqual(payload["error"]["code"], "NOT_FOUND")
            self.assertNotIn(identifier, json.dumps(payload))
        status, _ = self.http("/api/v2/companies/databricks")
        self.assertEqual(status, 200)

    def test_06e_standalone_tokens_absolute_paths_and_unsafe_websites_are_removed(self):
        public_raw = None
        with sqlite3.connect(self.db) as conn:
            public_raw = conn.execute("SELECT id FROM raw_records WHERE source_id='legacy_state_json' LIMIT 1").fetchone()[0]
            samples = (
                "Bearer abcdefghijklmnopqrstuvwxyz012345",
                "AKIAABCDEFGHIJKLMNOP",
                "eyJabcdefghi.abcdefghijkl.abcdefghijkl",
                "sk-abcdefghijklmnopqrstuvwxyz123456",
                "sk-proj-abcdefghijklmnopqrstuvwxyz123456",
                "ghp_abcdefghijklmnopqrstuvwxyz123456",
                "github_pat_11AAabcdefghijklmnopqrstuvwxyz123456",
                "xox" + "b-" + "a" * 40,
                "AIzaSyDabcdefghijklmnopqrstuvwxyz123456",
                "sk_" + "live_" + "a" * 32,
                "pk_" + "live_" + "a" * 32,
                "-----BEGIN OPENSSH PRIVATE KEY-----",
                "/opt/render/project/src/private.json",
                "/custom/root/private.json",
            )
            from scripts.query_v2_db import PublicProjectionPolicy
            for sample in samples:
                self.assertRegex(sample, PublicProjectionPolicy.SENSITIVE_TEXT)
            for index, sample in enumerate(samples):
                conn.execute("""INSERT INTO canonical_evidence_items VALUES(
                  ?, 'org_databricks','manual',?,NULL,NULL,'high',?,1)""",
                  (f"evidence_sensitive_{index}", sample, public_raw))
            conn.execute("UPDATE organizations SET website='javascript:alert(1)' WHERE id='org_databricks'")
            conn.execute("DELETE FROM canonical_field_decisions WHERE organization_id='org_databricks' AND field_path='identity.website'")
            conn.commit()
        _, evidence = self.http("/api/v2/companies/databricks/evidence")
        serialized = json.dumps(evidence)
        for marker in ("Bearer", "AKIA", "eyJ", "sk-", "ghp_", "github_pat_", "xoxb-", "AIza",
                       "sk_live_", "pk_live_", "PRIVATE KEY", "/opt/render", "/custom/root"):
            self.assertNotIn(marker, serialized)
        _, company = self.http("/api/v2/companies/databricks")
        self.assertIsNone(company["data"]["identity"]["website"])

    def test_06c_null_lineage_mixed_funding_and_secret_text_fail_closed(self):
        timestamp = "2026-08-02T00:00:00Z"
        with sqlite3.connect(self.db) as conn:
            conn.execute("""INSERT INTO organizations(id,canonical_name,organization_type,status,created_at,updated_at)
              VALUES('org_null_lineage','NULL LINEAGE SECRET','company','private',?,?)""", (timestamp, timestamp))
            public_raw = conn.execute("SELECT id FROM raw_records WHERE source_id='legacy_state_json' LIMIT 1").fetchone()[0]
            conn.execute("""INSERT INTO opportunities(
              id,organization_id,opportunity_type,stage,status,next_action,created_at,updated_at)
              VALUES('opp_null','org_databricks','direct','seed','open','NULL PROVENANCE SECRET',?,?)""", (timestamp, timestamp))
            conn.execute("""INSERT INTO canonical_evidence_items VALUES(
              'evidence_secret_path','org_databricks','manual',?,NULL,NULL,'high',?,1)""",
              (r"credential token=sk-test-secret C:\\Users\\name\\file.csv", public_raw))
            round_id = conn.execute("SELECT id FROM canonical_funding_rounds WHERE organization_id='org_databricks' LIMIT 1").fetchone()[0]
            conn.execute("UPDATE canonical_funding_rounds SET round_type='MIXED SOURCE SECRET' WHERE id=?", (round_id,))
            conn.execute("UPDATE canonical_funding_rounds SET metadata_json=? WHERE id=?",
                         (json.dumps({"financingType": "debt"}), round_id))
            conn.execute("""INSERT INTO funding_round_sources(id,funding_round_id,source_record_id,field_map_json,confidence,is_selected)
              VALUES('mixed_internal_source',?,'raw_rights_projection','{"round":"round_type","financingType":"metadata.financingType"}','high',0)""", (round_id,))
            conn.commit()
        _, listing = self.http("/api/v2/companies?limit=100&q=NULL LINEAGE SECRET")
        self.assertEqual(listing["data"], [])
        status, _ = self.http("/api/v2/companies/org_null_lineage")
        self.assertEqual(status, 404)
        _, company = self.http("/api/v2/companies/databricks")
        self.assertNotIn("NULL PROVENANCE SECRET", json.dumps(company))
        _, funding = self.http("/api/v2/companies/databricks/funding-rounds")
        self.assertNotIn("MIXED SOURCE SECRET", json.dumps(funding))
        self.assertFalse(any(row.get("financingType") == "debt" for row in funding["data"]))
        _, evidence = self.http("/api/v2/companies/databricks/evidence")
        serialized = json.dumps(evidence)
        self.assertNotIn("sk-test-secret", serialized)
        self.assertNotIn("Users", serialized)

    def test_07a_lifecycle_taxonomy_filter_and_conservative_gap(self):
        _, page = self.http("/api/v2/companies?limit=100")
        allowed = {"formation_pre_seed", "seed", "series_a_b", "growth_late_stage", "pre_ipo",
                   "secondary_tender", "crossover_pipe_strategic", "project_finance", "stage_unverified"}
        self.assertTrue(all(row["lifecycle"]["stage"] in allowed for row in page["data"]))
        unverified = [row for row in page["data"] if row["lifecycle"]["stage"] == "stage_unverified"]
        self.assertTrue(unverified)
        self.assertTrue(all("stage_precision" in row["lifecycle"]["coverageGaps"] for row in unverified))
        _, filtered = self.http("/api/v2/companies?limit=100&stage=stage_unverified")
        self.assertTrue(all(row["lifecycle"]["stage"] == "stage_unverified" for row in filtered["data"]))

    def test_08_v1_contract_and_read_only_guard(self):
        for path in ("/api/state", "/api/pipeline", "/api/company/databricks"):
            status, payload = self.http(path)
            self.assertEqual(status, 200, path)
            self.assertIsInstance(payload, dict)
        status, payload = self.http("/api/ops")
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "NOT_FOUND"})
        status, payload = self.http("/api/company/databricks", "POST", b"{}")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "READ_ONLY_DEPLOYMENT")
        status, payload = self.http("/api/v2/imports/preview", "POST", b"{}")
        self.assertEqual(status, 403)
        self.assertEqual(payload["error"]["code"], "READ_ONLY_DEPLOYMENT")

    def test_08a_error_envelopes_do_not_reflect_sensitive_paths_or_ids(self):
        status, payload = self.http("/api/v2/secret=sk-do-not-reflect/C:%5CUsers%5Cprivate")
        self.assertEqual(status, 404)
        serialized = json.dumps(payload)
        self.assertNotIn("sk-do-not-reflect", serialized)
        self.assertNotIn("Users", serialized)

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
