#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { withIpoHorizon, horizonDistribution, validIpoHorizonFields } = require('../src/ipoHorizon');

function main() {
  const target = path.resolve(process.argv[2] || path.join(__dirname, '..', 'data', 'state.json'));
  const original = fs.readFileSync(target, 'utf8');
  const state = JSON.parse(original);
  if (!Array.isArray(state.companies) || !state.companies.length) throw new Error('IPO_HORIZON_COMPANIES_REQUIRED');
  const ids = new Set(state.companies.map(company => company.id));
  if (ids.size !== state.companies.length) throw new Error('IPO_HORIZON_DUPLICATE_COMPANY_ID');
  state.companies = state.companies.map(company => withIpoHorizon(company, { asOf: state.meta?.asOf }));
  if (!state.companies.every(validIpoHorizonFields)) throw new Error('IPO_HORIZON_BACKFILL_INVALID');
  const distribution = horizonDistribution(state.companies);
  state.meta.ipoHorizonFramework = {
    version: '1', companyCount: state.companies.length, distribution,
    evidenceGapCount: state.companies.filter(company => company.coverageGaps.includes('ipo_horizon_evidence')).length
  };
  const output = JSON.stringify(state, null, 2) + '\n';
  if (output === original) return process.stdout.write(JSON.stringify({ status: 'unchanged', companyCount: state.companies.length, distribution }) + '\n');
  const temporary = `${target}.ipo-horizon-${process.pid}.tmp`;
  try {
    fs.writeFileSync(temporary, output, { encoding: 'utf8', mode: 0o600 });
    fs.renameSync(temporary, target);
  } finally { if (fs.existsSync(temporary)) fs.unlinkSync(temporary); }
  process.stdout.write(JSON.stringify({ status: 'updated', companyCount: state.companies.length, distribution }) + '\n');
}

main();
