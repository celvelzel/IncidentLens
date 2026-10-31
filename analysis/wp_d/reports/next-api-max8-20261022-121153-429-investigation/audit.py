"""Read saved fourth-round artifacts only; no provider or project imports."""
import collections
import datetime
import hashlib
import json
import pathlib
import statistics

OUT = pathlib.Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BATCH = ROOT / 'results/v16/wp-d/next-api-max8-20261022-121153'
PREVIOUS = OUT.parent / 'next-api-max8-20261022-121153-retry4-c2-20261023-094118'
read = lambda p: json.loads(p.read_bytes())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
manifest = read(BATCH / 'batch-manifest.json')
retry = read(PREVIOUS / 'retry-manifest.json')
before = {str(p.relative_to(BATCH)): digest(p) for p in BATCH.rglob('*') if p.is_file()}
requests, usages, deltas, latencies, rows = [], [], [], [], []
for entry in retry['slots']:
    directory = BATCH / entry['new_attempt']
    events = [json.loads(x) for x in (directory / 'observability/events-0001.jsonl').read_text(encoding='utf-8').splitlines()]
    starts, rate_limited, recovered = {}, set(), set()
    categories = collections.Counter()
    for e in events:
        d = e.get('event', {}).get('details', {})
        t = datetime.datetime.fromisoformat(e['recorded_at']).timestamp()
        key = (d.get('logical_call_id'), d.get('http_attempt_index'))
        if e['kind'] == 'PROVIDER_ATTEMPT':
            requests.append(t)
            starts[key] = t
            deltas.append((t, 1))
        if e['kind'] in ('PROVIDER_CALL_COMPLETED', 'PROVIDER_FAILURE_CLASSIFIED') and key in starts:
            deltas.append((t, -1))
            starts.pop(key)
        if e['kind'] == 'PROVIDER_FAILURE_CLASSIFIED':
            categories[d.get('category', 'unknown')] += 1
            if d.get('provider_http_status') == 429:
                rate_limited.add(key[0])
                latencies.append(d['elapsed_ms'])
        if e['kind'] == 'PROVIDER_CALL_COMPLETED' and key[0] in rate_limited:
            recovered.add(key[0])
        if e['kind'] == 'LLM_CALL':
            for u in d.get('request_usage', []):
                if u.get('total_tokens') is not None:
                    usages.append((t, u['total_tokens']))
    v = read(directory / 'verification.json')
    rows.append(dict(slot=entry['slot'], attempt=entry['new_attempt'], classifications=dict(categories), recovered_after_429=len(recovered), requests=v['actual_http_requests'], termination=v['termination']))
active = peak = 0
for t, delta in sorted(deltas):
    active += delta
    peak = max(peak, active)
after = {str(p.relative_to(BATCH)): digest(p) for p in BATCH.rglob('*') if p.is_file()}
summary = dict(
    scope='Only this fourth-round batch; other account/API-key traffic unavailable',
    physical_requests=len(requests),
    max_rolling_60s_requests=max(sum(t-60 < x <= t for x in requests) for t in requests),
    max_rolling_1s_requests=max(sum(t-1 < x <= t for x in requests) for t in requests),
    peak_inflight_from_client_events=peak,
    remaining_unmatched_inflight=active,
    http_429_count=len(latencies),
    median_429_response_ms=statistics.median(latencies),
    recorded_tokens=sum(v for _, v in usages),
    max_rolling_60s_recorded_tokens_at_call_completion=max(sum(v for x,v in usages if t-60 < x <= t) for t,_ in usages),
    token_caveat='Incomplete reported usage, timestamped by logical-call completion; not provider TPM accounting',
    recovered_logical_calls_after_429=sum(r['recovered_after_429'] for r in rows),
    frozen_inputs_checked=len(manifest['hashes']),
    frozen_mismatches=[p for p,h in manifest['hashes'].items() if digest(ROOT/p) != h],
    batch_files_checked=len(before), batch_unchanged_during_audit=before == after,
    slots=rows,
)
(OUT/'evidence.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k != 'slots'}, ensure_ascii=False, indent=2))
