#!/usr/bin/env python3
"""v16 hardening: high-priority commercial metrics / public-proof status.

Goal: convert A0/A1/B1/B2 names from ambiguous "未披露/待验证" into explicit
public-commercial-status records:
- official/reported metric when public and sourceable
- otherwise explicit "not publicly disclosed" + diligence ask + source boundary

No gated DB or private data fabrication.
"""
import json, sqlite3, re
from pathlib import Path
from datetime import datetime, timezone

APP = Path(__file__).resolve().parents[1]
STATE = APP / 'data/state.json'
DB = APP / 'data/pipeline.sqlite'
SOURCES_DIR = Path('/Users/mac/Downloads/preipo_v16_sources')

state = json.loads(STATE.read_text())
companies = {c['id']: c for c in state['companies']}
now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

SOURCE_ID = 'v16_public_commercial_metric_review_20260619'
SOURCE = {
    'id': SOURCE_ID,
    'name': 'v16 public commercial metric review for A0/A1/B1/B2 pre-IPO names',
    'type': 'manual public-source review',
    'sourceType': 'manual public-source review',
    'status': 'enabled',
    'connectorStatus': 'manual_public_review',
    'url': str(SOURCES_DIR),
    'refreshFrequency': 'manual / before IC review',
    'coverage': 'High-priority AI pre-IPO names: public revenue/ARR/backlog/unit-economics status and diligence asks.',
    'limitations': 'Not a paid private-market database. Many private companies do not disclose revenue/ARR/backlog; those are explicitly marked not publicly disclosed rather than estimated.'
}

# Source URLs captured or identified in this pass. Some company URLs returned 404/CAPTCHA; use only as source-boundary evidence.
SURL = {
    'databricks': 'https://www.databricks.com/company/newsroom/press-releases',
    'lightmatter': 'https://lightmatter.co/press-releases/lightmatter-raises-400m-series-d',
    'weka': 'https://www.weka.io/press-releases/weka-raises-140-million-in-series-e-funding-at-1-6-billion-valuation/',
    'minio': 'https://blog.min.io/minio-raises-103-million-series-b/',
    'openrouter': 'https://openrouter.ai/',
    'lambda': 'https://lambdalabs.com/customer-stories',
    'crusoe': 'https://www.crusoe.ai/resources/customers',
    'groq': 'https://groq.com/groqcloud',
    'hammerspace': 'https://hammerspace.com/customers/',
    'ddn': 'https://www.ddn.com/resources/customers/',
    'ayar-labs': 'https://ayarlabs.com/',
    'celestial-ai': 'https://www.celestial.ai/',
    'd-matrix': 'https://www.d-matrix.ai/',
}

DATA = {
    # A0 / A1 / B1 with more explicit source status
    'databricks': dict(
        revenue='Official/company-public metrics already in tracker: >$4.8B revenue run-rate; AI products >$1B run-rate; positive FCF. v16 status: public revenue proof strong; still ask for current quarter growth, NRR, FCF margin, secondary clearing price and IPO timing.',
        status='reported_metric', confidence='high', source=SURL['databricks'],
        ask='Update with latest quarter run-rate, NRR, FCF margin, AI product mix, tender/secondary terms, banker/IPO calendar.'),
    'drivenets': dict(
        revenue='Company/media-reported commercial proof in tracker: >$1B secured business; cash-flow positive since 2025. v16 status: strong backlog/secured-business proof, but needs customer concentration and revenue recognition schedule.',
        status='reported_backlog', confidence='medium', source='https://drivenets.com/',
        ask='Ask for secured-business contract tenor, realized revenue by year, customer concentration, gross margin, cash-flow definition, and AI networking exposure.'),
    'vast-data': dict(
        revenue='Revenue/CARR not publicly disclosed in v16 source pass; tracker has Reuters/public valuation signal but not current ARR. v16 status: commercial proof likely strong but not underwritable without CARR/ARR/FCF disclosure.',
        status='not_publicly_disclosed', confidence='medium', source='/Users/mac/Downloads/preipo_v16_sources/vast_30b.md',
        ask='Ask VAST/underwriters/investors for CARR/ARR, FCF status, AI/HPC customer mix, Nvidia/SuperPOD attach, net retention, and $30B valuation basis.'),
    'weka': dict(
        revenue='ARR/revenue scale is not available as a public number in v16 pass; source review confirms Series E / $1.6B valuation page and AI/HPC/NVIDIA architecture positioning, not revenue disclosure.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['weka'],
        ask='Ask for ARR/CARR, AI/HPC revenue mix, DGX/SuperPOD customer count, gross margin, NRR, FCF path, and IPO readiness.'),
    'lambda': dict(
        revenue='Revenue/utilization not publicly disclosed in v16 pass; public site exposes customer stories/pricing but not contracted ARR or GPU utilization. Treat as B1 unit-economics diligence, not revenue-proven.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['lambda'],
        ask='Ask for contracted revenue, utilization by GPU class, customer concentration, debt/capex terms, power/site commitments, depreciation, gross margin and churn.'),
    'crusoe': dict(
        revenue='Contracted revenue/MW energized not publicly disclosed in v16 pass; public customer/resource pages exist but do not provide ARR. Underwrite only after customer contracts, MW, debt/capex and power economics are verified.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['crusoe'],
        ask='Ask for contracted revenue/backlog, MW energized vs planned, tenant names/tenor, project-finance debt, power cost, GPU utilization, depreciation and gross margin.'),
    'ddn': dict(
        revenue='Private revenue not publicly disclosed in v16 pass; DDN public customer/resource pages support mature enterprise/HPC/AI footprint but do not expose AI-storage revenue scale.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['ddn'],
        ask='Ask for AI-storage revenue, growth, EBITDA/FCF, top AI customers, Nvidia/SuperPOD attachment, customer concentration and IPO/secondary plan.'),
    'hammerspace': dict(
        revenue='Revenue/ARR not publicly disclosed in v16 pass; public customer/news pages show enterprise data orchestration positioning, but no ARR/FCF metric.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['hammerspace'],
        ask='Ask for ARR, AI/HPC customer mix, cloud/on-prem split, gross margin, storage attach rate, NRR, and financing/IPO path.'),
    'minio': dict(
        revenue='ARR not publicly disclosed in v16 pass; public blog/source confirms historic $103M Series B/unicorn financing and current AIStor positioning, not current revenue.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['minio'],
        ask='Ask for subscription ARR, enterprise customer count, AIStor conversion, gross margin, NRR, open-source-to-paid conversion and liquidity path.'),
    # A1 / B2 architecture-shift names where commercial proof is the key gap
    'lightmatter': dict(
        revenue='Revenue/backlog not publicly disclosed; official press release confirms $400M Series D and $4.4B valuation, but not commercial revenue. v16 status: architecture-critical, revenue proof still data-room item.',
        status='not_publicly_disclosed', confidence='high', source=SURL['lightmatter'],
        ask='Ask for Passage design wins, production timing, committed revenue/backlog, customer names under NDA, margin model, optical I/O attach rate and IPO path.'),
    'ayar-labs': dict(
        revenue='Revenue not publicly disclosed in v16 pass; public/captcha-limited source boundary confirms Series D query path but no revenue. Treat as A1 hard-bottleneck with design-win diligence gap.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['ayar-labs'],
        ask='Ask for customer design wins, co-packaged optics production timeline, committed backlog, foundry/packaging partners, margin model and strategic investor access.'),
    'celestial-ai': dict(
        revenue='Revenue not publicly disclosed in v16 pass; public source path was noisy/Marvell-routed and did not provide company revenue. Treat as A1 photonic fabric candidate requiring customer/backlog proof.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['celestial-ai'],
        ask='Ask for Photonic Fabric design wins, committed revenue, customer qualification status, production timeline, gross margin and valuation basis.'),
    'd-matrix': dict(
        revenue='Revenue/customer production not publicly disclosed in v16 pass; tracker has Series C $275M / $2B valuation, but commercial revenue remains diligence item.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['d-matrix'],
        ask='Ask for Corsair shipment status, customer pilots vs production, software stack maturity, revenue/backlog, TCO vs GPU and Temasek/strategic access route.'),
    'groq': dict(
        revenue='Revenue/utilization not publicly disclosed; public GroqCloud/pricing/customer-story surfaces exist and tracker has official $6.9B post-money financing, but no ARR metric.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['groq'],
        ask='Ask for GroqCloud paid inference revenue, utilization, enterprise contracts, gross margin per token, customer concentration and data-center capacity ramp.'),
    'cerebras': dict(
        revenue='Revenue/customer concentration must be verified from S-1/latest financing materials; public tracker has valuation/financing but not durable revenue quality.',
        status='not_publicly_disclosed', confidence='medium', source='https://www.cerebras.ai/',
        ask='Ask for latest revenue, UAE/G42/customer concentration, WSE/CS system backlog, gross margin, IPO filing status and AI cloud recurring revenue.'),
    'tenstorrent': dict(
        revenue='Revenue/backlog not publicly disclosed; financing/strategic investor signal exists, but production silicon revenue and licensing revenue are diligence items.',
        status='not_publicly_disclosed', confidence='medium', source='https://tenstorrent.com/',
        ask='Ask for customer contracts, chip shipments, IP/licensing revenue, automotive/edge design wins, gross margin, and next financing/IPO path.'),
    'together-ai': dict(
        revenue='ARR/revenue not publicly disclosed; financing/valuation signal exists but underwrite only after paid inference/training revenue and utilization data.',
        status='not_publicly_disclosed', confidence='medium', source='https://www.together.ai/',
        ask='Ask for ARR, gross margin after GPU costs, utilization, top customers, model/API revenue mix, NRR and infrastructure capex commitments.'),
    'baseten': dict(
        revenue='ARR/revenue not publicly disclosed in v16 pass; AI inference platform positioning is clear but commercial scale remains diligence item.',
        status='not_publicly_disclosed', confidence='medium', source='https://www.baseten.co/',
        ask='Ask for ARR, enterprise customer count, inference volume, GPU gross margin, retention, and model deployment workload mix.'),
    'openrouter': dict(
        revenue='Public homepage exposes model marketplace/pricing-like surfaces but no company revenue/GMV disclosure. Treat as B2 active diligence around routing volume, take-rate and margin.',
        status='not_publicly_disclosed', confidence='medium', source=SURL['openrouter'],
        ask='Ask for GMV/API spend routed, take rate, gross margin after provider costs, developer/customer concentration, model provider contracts and enterprise traction.'),
    'panmnesia': dict(
        revenue='Revenue/backlog not publicly disclosed; CXL/memory architecture relevance high, but commercialization proof remains weak.',
        status='not_publicly_disclosed', confidence='low', source='public Korean startup/news coverage',
        ask='Ask for CXL controller/IP customer engagements, Samsung/SK relationship, tape-out/production status, revenue/backlog and IPO horizon.'),
    'zutacore': dict(
        revenue='Revenue/backlog not publicly disclosed; cooling technology relevance high but unit economics/customer deployments need verification.',
        status='not_publicly_disclosed', confidence='low', source='public news / company coverage',
        ask='Ask for installed MW, paid deployments, repeat customers, gross margin, service revenue, warranty/leakage history and data-center partner pipeline.'),
    'anyscale': dict(revenue='ARR/revenue not publicly disclosed; Ray ecosystem relevance remains, but public commercialization metric is not available.', status='not_publicly_disclosed', confidence='low', source='https://www.anyscale.com/', ask='Ask for ARR, enterprise customers, Ray adoption-to-paid conversion, gross margin and retention.'),
    'arrcus': dict(revenue='Revenue/backlog not publicly disclosed; AI networking relevance requires customer/design-win proof.', status='not_publicly_disclosed', confidence='low', source='https://www.arrcus.com/', ask='Ask for AI/data-center customers, ARR/backlog, routing software gross margin and strategic routes.'),
    'encharge-ai': dict(revenue='Revenue not publicly disclosed; analog in-memory AI chip remains pre-commercial/early commercial diligence.', status='not_publicly_disclosed', confidence='low', source='https://www.enchargeai.com/', ask='Ask for tape-out, sampling, design wins, revenue/backlog and manufacturing path.'),
    'etched': dict(revenue='Revenue/backlog not publicly disclosed; Sohu ASIC thesis requires customer commitment and production timing proof.', status='not_publicly_disclosed', confidence='low', source='https://www.etched.com/', ask='Ask for customer commitments, silicon status, software stack, capacity, pricing and revenue recognition.'),
    'fireworks-ai': dict(revenue='Revenue/ARR not publicly disclosed; inference platform diligence needs customer and margin proof.', status='not_publicly_disclosed', confidence='low', source='https://fireworks.ai/', ask='Ask for ARR, inference volume, GPU cost structure, customer concentration and NRR.'),
    'liquidstack': dict(revenue='Revenue/backlog not publicly disclosed; cooling infra relevance high but paid deployment/MW pipeline needs proof.', status='not_publicly_disclosed', confidence='low', source='https://liquidstack.com/', ask='Ask for MW deployed, revenue/backlog, hyperscaler/neocloud customers, gross margin and installation/service economics.'),
    'matx': dict(revenue='Revenue not publicly disclosed; AI silicon status likely early, needs production/customer proof.', status='not_publicly_disclosed', confidence='low', source='https://www.matx.com/', ask='Ask for chip status, customer design wins, revenue/backlog, power/performance claims and manufacturing route.'),
    'modal': dict(revenue='Revenue/ARR not publicly disclosed; developer cloud traction needs paid usage and margin proof.', status='not_publicly_disclosed', confidence='low', source='https://modal.com/', ask='Ask for ARR, active paying teams, workload volume, GPU/CPU gross margin, retention and enterprise conversion.'),
    'submer': dict(revenue='Revenue/backlog not publicly disclosed; immersion cooling relevance requires deployment economics.', status='not_publicly_disclosed', confidence='low', source='https://submer.com/', ask='Ask for MW deployed, backlog, customer mix, installation/service margins and repeat orders.'),
}

# Preserve existing high-quality revenue strings for names not in DATA? DATA covers all A0/A1/B1/B2 current gaps.

def add_source_registry():
    regs = state.setdefault('sourceRegistry', [])
    if not any(s.get('id') == SOURCE_ID for s in regs): regs.append(SOURCE)
    else:
        for s in regs:
            if s.get('id') == SOURCE_ID: s.update(SOURCE)

add_source_registry()
updated=[]
for cid, d in DATA.items():
    c = companies.get(cid)
    if not c: continue
    prior = str(c.get('revenueScale') or '')
    # Always harden if missing/ambiguous, or for A1/B1 names where public status needs explicit boundary.
    should = (not prior) or bool(re.search(r'未披露|待验证|not disclosed|not captured|unclear|verify|not publicly disclosed', prior, re.I)) or str(c.get('priorityTier','')).startswith(('A0','A1','B1','B2'))
    if not should: continue
    c['revenueScale'] = d['revenue']
    c['revenueScaleZh'] = d['revenue']
    c['publicCommercialStatus'] = d['status']
    c['commercialMetricConfidence'] = d['confidence']
    c['commercialMetricSource'] = d['source']
    c['commercialDiligenceAsk'] = d['ask']
    c['keyDiligence'] = d['ask']
    c['nextAction'] = d['ask']
    c['nextActionZh'] = d['ask']
    boundary = f"v16 commercial metric status: {d['status']} ({d['confidence']}); source={d['source']}; ask={d['ask']}"
    if boundary not in (c.get('evidenceBoundary') or ''):
        c['evidenceBoundary'] = (c.get('evidenceBoundary') or '') + ' | ' + boundary
    # Add/replace v16 public commercial metric in keyMetrics.
    km = [x for x in (c.get('keyMetrics') or []) if not str(x).startswith('v16 public commercial status:')]
    km.append(f"v16 public commercial status: {d['status']} / {d['confidence']} — {d['revenue']}")
    c['keyMetrics'] = km
    dc = c.setdefault('dataCompleteness', {})
    dc.update({'hasRevenueScale': True, 'v16CommercialMetricLoaded': True, 'v16CommercialStatus': d['status']})
    # Keep investor-facing notes current without wiping old qualitative notes entirely.
    v16_note = f"v16 commercial metric hardening: {d['revenue']} Diligence ask: {d['ask']} Source boundary: {d['source']}"
    old_notes = c.get('notesClean') or c.get('notes') or ''
    if 'v16 commercial metric hardening:' not in old_notes:
        c['notesClean'] = (old_notes + '\n' + v16_note).strip()
        c['notes'] = c['notesClean']
    # Add/replace embedded evidence so the company-detail Evidence tab and
    # missing-data readiness reflect this public commercial proof review.
    ev_list = c.setdefault('evidence', [])
    ev_list = [ev for ev in ev_list if ev.get('type') != 'v16_public_commercial_metric_review']
    ev_list.append({
        'date': now[:10],
        'type': 'v16_public_commercial_metric_review',
        'note': f"{d['status']} / {d['confidence']}: {d['revenue']} Diligence ask: {d['ask']}",
        'url': d['source'],
        'sourceId': SOURCE_ID,
    })
    c['evidence'] = ev_list
    updated.append(cid)

state['meta']['updatedAt'] = now
state['meta']['uiVersion'] = '16'
state['meta']['snapshotVersion'] = 'v16-commercial-metrics-hardening'
state['meta']['commercialMetricHardening'] = {
    'asOf': now,
    'sourceId': SOURCE_ID,
    'companiesUpdated': len(updated),
    'updatedCompanyIds': updated,
    'method': 'For A0/A1/B1/B2 pre-IPO track names, convert ambiguous revenue/ARR/backlog fields into explicit public commercial status: reported metric where available, otherwise not publicly disclosed + diligence ask + source boundary. No gated DB fabrication.'
}

STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

# SQLite sync: source registry + company_metrics + companies current_stage/updated_at minimal.
con=sqlite3.connect(DB); cur=con.cursor()
cur.execute('insert or replace into source_registry(id,source_name,source_type,connector_status,refresh_frequency,credential_env_var,limitations,last_checked_at) values(?,?,?,?,?,?,?,?)',
            (SOURCE_ID, SOURCE['name'], SOURCE['sourceType'], SOURCE['connectorStatus'], SOURCE['refreshFrequency'], '', SOURCE['limitations'], now))
# Keep SQLite evidence_items aligned with embedded company evidence for DB/API health counts.
cur.execute('delete from evidence_items where source_id=?', (SOURCE_ID,))
for cid in updated:
    c=companies[cid]; d=DATA[cid]
    cur.execute('delete from company_metrics where company_id=? and source_id=?', (cid, SOURCE_ID))
    rows=[
        ('Public commercial status', d['status'], '', 'commercial_status', 'v16', now, d['confidence'], d['source']),
        ('Revenue/ARR/backlog public proof', d['revenue'], '', 'revenue', 'v16', now, d['confidence'], d['ask']),
        ('Commercial diligence ask', d['ask'], '', 'diligence', 'v16', now, d['confidence'], d['source']),
    ]
    for name,val,unit,typ,period,asof,conf,notes in rows:
        cur.execute('insert into company_metrics(company_id,metric_name,metric_value,metric_unit,metric_type,period,as_of,source_id,confidence,notes) values(?,?,?,?,?,?,?,?,?,?)',
                    (cid,name,val,unit,typ,period,asof,SOURCE_ID,conf,notes))
    cur.execute('insert into evidence_items(company_id,claim,value,evidence_type,source_id,source_url,as_of,captured_at,confidence,needs_refresh,notes) values(?,?,?,?,?,?,?,?,?,?,?)',
                (cid, 'v16 public commercial metric status', d['revenue'], 'public_commercial_metric_review', SOURCE_ID, d['source'], now[:10], now, d['confidence'], 1, d['ask']))
con.commit(); con.close()
print(json.dumps(state['meta']['commercialMetricHardening'], ensure_ascii=False, indent=2))
