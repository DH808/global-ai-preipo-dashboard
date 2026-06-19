#!/usr/bin/env python3
"""v15 hardening: convert Taiwan ESB/pre-listing screen metrics from prior local
research into explicit revenue/valuation fields and source registry records.

No gated data. Uses /Users/mac/Downloads/taiwan_esb_screen_20260618.json produced
from public Taiwan ESB screen research. Keeps the funding tab as a capital-market
record, not fabricated VC funding.
"""
import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone

APP = Path(__file__).resolve().parents[1]
STATE = APP / 'data/state.json'
DB = APP / 'data/pipeline.sqlite'
ESB = Path('/Users/mac/Downloads/taiwan_esb_screen_20260618.json')

state = json.loads(STATE.read_text())
esb_rows = json.loads(ESB.read_text())
by_code = {str(r.get('code')): r for r in esb_rows}

MAP = {
    'bellwether-electronics': '7861',
    'hermes-testing': '7856',
    'asrock-industrial': '7710',
    'climax-technology': '7689',
    'xalloy': '7918',
    'jtpc': '6826',
    'yesiang': '7909',
}

SOURCE_ID = 'taiwan_esb_public_screen_20260618'
SOURCE = {
    'id': SOURCE_ID,
    'name': 'Taiwan Emerging Stock / listing application public screen 2026-06-18',
    'type': 'manual public dataset / exchange-screen-derived',
    'sourceType': 'manual public dataset / exchange-screen-derived',
    'status': 'enabled',
    'connectorStatus': 'manual_dataset_loaded',
    'url': '/Users/mac/Downloads/taiwan_esb_screen_20260618.json',
    'refreshFrequency': 'manual / before IC review',
    'coverage': 'Taiwan ESB/pre-listing names: code, price, capital, implied market cap, YTD revenue, YoY, EPS, application status/date, website.',
    'limitations': 'Local public-screen snapshot; must refresh from TWSE/TPEx/ESB official pages before trade or IC memo. Market cap is screen-implied, not a financing round.'
}

def ntd_bn_from_100m(x):
    if x is None: return '未披露'
    return f"NT${float(x)/10:.1f}B"

def pct(x):
    if x is None: return 'n/a'
    return f"{float(x):+.1f}%"

def clean_applying(code):
    # Existing dataset uses upper/lower A/B inconsistently; keep raw code but map readable status.
    if not code: return 'no current TWSE/TPEx application flag in screen'
    return f"application flag {code}"

def ensure_source_registry():
    regs = state.setdefault('sourceRegistry', [])
    if not any(s.get('id') == SOURCE_ID for s in regs):
        regs.append(SOURCE)
    else:
        for s in regs:
            if s.get('id') == SOURCE_ID:
                s.update(SOURCE)

def update_company(c, r):
    code = str(r['code'])
    revenue = ntd_bn_from_100m(r.get('ytd_rev_100m'))
    mcap = ntd_bn_from_100m(r.get('mcap_100m'))
    ytd_yoy = pct(r.get('ytd_yoy'))
    month_yoy = pct(r.get('month_yoy'))
    eps = r.get('eps')
    price = r.get('price')
    cap = r.get('capital_ntd')
    appdate = str(r.get('appdate') or '').strip()
    applying = clean_applying(r.get('applying'))
    rev_text = f"2026 YTD revenue {revenue}; YTD YoY {ytd_yoy}; latest month YoY {month_yoy}; EPS {eps}; ESB price NT${price}."
    val_text = f"ESB implied market cap {mcap} on 2026-06-18 public screen; price NT${price}; capital NT${cap/1e8:.2f}亿." if cap else f"ESB implied market cap {mcap} on 2026-06-18 public screen."
    c['revenueScale'] = rev_text
    c['revenueScaleZh'] = rev_text
    c['latestValuation'] = val_text
    c['latestAvailableValuation'] = val_text
    c['latestValuationZh'] = val_text
    c['valuationView'] = val_text
    metrics = list(c.get('keyMetrics') or [])
    # Remove stale Taiwan screen metrics and rewrite in a consistent format.
    metrics = [m for m in metrics if not re.search(r'2026 Jan-May revenue|Estimated ESB market cap|EPS rank data|EPS:', str(m))]
    metrics.extend([
        f"Taiwan code {code}; {r.get('industry')} / {r.get('full')}",
        f"ESB/listing date screen: {r.get('listing_date')}; listing/application status: {applying}; appdate {appdate or 'n/a'}",
        f"Market screen: price NT${price}; implied mcap {mcap}; capital NT${cap/1e8:.2f}亿" if cap else f"Market screen: price NT${price}; implied mcap {mcap}",
        f"Revenue screen: YTD {revenue}; YTD YoY {ytd_yoy}; month YoY {month_yoy}; EPS {eps}",
        f"Website: {r.get('web')}"
    ])
    c['keyMetrics'] = metrics
    boundary_note = 'v15: Taiwan ESB financial metrics from local public-screen snapshot; refresh official TWSE/TPEx pages before IC/trade.'
    if boundary_note not in (c.get('evidenceBoundary') or ''):
        c['evidenceBoundary'] = (c.get('evidenceBoundary') or '') + ' | ' + boundary_note
    # Remove stale v14 note text that had inconsistent NT$B conversions and
    # rebuild investor-facing notes from the current normalized fields.
    current_note = (
        f"Recommendation: {c.get('recommendation') or '继续跟踪台湾准上市AI供应链标的，价格/收入质量/客户结构决定是否Act Now。'}\n"
        f"Mandate fit: {c.get('mandateFit') or 'Taiwan pre-listing AI hardware/supply-chain fit.'}\n"
        f"Why now: {c.get('whyNow') or 'ESB/listing application screen provides liquidity-event visibility.'}\n"
        f"Key metrics: {'; '.join(metrics)}\n"
        f"Valuation view: {val_text}\n"
        f"Revenue view: {rev_text}\n"
        f"Access route: {c.get('routeToAccess') or c.get('relationshipRoute') or 'underwriter/company/industry channel checks'}\n"
        f"Evidence boundary: {c.get('evidenceBoundary')}"
    )
    c['notesClean'] = current_note
    c['notes'] = current_note
    # Patch embedded evidence snippets if they carried the old conversion.
    for ev in c.get('evidence', []) or []:
        note = str(ev.get('note') or '')
        if 'Jan-May revenue' in note or 'TPEx open data' in note or 'Estimated ESB market cap' in note:
            ev['note'] = f"Taiwan public ESB/pre-listing screen: YTD revenue {revenue}, YoY {ytd_yoy}, month YoY {month_yoy}, EPS {eps}, screen-implied market cap {mcap}; refresh official exchange/company filings before IC/trade."
            ev['type'] = ev.get('type') or 'public_screen'
            ev['date'] = ev.get('date') or '2026-06-18'
    dc = c.setdefault('dataCompleteness', {})
    dc.update({'hasRevenueScale': True, 'hasValuation': True, 'taiwanEsbMetricsLoaded': True, 'taiwanEsbSourceId': SOURCE_ID})
    return {'code': code, 'company': c['name'], 'revenue': revenue, 'mcap': mcap, 'ytd_yoy': ytd_yoy, 'eps': eps}

def update_funding_rounds(company_id, r):
    updated = 0
    for fr in state.get('fundingRounds', []):
        if fr.get('companyId') != company_id:
            continue
        # For A2 Taiwan names, the funding panel intentionally stores a
        # capital-market / pre-listing record rather than a private VC round.
        # Rewrite all matching rows so old TBD placeholders do not survive.
        fr['sourceName'] = SOURCE['name']
        fr['sourceType'] = 'official_screen_public_dataset'
        fr['confidence'] = 'official_screen'
        fr['url'] = SOURCE['url']
        fr['amount'] = f"Not a VC round; ESB/listing application capital-market screen. Capital NT${float(r.get('capital_ntd') or 0)/1e8:.2f}亿."
        fr['valuation'] = f"Screen-implied market cap {ntd_bn_from_100m(r.get('mcap_100m'))}; price NT${r.get('price')}."
        fr['notes'] = f"v15 hardened: public Taiwan screen metrics loaded (YTD revenue {ntd_bn_from_100m(r.get('ytd_rev_100m'))}, YoY {pct(r.get('ytd_yoy'))}, EPS {r.get('eps')}); this is a pre-listing/ESB market record, not a private financing round."
        updated += 1
    return updated

ensure_source_registry()
summary=[]; round_updates=0
companies_by_id = {c['id']: c for c in state['companies']}
for cid, code in MAP.items():
    r = by_code.get(code)
    c = companies_by_id.get(cid)
    if not r or not c: continue
    summary.append(update_company(c, r))
    round_updates += update_funding_rounds(cid, r)

now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
state['meta']['updatedAt'] = now
state['meta']['uiVersion'] = '15'
state['meta']['snapshotVersion'] = 'v15-taiwan-esb-metrics-hardening'
state['meta']['taiwanEsbMetricHardening'] = {
    'asOf': now,
    'sourceFile': str(ESB),
    'sourceId': SOURCE_ID,
    'companiesUpdated': len(summary),
    'fundingRoundRecordsUpgraded': round_updates,
    'method': 'Loaded Taiwan ESB/pre-listing public-screen metrics into revenueScale/latestValuation/keyMetrics; upgraded A2 Taiwan capital-market placeholder records to official_screen confidence without fabricating VC funding.'
}
fe = state['meta'].setdefault('fundingEnrichment', {})
fe.update({
    'asOf': now,
    'fundingRounds': len(state.get('fundingRounds', [])),
    'companiesWithFundingPanelRecord': len({r.get('companyId') for r in state.get('fundingRounds', [])}),
    'coverageGapPlaceholders': sum(1 for r in state.get('fundingRounds', []) if r.get('sourceType') == 'coverage_gap'),
    'highConfidenceRounds': sum(1 for r in state.get('fundingRounds', []) if str(r.get('confidence','')).lower() in ('high','official','official_screen')),
    'mediumOrBetterRounds': sum(1 for r in state.get('fundingRounds', []) if str(r.get('confidence','')).lower() in ('high','official','official_screen','medium')),
})
STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

# Sync SQLite company_metrics / funding_rounds / source_registry minimal fields
con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute('insert or replace into source_registry(id,source_name,source_type,connector_status,refresh_frequency,credential_env_var,limitations,last_checked_at) values(?,?,?,?,?,?,?,?)',
            (SOURCE_ID, SOURCE['name'], SOURCE['sourceType'], SOURCE['connectorStatus'], SOURCE['refreshFrequency'], '', SOURCE['limitations'], now))
for item in summary:
    cid = next(k for k,v in MAP.items() if v == item['code'])
    cur.execute("delete from company_metrics where company_id=? and source_id=?", (cid, SOURCE_ID))
    metrics = [
        ('Revenue/ARR', item['revenue'], 'NTD', 'revenue', '2026 YTD', now, 'official_screen', f"YTD YoY {item['ytd_yoy']}; EPS {item['eps']}"),
        ('Latest valuation', item['mcap'], 'NTD', 'valuation', '2026-06-18 screen', now, 'official_screen', 'Screen-implied ESB/pre-listing market cap; not a financing round.'),
        ('EPS', str(item['eps']), 'NTD/share', 'profitability', 'latest screen', now, 'official_screen', ''),
    ]
    for name,val,unit,typ,period,asof,conf,notes in metrics:
        cur.execute('insert into company_metrics(company_id,metric_name,metric_value,metric_unit,metric_type,period,as_of,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?)',
                    (cid,name,val,unit,typ,period,asof,SOURCE_ID,conf,notes))
cur.execute('delete from funding_rounds')
for fr in state.get('fundingRounds', []):
    cur.execute('insert or replace into funding_rounds(id,company_id,date,round_name,amount,valuation_post,lead_investors,participants,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?,?)',
                (fr.get('id'), fr.get('companyId'), fr.get('date',''), fr.get('round',''), fr.get('amount',''), fr.get('valuation',''), json.dumps(fr.get('leadInvestors',[]),ensure_ascii=False), json.dumps(fr.get('participants',[]),ensure_ascii=False), fr.get('sourceName') or fr.get('sourceType',''), fr.get('confidence',''), fr.get('notes','')))
con.commit(); con.close()
print(json.dumps(state['meta']['taiwanEsbMetricHardening'], ensure_ascii=False, indent=2))
print('updated companies')
for x in summary: print(x)
