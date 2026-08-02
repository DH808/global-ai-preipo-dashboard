'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'public/lifecycle.js'), 'utf8'), context);
vm.runInContext(fs.readFileSync(path.join(root, 'public/tmtTaxonomy.js'), 'utf8'), context);
assert.deepEqual(Array.from(context.lifecycleTaxonomy.EARLY_STAGES), ['formation_pre_seed','seed','series_a_b']);
assert.equal(context.lifecycleTaxonomy.stageFilterValue('formation_series_b'), 'formation_pre_seed,seed,series_a_b');
assert.equal(context.lifecycleTaxonomy.stageFilterValue('pre_ipo'), 'pre_ipo');
assert.deepEqual(Array.from(context.tmtTaxonomy.TMT_VERTICALS), require('../src/tmtTaxonomy').TMT_VERTICALS);

const app = fs.readFileSync(path.join(root, 'public/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'public/index.html'), 'utf8');
assert.match(app, /\$\('#stage'\)\.addEventListener\('change', \(\) => load\(\)\)/, 'stage selector must trigger a reload');
assert.match(app, /function renderCoverageMatrix\(\)/, 'coverage matrix must be rendered deterministically');
for (const field of ['classification','businessModel','customerType','monetization','financing','investors','revenue','evidence','sourceVintage']) assert.ok(app.includes(field), `${field} completeness missing`);
assert.ok(html.includes('id="tmtVertical"') && html.includes('id="coverageMatrix"'), 'TMT vertical filter and coverage matrix are required');
assert.ok(html.includes('id="regionalExposure"') && html.includes('Asia Priority'), 'Asia exposure filter and preset are required');
for (const marker of ['asiaPriorityOnly', 'regionalExposure', 'asia-coverage-matrix', "['china','taiwan','japan','south_korea','singapore']"]) assert.ok(app.includes(marker), `${marker} Asia desktop/mobile logic missing`);
assert.match(app, /asiaPriorityOnly=false/, 'reset must clear Asia Priority on desktop and mobile');
const css = fs.readFileSync(path.join(root, 'public/style.css'), 'utf8');
assert.match(css, /\.coverage-matrix-wrap\{overflow:auto/, 'wide coverage matrix must scroll responsively');
assert.match(css, /@media\(max-width:720px\)/, 'mobile breakpoint must remain present');
assert.ok(!app.includes("get('admin')"), 'admin query mode must not exist');
assert.ok(!html.includes('id="editDialog"') && !html.includes('id="newBtn"'), 'public UI must not contain edit controls');
for (const text of ['parseEvidenceNote', 'Diligence ask', 'Ask for', 'keyDiligence', 'nextActionZh', 'e.note']) {
  assert.ok(!app.includes(text), `public UI must not parse or render operational evidence text: ${text}`);
}
assert.match(app, /\^\(https\?\):\$/, 'UI URL policy must accept only HTTP(S)');
for (const scheme of ['javascript:', 'data:', 'file:']) assert.ok(!html.toLowerCase().includes(`href="${scheme}`));
console.log('✓ lifecycle/TMT filters, coverage matrix, responsive controls, and link policy passed');
