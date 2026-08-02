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
assert.match(app, /\['stage','ipoHorizon'\]/, 'stage and horizon selectors must trigger reloads');
assert.match(app, /function renderCoverageMatrix\(\)/, 'coverage matrix must be rendered deterministically');
for (const field of ['classification','businessModel','customerType','monetization','financing','investors','revenue','evidence','sourceVintage']) assert.ok(app.includes(field), `${field} completeness missing`);
assert.ok(html.includes('id="tmtVertical"') && html.includes('id="coverageMatrix"'), 'TMT vertical filter and coverage matrix are required');
assert.ok(html.includes('id="regionalExposure"') && html.includes('Asia Priority'), 'Asia exposure filter and preset are required');
assert.ok(html.includes('id="ipoHorizon"') && html.includes('monitoring expectations, not forecasts'), 'horizon filter and bilingual disclaimer are required');
for (const legacy of ['24–36m strategic/pre-IPO path', '12–24m IPO / approved secondary', '18–36m secondary/IPO/next-round path', 'IPO 窗口', '流动性窗口']) {
  assert.ok(!app.includes(legacy) && !html.includes(legacy), `public UI retained legacy IPO-window claim: ${legacy}`);
}
for (const marker of ['IPO_HORIZON_LABELS','horizonDistribution','近期监测 · 0–24m','24–48m 机会','长期机会 · 48m+','Asia · 24–48m+']) assert.ok(app.includes(marker), `${marker} horizon desktop/mobile logic missing`);
for (const marker of ['asiaPriorityOnly', 'regionalExposure', 'asia-coverage-matrix', "['china','taiwan','japan','south_korea','singapore']"]) assert.ok(app.includes(marker), `${marker} Asia desktop/mobile logic missing`);
assert.match(app, /asiaPriorityOnly=false/, 'reset must clear Asia Priority on desktop and mobile');
assert.match(app, /\$\('#ipoHorizon'\)\.value=''/, 'reset must clear horizon on desktop and mobile');
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
