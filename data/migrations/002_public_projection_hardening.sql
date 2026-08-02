-- Public projection hardening. Opportunities now carry record provenance.
-- Existing rows remain NULL until an authorized importer explicitly attributes them;
-- the public projector treats NULL as non-redistributable.
ALTER TABLE opportunities ADD COLUMN source_record_id TEXT REFERENCES raw_records(id);

CREATE INDEX IF NOT EXISTS idx_opportunities_public_source
  ON opportunities(organization_id, source_record_id);
