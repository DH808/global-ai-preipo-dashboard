import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.import_asia_tmt_seed import run

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "state.json"
SEED = ROOT / "data" / "connectors" / "asia_tmt_seed_20260802.json"
PROFILE = ROOT / "data" / "connectors" / "asia_expansion.profile.json"
BASELINE_STATE = subprocess.check_output(["git", "show", "d0fb350:data/state.json"], cwd=ROOT)


class AsiaTmtSeedImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="asia-tmt-seed-")
        self.addCleanup(self.temp.cleanup)
        self.tmp = Path(self.temp.name)
        self.state = self.tmp / "state.json"
        self.state.write_bytes(BASELINE_STATE)
        self.seed = self.tmp / "seed.json"
        self.seed.write_bytes(SEED.read_bytes())

    def mutate(self, callback):
        value = json.loads(SEED.read_text(encoding="utf-8"))
        callback(value)
        self.seed.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def result(self, apply=False):
        return run(self.seed, self.state, PROFILE, apply, date(2026, 8, 2))

    def test_preview_apply_and_digest_replay_are_atomic(self):
        before = self.state.read_bytes()
        preview = self.result()
        self.assertEqual(preview["status"], "valid")
        self.assertEqual((preview["beforeCompanyCount"], preview["afterCompanyCount"]), (167, 171))
        self.assertEqual((preview["summary"]["created"], preview["summary"]["matched"]), (4, 1))
        self.assertEqual(self.state.read_bytes(), before)
        applied = self.result(True)
        self.assertTrue(applied["mutated"])
        replay = self.result(True)
        self.assertTrue(replay["summary"]["alreadyApplied"])
        self.assertFalse(replay["mutated"])
        self.assertEqual(replay["applicationSha256"], applied["applicationSha256"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(len(state["companies"]), 171)
        self.assertEqual(len(state["meta"]["asiaSeedImports"]), 1)
        receipt = state["meta"]["asiaSeedImports"][0]
        self.assertEqual(receipt["expectedPostCompanyCount"], 171)
        self.assertEqual(len(receipt["stateBusinessSha256"]), 64)
        self.assertEqual(len(receipt["identityGraphSha256"]), 64)
        self.assertEqual(len(receipt["receiptSha256"]), 64)

    def test_existing_match_preserved_and_deterministic_backfill(self):
        before = json.loads(BASELINE_STATE)
        original = next(row for row in before["companies"] if row["id"] == "moonshot-ai")
        self.result(True)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in state["companies"]}
        moonshot = by_id["moonshot-ai"]
        for field in ("id", "name", "country", "region", "status", "stage", "layer", "ipoSignal"):
            self.assertEqual(moonshot.get(field), original.get(field))
        self.assertEqual(moonshot["evidence"][:len(original["evidence"])], original["evidence"])
        taiwan = [row for row in state["companies"] if row.get("country") == "Taiwan"]
        self.assertEqual(len(taiwan), 10)
        self.assertTrue(all(row["regionalExposureProfile"]["tags"] == ["taiwan"] and row["regionalExposureProfile"]["accessLane"] == "taiwan_market_access" for row in taiwan))
        for country, tag, lane in (("China", "china", "monitor_or_strategic_relationship"), ("Japan", "japan", "relationship_or_local_private"), ("South Korea", "south_korea", "relationship_or_local_private")):
            rows = [row for row in state["companies"] if row.get("country") == country]
            self.assertTrue(rows)
            self.assertTrue(all(tag in row["regionalExposureProfile"]["tags"] and row["regionalExposureProfile"]["accessLane"] == lane for row in rows))
        self.assertEqual(by_id["moloco"]["country"], "United States")
        self.assertEqual(by_id["moloco"]["regionalExposureProfile"]["lineage"], "reviewed_explicit_exposure")

    def test_financing_and_source_boundaries(self):
        self.result(True)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in state["companies"]}
        ids = {"moonshot-ai", "pixverse", "layerx", "moloco", "viva-republica"}
        financed = {row["id"] for row in state["companies"] if row["id"] in ids and row.get("latestFinancing")}
        self.assertEqual(financed, {"moonshot-ai", "pixverse", "layerx"})
        self.assertNotIn("latestFinancing", by_id["moloco"])
        self.assertNotIn("latestFinancing", by_id["viva-republica"])
        for company_id in financed:
            self.assertFalse(any("valuation" in key.lower() for key in by_id[company_id]["latestFinancing"]))
            source = by_id[company_id]["evidence"][-1]
            self.assertEqual((source["rightsProfile"], source["publicationEligible"], source["claimType"]), ("public_allowed", True, "latest_financing"))
        self.assertEqual(by_id["moloco"]["sourceVintage"], "2024-08-31")
        self.assertEqual(by_id["viva-republica"]["sourceVintage"], "2024-08-31")
        self.assertEqual(by_id["moonshot-ai"]["latestFinancing"]["amountDisplay"], "about $2B")
        self.assertEqual((by_id["pixverse"]["businessModel"], by_id["pixverse"]["customerType"], by_id["pixverse"]["monetization"]), ("Usage-based", "Mixed", ["Usage-based"]))
        self.assertEqual((by_id["layerx"]["businessModel"], by_id["layerx"]["customerType"], by_id["layerx"]["monetization"]), ("SaaS", "B2B", ["Other"]))
        self.assertEqual((by_id["moonshot-ai"]["businessModel"], by_id["moonshot-ai"]["customerType"], by_id["moonshot-ai"]["monetization"]), ("Usage-based", "Mixed", ["Subscription", "Usage-based"]))
        self.assertEqual((by_id["moloco"]["businessModel"], by_id["moloco"]["customerType"], by_id["moloco"]["monetization"]), ("Advertising", "B2B", ["Advertising"]))
        self.assertEqual(by_id["viva-republica"]["monetization"], ["Other"])

    def test_canonical_viva_identity_and_alias_resolution(self):
        self.result(True)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in state["companies"]}
        self.assertNotIn("toss", by_id)
        viva = by_id["viva-republica"]
        self.assertEqual((viva["name"], viva["aliases"]), ("Viva Republica", ["Toss"]))
        tokens = lambda value: "".join(ch for ch in value.casefold() if ch.isalnum())
        resolved = {tokens(value): row["id"] for row in state["companies"] for value in [row.get("name", ""), *(row.get("aliases") or [])]}
        self.assertEqual(resolved[tokens("Toss")], "viva-republica")
        self.assertEqual(resolved[tokens("Viva Republica")], "viva-republica")

    def test_unknown_array_is_replaced_but_stronger_array_is_preserved(self):
        state = json.loads(self.state.read_text(encoding="utf-8"))
        moonshot = next(row for row in state["companies"] if row["id"] == "moonshot-ai")
        moonshot["monetization"] = ["Advertising"]
        self.state.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        result = self.result(True)
        self.assertEqual(result["status"], "valid")
        applied = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(next(row for row in applied["companies"] if row["id"] == "moonshot-ai")["monetization"], ["Advertising"])

    def test_replay_revalidates_count_receipt_business_digest_and_identity_graph(self):
        self.result(True)
        pristine = self.state.read_bytes()
        mutations = [
            lambda state: state["companies"].pop(),
            lambda state: next(row for row in state["companies"] if row["id"] == "pixverse").update(customerType="B2B"),
            lambda state: state["meta"]["asiaSeedImports"][0].update(expectedPostCompanyCount=170),
            lambda state: state["meta"]["asiaSeedImports"][0].update(receiptSha256="0" * 64),
            lambda state: state["companies"].append({"id": "duplicate-viva", "name": "Viva Republica", "aliases": [], "status": "private"}),
            lambda state: next(row for row in state["companies"] if row["id"] == "pixverse")["aliases"].append("Toss"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                state = json.loads(pristine)
                mutation(state)
                self.state.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                before = self.state.read_bytes()
                replay = self.result(True)
                self.assertEqual(replay["status"], "invalid")
                self.assertFalse(replay.get("mutated", False))
                self.assertEqual(self.state.read_bytes(), before)

    def test_exact_already_applied_batch_is_atomically_replaced(self):
        self.result(True)
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        manifest = seed["replacement"]
        state = json.loads(self.state.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in state["companies"]}
        for guard in manifest["guardedFieldReplacements"]:
            by_id[guard["id"]][guard["field"]] = guard["from"]
        viva = by_id["viva-republica"]
        viva.update(id="toss", name="Toss", aliases=["Viva Republica"], monetization=["Transaction fees", "Interest/net interest"])
        viva.pop("privateStatusVerificationDue")
        by_id["moloco"].pop("privateStatusVerificationDue")
        state["meta"]["asiaSeedImports"] = [manifest["supersededReceipt"]]
        self.state.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

        replaced = self.result(True)
        self.assertEqual(replaced["status"], "valid")
        self.assertTrue(replaced["summary"]["replacement"]["performed"])
        self.assertEqual((replaced["beforeCompanyCount"], replaced["afterCompanyCount"]), (171, 171))
        final = json.loads(self.state.read_text(encoding="utf-8"))
        final_ids = {row["id"] for row in final["companies"]}
        self.assertNotIn("toss", final_ids)
        self.assertIn("viva-republica", final_ids)
        self.assertEqual(len(final["meta"]["asiaSeedImports"]), 1)
        self.assertEqual(final["meta"]["asiaSeedImports"][0]["replacesApplicationSha256"], manifest["supersededReceipt"]["applicationSha256"])
        self.assertTrue(self.result(True)["summary"]["alreadyApplied"])

    def test_fail_closed_cases_do_not_write(self):
        mutations = [
            lambda seed: seed["review"].update(status="pending"),
            lambda seed: seed["records"][1]["aliases"].append("Moonshot AI"),
            lambda seed: seed["records"][0]["sources"][0].update(rightsProfile="internal_only"),
            lambda seed: seed["records"][0]["sources"][0].update(claimTypes=["company_profile", "private_status", "latest_financing"]),
            lambda seed: seed["records"][4].update(sourceVintage="2023-01-01"),
            lambda seed: seed["records"][0]["privateStatusBoundary"].update(status="public"),
            lambda seed: seed["records"][0]["latestFinancing"].update(postMoneyValuation="$20b"),
            lambda seed: seed["records"][0].update(headquartersCountry="Canada"),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.seed.write_bytes(SEED.read_bytes())
                before = self.state.read_bytes()
                self.mutate(mutation)
                result = self.result(True)
                self.assertEqual(result["status"], "invalid")
                self.assertEqual(self.state.read_bytes(), before)

    def test_public_v1_v2_counts_projection_financing_and_schema_002(self):
        self.result(True)
        public_state, db = self.tmp / "public-state.json", self.tmp / "public.sqlite"
        built = subprocess.run(["python3", str(ROOT / "scripts" / "build_public_v2_db.py"), "--state-file", str(self.state), "--public-state-file", str(public_state), "--db", str(db)], cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(built.stdout)["publicCompanyCount"], 171)
        snapshot = json.loads(public_state.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in snapshot["companies"]}
        self.assertEqual(snapshot["meta"]["publicCompanyCount"], 171)
        self.assertEqual(by_id["moloco"]["regionalExposure"], ["south_korea"])
        self.assertEqual(by_id["moloco"]["regionalExposureLineage"], "reviewed_explicit_exposure")
        self.assertEqual(by_id["viva-republica"]["regionalExposureRights"], "public_allowed")
        public_text = json.dumps(snapshot, ensure_ascii=False)
        for marker in ("regionalExposureProfile", "asiaSeedImports", "applicationSha256", "privateStatusVerificationDue", "reviewedBy", "Hermes Asia source-gate", '"nextAction":', '"owner":'):
            self.assertNotIn(marker, public_text)
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0], "002")
            rows = conn.execute("SELECT organization_id,valuation_display,post_money_value,metadata_json FROM canonical_funding_rounds WHERE organization_id IN ('org_moonshot-ai','org_pixverse','org_layerx','org_moloco','org_viva-republica')").fetchall()
            structured = [row for row in rows if json.loads(row[3] or "{}").get("financingType")]
            self.assertEqual({row[0] for row in structured}, {"org_moonshot-ai", "org_pixverse", "org_layerx"})
            self.assertTrue(all(row[1] is None and row[2] is None for row in structured))
        env = os.environ.copy(); env.update({"PIPELINE_V2_DB_FILE": str(db), "PUBLIC_STATE_FILE": str(public_state), "NODE_ENV": "production", "ENABLE_WRITES": "false"})
        def http(path):
            request = json.dumps({"path": path, "method": "GET", "body": ""})
            return json.loads(subprocess.run(["node", "test/api_contract_runner_v2.js", request], cwd=ROOT, env=env, text=True, capture_output=True, check=True).stdout)["payload"]
        v1 = http("/api/state?regionalExposure=taiwan")
        self.assertEqual(v1["dashboard"]["total"], 10)
        self.assertTrue(all(row["regionalExposure"] == ["taiwan"] for row in v1["companies"]))
        v2 = http("/api/v2/companies?regionalExposure=south_korea&limit=100")
        self.assertTrue({"moloco", "viva-republica"} <= {row["legacySlug"] for row in v2["data"]})

    def test_stale_private_status_evidence_drops_from_future_public_build(self):
        self.result(True)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        state["meta"]["asOf"] = "2026-09-01"
        self.state.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        public_state, db = self.tmp / "future-public-state.json", self.tmp / "future-public.sqlite"
        subprocess.run(["python3", str(ROOT / "scripts" / "build_public_v2_db.py"), "--state-file", str(self.state), "--public-state-file", str(public_state), "--db", str(db)], cwd=ROOT, text=True, capture_output=True, check=True)
        snapshot = json.loads(public_state.read_text(encoding="utf-8"))
        by_id = {row["id"]: row for row in snapshot["companies"]}
        self.assertEqual(by_id["moloco"]["evidence"], [])
        self.assertEqual(by_id["viva-republica"]["evidence"], [])


if __name__ == "__main__":
    unittest.main()
