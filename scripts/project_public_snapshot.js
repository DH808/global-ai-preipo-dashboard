#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { buildPublicSnapshot, canonicalJson } = require('../src/publicProjection');
const { lifecycleCoverage } = require('../src/lifecycle');

function main() {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) throw new Error('USAGE: project_public_snapshot.js INPUT OUTPUT');
  const state = JSON.parse(fs.readFileSync(path.resolve(input), 'utf8'));
  const snapshot = buildPublicSnapshot(state, lifecycleCoverage);
  if (!snapshot.companies.length) throw new Error('PUBLIC_SNAPSHOT_EMPTY');
  fs.writeFileSync(path.resolve(output), canonicalJson(snapshot) + '\n', { encoding: 'utf8', mode: 0o600 });
}

main();
