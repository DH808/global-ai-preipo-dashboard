#!/usr/bin/env node
'use strict';

const { withIpoHorizon, horizonDistribution, validIpoHorizonFields, IPO_HORIZON_GAP } = require('../src/ipoHorizon');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => {
  input += chunk;
  if (input.length > 20 * 1024 * 1024) throw new Error('IPO_HORIZON_CLASSIFIER_INPUT_TOO_LARGE');
});
process.stdin.on('end', () => {
  const value = JSON.parse(input);
  if (!value || !Array.isArray(value.companies) || !/^\d{4}-\d{2}-\d{2}$/.test(value.asOf || '')) throw new Error('IPO_HORIZON_CLASSIFIER_INPUT_INVALID');
  const companies = value.companies.map(company => withIpoHorizon(company, { asOf: value.asOf }));
  if (!companies.every(validIpoHorizonFields)) throw new Error('IPO_HORIZON_CLASSIFIER_OUTPUT_INVALID');
  const framework = {
    version: '1', companyCount: companies.length, distribution: horizonDistribution(companies),
    evidenceGapCount: companies.filter(company => (company.coverageGaps || []).includes(IPO_HORIZON_GAP)).length
  };
  process.stdout.write(JSON.stringify({ companies, framework }));
});
