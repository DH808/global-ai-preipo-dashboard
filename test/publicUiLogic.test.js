'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '..');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'public/lifecycle.js'), 'utf8'), context);
assert.deepEqual(Array.from(context.lifecycleTaxonomy.EARLY_STAGES), ['formation_pre_seed','seed','series_a_b']);
assert.equal(context.lifecycleTaxonomy.stageFilterValue('formation_series_b'), 'formation_pre_seed,seed,series_a_b');
assert.equal(context.lifecycleTaxonomy.stageFilterValue('pre_ipo'), 'pre_ipo');

const app = fs.readFileSync(path.join(root, 'public/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'public/index.html'), 'utf8');
assert.match(app, /\$\('#stage'\)\.addEventListener\('change', \(\) => load\(\)\)/, 'stage selector must trigger a reload');
assert.ok(!app.includes("get('admin')"), 'admin query mode must not exist');
assert.ok(!html.includes('id="editDialog"') && !html.includes('id="newBtn"'), 'public UI must not contain edit controls');
for (const text of ['parseEvidenceNote', 'Diligence ask', 'Ask for', 'keyDiligence', 'nextActionZh', 'e.note']) {
  assert.ok(!app.includes(text), `public UI must not parse or render operational evidence text: ${text}`);
}
assert.match(app, /\^\(https\?\):\$/, 'UI URL policy must accept only HTTP(S)');
for (const scheme of ['javascript:', 'data:', 'file:']) assert.ok(!html.toLowerCase().includes(`href="${scheme}`));
console.log('✓ lifecycle selector, Formation–Series B preset, public controls, and link policy passed');
