const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const REGISTRY_FILE = path.join(__dirname, '..', 'data', 'source_registry.json');

function loadRegistry() {
  return JSON.parse(fs.readFileSync(REGISTRY_FILE, 'utf8')).sources;
}

function fetchText(url, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 HermesResearchBot/1.0' }, timeout: timeoutMs }, res => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ statusCode: res.statusCode, text: data }));
    });
    req.on('timeout', () => { req.destroy(); reject(new Error('TIMEOUT')); });
    req.on('error', reject);
  });
}

function parseInterVestPortfolio(html) {
  const items = [];
  const re = /<div class="col-4[^>]*data-tab="([^"]+)"\s+data-type="([^"]+)"[\s\S]*?<a href="([^"]*)"[\s\S]*?<img[^>]*alt="([^"]+) logo"/g;
  let m;
  while ((m = re.exec(html))) {
    items.push({ source: 'intervest_portfolio', tab: m[1], category: m[2], url: m[3], name: cleanName(m[4]) });
  }
  return items;
}
function cleanName(name) { return String(name).replace(/ Ai$/i, ' AI').trim(); }

async function refreshInterVest() {
  const source = loadRegistry().find(s => s.id === 'intervest_portfolio');
  const res = await fetchText(source.url);
  if (res.statusCode < 200 || res.statusCode >= 300) throw new Error(`HTTP_${res.statusCode}`);
  const items = parseInterVestPortfolio(res.text);
  return { sourceId: 'intervest_portfolio', status: 'ok', fetchedAt: new Date().toISOString(), count: items.length, items };
}

function parseNewsRss(xml) {
  const out = [];
  const itemRe = /<item>[\s\S]*?<title><!\[CDATA\[([\s\S]*?)\]\]><\/title>[\s\S]*?<link>([\s\S]*?)<\/link>[\s\S]*?<pubDate>([\s\S]*?)<\/pubDate>[\s\S]*?<\/item>/g;
  let m;
  while ((m = itemRe.exec(xml))) out.push({ title: decode(m[1]), url: decode(m[2]), publishedAt: decode(m[3]) });
  if (!out.length) {
    const itemRe2 = /<item>[\s\S]*?<title>([\s\S]*?)<\/title>[\s\S]*?<link>([\s\S]*?)<\/link>[\s\S]*?<pubDate>([\s\S]*?)<\/pubDate>[\s\S]*?<\/item>/g;
    while ((m = itemRe2.exec(xml))) out.push({ title: decode(m[1]), url: decode(m[2]), publishedAt: decode(m[3]) });
  }
  return out.slice(0, 10);
}
function decode(s) { return String(s || '').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&#39;/g,"'").replace(/&quot;/g,'"').trim(); }

async function fetchCompanyNews(companyName) {
  const q = encodeURIComponent(`${companyName} funding IPO valuation investors AI`);
  const url = `https://news.google.com/rss/search?q=${q}&hl=en-US&gl=US&ceid=US:en`;
  const res = await fetchText(url);
  return { sourceId: 'google_news_rss', status: res.statusCode === 200 ? 'ok' : `http_${res.statusCode}`, fetchedAt: new Date().toISOString(), items: parseNewsRss(res.text) };
}

function sourceStatus() {
  const sources = loadRegistry().map(s => {
    if (s.id === 'crunchbase') return { ...s, runtimeStatus: process.env.CRUNCHBASE_API_KEY ? 'credential_present_not_tested' : 'missing_credential' };
    if (s.id === 'dealroom') return { ...s, runtimeStatus: process.env.DEALROOM_API_KEY ? 'credential_present_not_tested' : 'missing_credential' };
    return { ...s, runtimeStatus: s.status };
  });
  return sources;
}

module.exports = { loadRegistry, refreshInterVest, fetchCompanyNews, sourceStatus, parseInterVestPortfolio, parseNewsRss };
