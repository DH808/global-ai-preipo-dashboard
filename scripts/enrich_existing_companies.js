const fs = require('fs');
const path = require('path');

const statePath = path.join(__dirname, '..', 'data', 'state.json');
const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
const asOf = new Date().toISOString().slice(0, 10);

const curatedInvestors = {
  'Databricks': ['a16z', 'NEA', 'Microsoft', 'CapitalG', 'ICONIQ Capital', 'Thrive Capital', 'Temasek', 'NVIDIA'],
  'Mistral AI': ['General Catalyst', 'Lightspeed Venture Partners', 'a16z', 'Bpifrance', 'NVIDIA', 'Salesforce Ventures', 'Cisco', 'IBM', 'ASML'],
  'DeepL': ['Benchmark', 'Index Ventures', 'IVP', 'Atomico'],
  'StepFun / 阶跃星辰': ['Tencent', 'Qiming Venture Partners', 'HongShan', 'Gaorong Capital'],
  'Moonshot AI / 月之暗面': ['Alibaba', 'Tencent', 'HongShan', 'Monolith Management', 'Meituan'],
  'Together AI': ['Salesforce Ventures', 'NVIDIA', 'Kleiner Perkins', 'NEA', 'Lux Capital', 'Coatue'],
  'Glean': ['Sequoia Capital', 'Kleiner Perkins', 'Lightspeed Venture Partners', 'General Catalyst', 'IVP', 'Sapphire Ventures', 'Capital One Ventures', 'Databricks Ventures'],
  'ElevenLabs': ['a16z', 'Sequoia Capital', 'Salesforce Ventures', 'NVIDIA', 'Nat Friedman', 'Daniel Gross'],
  'Harvey': ['OpenAI Startup Fund', 'Sequoia Capital', 'Kleiner Perkins', 'Coatue', 'Elad Gil'],
  'Synthesia': ['Accel', 'GV', 'Kleiner Perkins', 'FirstMark', 'NVIDIA'],
  'Cerebras': ['Foundation Capital', 'Benchmark', 'Eclipse Ventures', 'Alpha Wave', 'G42', 'Tiger Global', 'Altimeter Capital'],
  'Groq': ['BlackRock', 'Disruptive', 'Cisco Investments', 'Samsung Catalyst Fund', 'D1 Capital'],
  'xAI': ['Valor Equity Partners', 'Andreessen Horowitz', 'Sequoia Capital', 'Fidelity', 'Kingdom Holding', 'QIA'],
  'Perplexity AI': ['IVP', 'NEA', 'NVIDIA', 'Databricks Ventures', 'Bessemer Venture Partners', 'SoftBank Vision Fund', 'Jeff Bezos'],
  'Anysphere / Cursor': ['Thrive Capital', 'Accel', 'a16z', 'DST Global'],
  'Rippling': ['Greenoaks', 'Coatue', 'Founders Fund', 'Sequoia Capital', 'Thrive Capital'],
  'Runway': ['General Atlantic', 'NVIDIA', 'Google', 'Salesforce Ventures', 'Coatue'],
  'Lightmatter': ['GV', 'Viking Global Investors', 'SIP Global Partners', 'T. Rowe Price', 'Fidelity', 'Spark Capital'],
  'Celestial AI': ['AMD Ventures', 'Temasek/Xora', 'Samsung Catalyst Fund', 'Koch Disruptive Technologies', 'Porsche Automobil Holding'],
  'd-Matrix': ['M12', 'Temasek', 'Playground Global', 'SK hynix', 'Ericsson Ventures', 'Marvell Technology'],
  'Tenstorrent': ['Samsung Catalyst Fund', 'Hyundai Motor Group', 'Fidelity', 'Eclipse Ventures', 'Bezos Expeditions'],
  'Weights & Biases': ['Insight Partners', 'Coatue', 'Felicis', 'BOND', 'Trinity Ventures'],
  'Pinecone': ['Andreessen Horowitz', 'ICONIQ Growth', 'Menlo Ventures', 'Tiger Global', 'Wing Venture Capital'],
  'Scale AI': ['Accel', 'Tiger Global', 'Founders Fund', 'Greenoaks', 'Dragoneer', 'Coatue', 'Amazon', 'Meta'],
  'PhysicsX': ['Temasek', 'General Catalyst', 'Standard Investments', 'NVIDIA'],
  'Black Forest Labs': ['Andreessen Horowitz', 'General Catalyst', 'Lightspeed Venture Partners', 'Temasek', 'NVIDIA'],
  'CuspAI': ['Temasek', 'NEA', 'Radical Ventures', 'Hoxton Ventures'],
  'PsiQuantum': ['BlackRock', 'Temasek', 'Baillie Gifford', 'Microsoft', 'M12', 'QIA'],
  'AlphaSense': ['Viking Global Investors', 'BDT & MSD Partners', 'CapitalG', 'Goldman Sachs', 'Morgan Stanley Tactical Value'],
  'Sierra': ['Greenoaks', 'Sequoia Capital', 'Benchmark', 'ICONIQ Capital'],
  'Baseten': ['IVP', 'Spark Capital', 'Greylock', 'Conviction', 'CapitalG'],
  'Clay': ['CapitalG', 'Sequoia Capital', 'Meritech Capital', 'First Round Capital'],
  'Physical Intelligence': ['Lux Capital', 'Thrive Capital', 'Khosla Ventures', 'OpenAI', 'Sequoia Capital'],
  'Neysa': ['Z47', 'Nexus Venture Partners', 'NTTVC'],
  'Anyscale': ['Andreessen Horowitz', 'NEA', 'Intel Capital', 'Addition', 'Foundation Capital'],
  'DDN': ['Blackstone', 'TPG', 'Management / private ownership'],
  'Hammerspace': ['Prosperity7 Ventures', 'ARK Invest', 'Pier 88 Investment Partners', 'Samsung Ventures'],
  'MinIO': ['Intel Capital', 'SoftBank Vision Fund 2', 'Nexus Venture Partners', 'General Catalyst', 'Dell Technologies Capital'],
  'Arrcus': ['Clear Ventures', 'General Catalyst', 'Lightspeed Venture Partners', 'Liberty Global Ventures', 'Prosperity7 Ventures', 'NVIDIA'],
  'EnCharge AI': ['Tiger Global', 'RTX Ventures', 'ACVC Partners', 'Anzu Partners', 'Alumni Ventures'],
  'Etched': ['Primary Venture Partners', 'Positive Sum', 'Two Sigma Ventures', 'Peter Thiel', 'Jane Street'],
  'Fireworks AI': ['Benchmark', 'Sequoia Capital', 'NVIDIA', 'AMD Ventures'],
  'LiquidStack': ['Tiger Global', 'Trane Technologies', 'Standard Investments'],
  'MatX': ['Spark Capital', 'Nat Friedman', 'Daniel Gross'],
  'Modal': ['Amplify Partners', 'Redpoint Ventures', 'Lux Capital'],
  'Submer': ['M&G Catalyst', 'Planet First Partners', 'Norrsken VC'],
  'Avicena': ['Cerium Technology', 'Samsung Catalyst Fund', 'Micron Ventures', 'IAG Capital Partners'],
  'DustPhotonics': ['Intel Capital', 'WRVI Capital', 'Celesta Capital', 'Greenfield Partners'],
  'OpenLight': ['Synopsys', 'Juniper Networks'],
  'Ranovus': ['BDC Capital', 'Export Development Canada', 'Sustainable Development Technology Canada'],
  'Selector AI': ['Two Bear Capital', 'Atlantic Bridge', 'SineWave Ventures'],
  'Xscape Photonics': ['IAG Capital Partners', 'Cisco Investments', 'Fathom Fund'],
  '台智雲 / Taiwan AI Cloud': ['ASUS group ecosystem / ownership to confirm']
};

const badInvestor = /style investors|investors - verify|TBD|verify ownership|Korean local investors|Chinese growth investors|other major investors to verify|other strategic\/financial investors to verify|top global growth investors|top growth investors|strategic cloud ecosystem|nvidia-backed ecosystem|nvidia-backed investors|nvidia\/alphabet vc arms|european strategic capital|korea funds|ventures$/i;
const genericKeep = /lead underwriter|management|private ownership/i;
function uniq(arr) {
  const out = [];
  const seen = new Set();
  for (const raw of arr || []) {
    const x = String(raw || '').replace(/\s+/g, ' ').trim();
    if (!x || /^TBD$/i.test(x)) continue;
    const key = x.toLowerCase();
    if (!seen.has(key)) { seen.add(key); out.push(x); }
  }
  return out;
}
function companyDescription(c) {
  if (c.companyDescription) return c.companyDescription;
  if (c.description || c.whatItDoes || c.businessDescription) return c.description || c.whatItDoes || c.businessDescription;
  const layer = [c.sector, c.subSector].filter(Boolean).join(' — ');
  return layer || c.notes || 'Description not captured yet.';
}
function latestAvailableValuation(c) {
  return c.latestAvailableValuation || c.latestValuation || c.valuationView || c.latestFunding || '未披露/待验证';
}
const roundsByCompany = new Map();
for (const r of state.fundingRounds || []) {
  if (!roundsByCompany.has(r.companyId)) roundsByCompany.set(r.companyId, []);
  roundsByCompany.get(r.companyId).push(r);
}
let enrichedInvestors = 0;
let descAdded = 0;
let valuationAdded = 0;
for (const c of state.companies || []) {
  const before = JSON.stringify(c.investors || []);
  const roundInvestors = (roundsByCompany.get(c.id) || []).flatMap(r => r.participants || r.investors || r.leadInvestors || []);
  const curated = curatedInvestors[c.name] || [];
  const original = c.investors || [];
  const cleanedOriginal = original.filter(x => !badInvestor.test(String(x)) || genericKeep.test(String(x)));
  const merged = uniq([...cleanedOriginal, ...roundInvestors, ...curated])
    .filter(x => !badInvestor.test(String(x)) || genericKeep.test(String(x)))
    .map(x => x === 'public ESB investors' ? 'Public ESB shareholders / shareholder registry pending' : x)
    .map(x => x === 'ASUS ecosystem / verify ownership' ? 'ASUS group ecosystem / ownership to confirm' : x);
  c.investors = merged.length ? merged : original;
  if (JSON.stringify(c.investors) !== before) enrichedInvestors += 1;
  if (!c.companyDescription) { c.companyDescription = companyDescription(c); descAdded += 1; }
  if (!c.latestAvailableValuation) { c.latestAvailableValuation = latestAvailableValuation(c); valuationAdded += 1; }
  c.investorSummary = c.investors.slice(0, 5).join(', ') + (c.investors.length > 5 ? ` +${c.investors.length - 5}` : '');
  c.investorDataQuality = c.investors.some(x => badInvestor.test(String(x))) ? 'mixed / needs verification' : 'structured from existing tracker + public/manual enrichment';
  c.dataCompleteness = {
    hasDescription: Boolean(c.companyDescription),
    hasValuation: Boolean(c.latestAvailableValuation && !/未披露|待验证|not disclosed|unknown/i.test(c.latestAvailableValuation)),
    investorCount: c.investors.length,
    evidenceCount: (c.evidence || []).length,
    hasRoute: Boolean(c.relationshipRoute || c.routeToAccess)
  };
  c.enrichedAsOf = asOf;
}
state.meta = state.meta || {};
state.meta.updatedAt = new Date().toISOString();
state.meta.dataEnrichment = {
  asOf,
  method: 'merged existing tracker fields, funding-round participants, and curated public/manual investor aliases; no secrets or gated APIs used',
  companies: state.companies.length,
  enrichedInvestors,
  descriptionsAdded: descAdded,
  latestAvailableValuationsAdded: valuationAdded
};
fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
console.log(JSON.stringify(state.meta.dataEnrichment, null, 2));
