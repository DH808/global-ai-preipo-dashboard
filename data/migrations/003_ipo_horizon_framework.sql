-- Conservative IPO/exit monitoring horizons. These columns contain only safe,
-- canonical enums; free-text rationale and operational actions remain private.
ALTER TABLE opportunities ADD COLUMN ipo_horizon TEXT
  CHECK (ipo_horizon IN ('0_12m','12_24m','24_48m','48m_plus','evergreen_private','unknown'));
ALTER TABLE opportunities ADD COLUMN ipo_horizon_confidence TEXT
  CHECK (ipo_horizon_confidence IN ('high','medium','low','unverified'));
ALTER TABLE opportunities ADD COLUMN ipo_horizon_basis TEXT
  CHECK (ipo_horizon_basis IN ('official_filing','exchange_application','company_statement','recent_financing','secondary_liquidity','stage_heuristic','insufficient_evidence'));
ALTER TABLE opportunities ADD COLUMN ipo_horizon_classification_method TEXT
  CHECK (ipo_horizon_classification_method IN ('official_filing','exchange_application','explicit_ipo_window','recent_financing_monitor','lifecycle_stage_heuristic','insufficient_evidence'));

CREATE INDEX IF NOT EXISTS idx_opportunities_ipo_horizon
  ON opportunities(ipo_horizon, ipo_horizon_confidence, organization_id);
