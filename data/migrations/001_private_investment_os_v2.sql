-- Private Investment Opportunity OS v2, Phase 1.
-- RAW tables are append-only ingestion records. CANONICAL tables are provider
-- neutral. SERVING/AUDIT tables contain rebuildable projections and checks.

CREATE TABLE IF NOT EXISTS source_rights_profiles (
  id TEXT PRIMARY KEY,
  redistribution TEXT NOT NULL CHECK (redistribution IN ('internal_only','sanitized_derived','public_allowed')),
  raw_retention_policy TEXT NOT NULL,
  quote_limit INTEGER,
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connector_registry (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  provider_type TEXT NOT NULL,
  access_mode TEXT NOT NULL,
  connector_status TEXT NOT NULL,
  credential_env_var TEXT,
  rights_profile_id TEXT NOT NULL REFERENCES source_rights_profiles(id),
  refresh_policy TEXT NOT NULL,
  capabilities_json TEXT NOT NULL DEFAULT '[]',
  last_success_at TEXT,
  last_error_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES connector_registry(id),
  connector_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT NOT NULL,
  cursor_in TEXT,
  cursor_out TEXT,
  records_seen INTEGER NOT NULL DEFAULT 0,
  records_inserted INTEGER NOT NULL DEFAULT 0,
  records_rejected INTEGER NOT NULL DEFAULT 0,
  request_fingerprint TEXT NOT NULL,
  error_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE(source_id, request_fingerprint)
);

CREATE TABLE IF NOT EXISTS raw_records (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES connector_registry(id),
  ingestion_run_id TEXT NOT NULL REFERENCES ingestion_runs(id),
  provider_object_type TEXT NOT NULL,
  provider_object_id TEXT NOT NULL,
  observed_at TEXT,
  source_updated_at TEXT,
  ingested_at TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  rights_profile_id TEXT NOT NULL REFERENCES source_rights_profiles(id),
  supersedes_raw_record_id TEXT REFERENCES raw_records(id),
  UNIQUE(source_id, provider_object_type, provider_object_id, payload_sha256)
);

CREATE INDEX IF NOT EXISTS idx_raw_records_run ON raw_records(ingestion_run_id);
CREATE INDEX IF NOT EXISTS idx_raw_records_lookup ON raw_records(source_id, provider_object_type, provider_object_id);

CREATE TRIGGER IF NOT EXISTS raw_records_no_update
BEFORE UPDATE ON raw_records BEGIN SELECT RAISE(ABORT, 'RAW_RECORDS_ARE_IMMUTABLE'); END;
CREATE TRIGGER IF NOT EXISTS raw_records_no_delete
BEFORE DELETE ON raw_records BEGIN SELECT RAISE(ABORT, 'RAW_RECORDS_ARE_IMMUTABLE'); END;

CREATE TABLE IF NOT EXISTS organizations (
  id TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  legal_name TEXT,
  organization_type TEXT NOT NULL,
  status TEXT NOT NULL,
  country TEXT,
  region TEXT,
  hq_location TEXT,
  founded_date TEXT,
  website TEXT,
  description TEXT,
  source_record_id TEXT REFERENCES raw_records(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  record_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_organizations_type_name ON organizations(organization_type, canonical_name);
CREATE INDEX IF NOT EXISTS idx_organizations_filters ON organizations(organization_type, region, status, id);

CREATE TABLE IF NOT EXISTS organization_aliases (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  alias TEXT NOT NULL,
  alias_type TEXT NOT NULL,
  language TEXT,
  source_record_id TEXT REFERENCES raw_records(id),
  confidence TEXT NOT NULL,
  UNIQUE(organization_id, alias, alias_type)
);

CREATE TABLE IF NOT EXISTS external_ids (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  source_id TEXT NOT NULL REFERENCES connector_registry(id),
  provider_object_type TEXT NOT NULL,
  provider_object_id TEXT NOT NULL,
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  source_record_id TEXT REFERENCES raw_records(id),
  UNIQUE(source_id, provider_object_type, provider_object_id)
);

CREATE TABLE IF NOT EXISTS canonical_funding_rounds (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  announced_date TEXT,
  round_type TEXT,
  amount_value REAL,
  amount_currency TEXT,
  amount_display TEXT,
  pre_money_value REAL,
  post_money_value REAL,
  valuation_currency TEXT,
  valuation_display TEXT,
  is_secondary INTEGER NOT NULL DEFAULT 0 CHECK (is_secondary IN (0,1)),
  is_debt INTEGER NOT NULL DEFAULT 0 CHECK (is_debt IN (0,1)),
  status TEXT NOT NULL,
  canonical_confidence TEXT NOT NULL,
  selected_source_record_id TEXT REFERENCES raw_records(id),
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_canonical_rounds_org_date ON canonical_funding_rounds(organization_id, announced_date DESC, id);

CREATE TABLE IF NOT EXISTS funding_round_sources (
  id TEXT PRIMARY KEY,
  funding_round_id TEXT NOT NULL REFERENCES canonical_funding_rounds(id),
  source_record_id TEXT NOT NULL REFERENCES raw_records(id),
  field_map_json TEXT NOT NULL DEFAULT '{}',
  confidence TEXT NOT NULL,
  is_selected INTEGER NOT NULL DEFAULT 0 CHECK (is_selected IN (0,1)),
  UNIQUE(funding_round_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS canonical_investors (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL UNIQUE REFERENCES organizations(id),
  investor_type TEXT,
  geography TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_round_investors (
  id TEXT PRIMARY KEY,
  funding_round_id TEXT NOT NULL REFERENCES canonical_funding_rounds(id),
  investor_id TEXT NOT NULL REFERENCES canonical_investors(id),
  role TEXT NOT NULL,
  source_record_id TEXT REFERENCES raw_records(id),
  confidence TEXT NOT NULL,
  UNIQUE(funding_round_id, investor_id, role)
);

CREATE TABLE IF NOT EXISTS canonical_organization_investors (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  investor_id TEXT NOT NULL REFERENCES canonical_investors(id),
  relationship_type TEXT NOT NULL,
  source_record_id TEXT REFERENCES raw_records(id),
  confidence TEXT NOT NULL,
  UNIQUE(organization_id, investor_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS metric_definitions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  value_type TEXT NOT NULL,
  default_unit TEXT,
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_observations (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  metric_definition_id TEXT NOT NULL REFERENCES metric_definitions(id),
  value_numeric REAL,
  value_text TEXT,
  unit TEXT,
  currency TEXT,
  period_start TEXT,
  period_end TEXT,
  as_of TEXT,
  vintage_date TEXT,
  source_record_id TEXT NOT NULL REFERENCES raw_records(id),
  confidence TEXT NOT NULL,
  is_canonical INTEGER NOT NULL DEFAULT 0 CHECK (is_canonical IN (0,1)),
  caliber_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_metric_observations_org ON metric_observations(organization_id, metric_definition_id, as_of DESC);

CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  opportunity_type TEXT NOT NULL,
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  owner TEXT,
  thesis TEXT,
  next_action TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_stage_history (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
  from_stage TEXT,
  to_stage TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  actor TEXT NOT NULL,
  reason TEXT
);

CREATE TABLE IF NOT EXISTS canonical_evidence_items (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  evidence_type TEXT NOT NULL,
  note TEXT NOT NULL,
  source_locator TEXT,
  as_of TEXT,
  confidence TEXT NOT NULL,
  source_record_id TEXT NOT NULL REFERENCES raw_records(id),
  publication_eligible INTEGER NOT NULL DEFAULT 0 CHECK (publication_eligible IN (0,1))
);

CREATE TABLE IF NOT EXISTS canonical_claims (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  claim_type TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence TEXT NOT NULL,
  source_record_id TEXT NOT NULL REFERENCES raw_records(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_claim_evidence (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL REFERENCES canonical_claims(id),
  evidence_id TEXT NOT NULL REFERENCES canonical_evidence_items(id),
  relation TEXT NOT NULL,
  UNIQUE(claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS canonical_tasks (
  id TEXT PRIMARY KEY,
  organization_id TEXT REFERENCES organizations(id),
  title TEXT NOT NULL,
  category TEXT,
  owner TEXT,
  due_date TEXT,
  status TEXT NOT NULL,
  priority TEXT,
  notes TEXT,
  source_record_id TEXT NOT NULL REFERENCES raw_records(id)
);

CREATE TABLE IF NOT EXISTS canonical_relationships (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  route_node TEXT,
  route_type TEXT NOT NULL,
  route_description TEXT,
  access_goal TEXT,
  owner TEXT,
  next_action TEXT,
  confidence TEXT NOT NULL,
  source_record_id TEXT NOT NULL REFERENCES raw_records(id)
);

CREATE TABLE IF NOT EXISTS conflict_cases (
  id TEXT PRIMARY KEY,
  organization_id TEXT REFERENCES organizations(id),
  field_path TEXT NOT NULL,
  status TEXT NOT NULL,
  severity TEXT NOT NULL,
  candidate_values_json TEXT NOT NULL,
  source_record_ids_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS canonical_field_decisions (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  field_path TEXT NOT NULL,
  selected_value_json TEXT NOT NULL,
  selected_source_record_id TEXT REFERENCES raw_records(id),
  rule TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  UNIQUE(organization_id, field_path)
);

CREATE TABLE IF NOT EXISTS decision_events (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT REFERENCES opportunities(id),
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  decision_type TEXT NOT NULL,
  decision TEXT NOT NULL,
  rationale TEXT,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcome_reviews (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT REFERENCES opportunities(id),
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  outcome_type TEXT NOT NULL,
  outcome_json TEXT NOT NULL,
  reviewed_by TEXT NOT NULL,
  reviewed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS readiness_gates (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  gate_type TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT,
  computed_at TEXT NOT NULL,
  method_version TEXT NOT NULL,
  UNIQUE(organization_id, gate_type)
);

CREATE TABLE IF NOT EXISTS company_change_feed (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL REFERENCES organizations(id),
  change_type TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  summary TEXT NOT NULL,
  source_record_id TEXT REFERENCES raw_records(id)
);

CREATE TABLE IF NOT EXISTS data_quality_checks (
  id TEXT PRIMARY KEY,
  organization_id TEXT REFERENCES organizations(id),
  check_type TEXT NOT NULL,
  status TEXT NOT NULL,
  severity TEXT NOT NULL,
  field_path TEXT,
  message TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  source_record_id TEXT REFERENCES raw_records(id),
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_dq_status_type ON data_quality_checks(status, check_type, organization_id);

CREATE TABLE IF NOT EXISTS import_idempotency_keys (
  idempotency_key TEXT PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES connector_registry(id),
  input_sha256 TEXT NOT NULL,
  ingestion_run_id TEXT REFERENCES ingestion_runs(id),
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projection_snapshots (
  id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  projection_type TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  payload_sha256 TEXT NOT NULL,
  qc_status TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
