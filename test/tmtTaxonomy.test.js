'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const taxonomy = require('../src/tmtTaxonomy');
const projection = require('../src/publicProjection');
const lifecycle = require('../src/lifecycle');

assert.deepEqual(taxonomy.TMT_VERTICALS, [
  'AI/Cloud/Semiconductor Infrastructure','Enterprise Software','Data/Analytics','Cybersecurity/Identity',
  'Fintech/Payments/Insurtech','Commerce/Marketplaces','Consumer Internet/Media/Gaming','Digital Health',
  'Climate/Industrial Tech','Space/Communications','Robotics/Mobility','Other'
]);
const schema = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'connectors', 'tmt_seed.schema.json'), 'utf8'));
const recordProperties = schema.properties.records.items.properties;
assert.deepEqual(recordProperties.tmtVertical.enum, taxonomy.TMT_VERTICALS, 'seed schema verticals drifted from canonical taxonomy');
assert.deepEqual(recordProperties.businessModel.enum, taxonomy.BUSINESS_MODELS, 'business-model vocabulary drifted');
assert.deepEqual(recordProperties.customerType.enum, taxonomy.CUSTOMER_TYPES, 'customer-type vocabulary drifted');
assert.deepEqual(recordProperties.monetization.items.enum, taxonomy.MONETIZATION, 'monetization vocabulary drifted');
assert.deepEqual(recordProperties.investabilityAccessLane.enum, taxonomy.ACCESS_LANES, 'access-lane vocabulary drifted');
assert.equal(taxonomy.inferTmtVertical({ sector: 'identity security platform' }), 'Cybersecurity/Identity');
assert.equal(taxonomy.inferTmtVertical({ sector: 'payments infrastructure' }), 'Fintech/Payments/Insurtech');
assert.equal(taxonomy.inferTmtVertical({ sector: 'unclassified private business' }), 'Other');
assert.equal(taxonomy.inferTmtVertical({ tmtVertical: 'Digital Health', sector: 'software' }), 'Digital Health');

const source = {
  id: 'test-company', name: 'Test Company', status: 'private', sector: 'Security', tmtVertical: 'Cybersecurity/Identity',
  businessModel: 'SaaS', customerType: 'B2B', monetization: ['Subscription'], sourceVintage: '2026-07-01',
  confidence: 'high', privateStatus: 'private', privateStatusAsOf: '2026-07-01', privateStatusConfidence: 'high',
  investabilityAccessLane: 'relationship_development', aliases: ['Secret Alias'],
  classificationMethod: 'deterministic_legacy_mapping', classificationConfidence: 'derived',
  latestFinancing: { roundType: 'Series B', amountDisplay: '$80m', announcedDate: '2026-07-01', financingType: 'equity', sourceUrl: 'https://example.com/status' },
  tmtFieldEvidence: { tmtVertical: { sourceDate: '2026-07-01', seedSha256: 'private' } },
  evidence: [{ url: 'https://example.com/status', date: '2026-07-01', type: 'official', confidence: 'high', note: 'internal note',
    claimType: 'latest_financing', publicationEligible: true, rightsProfile: 'public_allowed' }]
};
const publicCompany = projection.projectCompany(source, lifecycle.lifecycleCoverage, { snapshotAsOf: '2026-08-02' });
for (const field of ['tmtVertical','businessModel','customerType','monetization','sourceVintage','confidence','privateStatus','privateStatusAsOf','privateStatusConfidence','investabilityAccessLane']) assert.ok(field in publicCompany, `${field} missing`);
assert.deepEqual(publicCompany.latestFinancing, source.latestFinancing);
assert.equal(publicCompany.completeness.classification, 'present');
assert.ok(!('valuation' in publicCompany.latestFinancing));
assert.ok(!projection.projectLatestFinancing({ ...source, latestFinancing: { ...source.latestFinancing, sourceUrl: 'javascript:alert(1)' } }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing({ ...source, evidence: [{ ...source.evidence[0], rightsProfile: 'internal_only' }] }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing({ ...source, evidence: [{ ...source.evidence[0], publicationEligible: false }] }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing({ ...source, evidence: [{ ...source.evidence[0], claimType: undefined }] }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing({ ...source, evidence: [{ url: source.latestFinancing.sourceUrl, date: source.latestFinancing.announcedDate, type: 'official' }] }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing({ ...source, evidence: [{ ...source.evidence[0], url: 'https://example.com/other' }] }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing({ ...source, evidence: [{ ...source.evidence[0], date: '2026-06-30' }] }, '2026-08-02'));
assert.ok(!projection.projectLatestFinancing(source));
assert.ok(!projection.projectLatestFinancing(source, 'malformed'));
assert.ok(!projection.projectLatestFinancing(source, '2024-01-01'));
assert.ok(!projection.projectLatestFinancing({ ...source, latestFinancing: { ...source.latestFinancing, announcedDate: '2024-07-31' }, evidence: [{ ...source.evidence[0], date: '2024-07-31' }] }, '2026-08-02'));
for (const field of ['aliases','tmtFieldEvidence','privateStatusBoundary']) assert.ok(!(field in publicCompany), `${field} leaked`);
assert.ok(!('note' in publicCompany.evidence[0]));
const noRightsCompany = projection.projectCompany({ ...source, evidence: [{ ...source.evidence[0], rightsProfile: undefined }] }, lifecycle.lifecycleCoverage, { snapshotAsOf: '2026-08-02' });
assert.deepEqual(noRightsCompany.evidence, []);
assert.ok(!noRightsCompany.latestFinancing);
console.log('✓ canonical TMT taxonomy, deterministic legacy mapping, and public projection passed');
