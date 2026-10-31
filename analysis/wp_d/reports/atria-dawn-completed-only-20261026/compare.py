"""Read archived HPC results only; no runtime imports or provider calls.

Run from this checkout's root. Outputs stay beside this script.
"""
import hashlib
import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / 'results/hpc-wpd/atria-dawn-dev40-20261025T154709Z'
OUT = Path(__file__).resolve().parent
VARIANTS = ['full', 'single', 'fixed', 'dynamic_no_verifier']
LABELS = ['Full', 'Single', 'Fixed', 'NoVerifier']

def load(p):
    return json.loads(p.read_text(encoding='utf-8'))

rows, hashes = [], {}
summary = load(BATCH / 'summary.json')
for slot in summary['slots']:
    p = BATCH / 'batch' / slot['attempt']
    r, v, t = [load(p / f) for f in ['result.json', 'verification.json', 'trace.json']]
    for f in ['result.json', 'verification.json', 'trace.json', 'scope.json']:
        fp = p / f
        hashes[str(fp.relative_to(ROOT))] = hashlib.sha256(fp.read_bytes()).hexdigest()
    term = r['termination']
    ok = (slot['status'] == 'completed' and not term['runtime_failure']
          and not v['runtime_failure'] and v['protocol_valid'] and v['stop_completion']
          and v['source_unchanged'] and r['workflow_status'] != 'FAILED')
    events = Counter(e['event_type'] for e in t['state']['events'])
    if ok:
        assert events['TOOL_CALL'] == t['state']['tool_calls_used']
    assert v['actual_http_requests'] == v['llm_requests']
    assert t['elapsed_ms'] > 0
    rows.append(dict(slot=slot['slot'], incident=slot['incident'], variant=slot['variant'],
                     included=ok, seconds=t['elapsed_ms']/1000 if ok else None,
                     requests=v['actual_http_requests'] if ok else None,
                     tools=t['state']['tool_calls_used'] if ok else None,
                     abstained=(r['status']=='INCONCLUSIVE') if ok else None,
                     result_status=r['status'], termination=term,
                     source=str(p.relative_to(ROOT))))
assert len(rows) == 40 and sum(x['included'] for x in rows) == 24
assert len({(x['incident'], x['variant']) for x in rows}) == 40
totals = {}
for variant in VARIANTS:
    rs = [x for x in rows if x['variant']==variant and x['included']]
    totals[variant] = dict(completed=len(rs), seconds=sum(x['seconds'] for x in rs),
                           requests=sum(x['requests'] for x in rs), tools=sum(x['tools'] for x in rs),
                           abstained=sum(x['abstained'] for x in rs))
output = dict(batch=str(BATCH.relative_to(ROOT)), source_commit='cb955f8',
              duration_basis='trace.elapsed_ms / 1000 (investigation runtime, excludes cluster queue gaps)',
              request_basis='verification.actual_http_requests (includes repair attempts)',
              tool_basis='trace.state.tool_calls_used, checked against TOOL_CALL event count',
              rows=rows, totals=totals, source_sha256=hashes)
(OUT/'comparison.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['# Atria-Dawn HPC：正常完成运行的四架构逐例对比', '',
         '来源：`codex/hpc-wpd` 提交 `cb955f8`；批次 `atria-dawn-dev40-20261025T154709Z`。', '',
         '仅纳入正常完成、协议有效、STOP 完成、无 runtime_failure 且 source_unchanged 的运行。40 槽中纳入 24 槽、排除 16 槽。每槽仅一个 attempt，无择优替换。', '',
         '每格：**分钟 / 真实 HTTP 请求数 / 工具调用数 / 是否弃答**。是=INCONCLUSIVE；否=RESOLVED（仅表示输出根因，尚未独立核验正确性）。—=失败排除。', '',
         '耗时采用 trace.elapsed_ms，排除集群排队及 supervisor 恢复空档；请求含结构化修复；工具调用是实际调用次数，不是去重查询数。正常完成过程中的修复仍计入。', '',
         '| 样例 | Full | Single | Fixed | NoVerifier |', '|---|---|---|---|---|']
for incident in sorted({x['incident'] for x in rows}):
    cells = []
    for variant in VARIANTS:
        r = next(x for x in rows if x['incident']==incident and x['variant']==variant)
        cells.append(f"{r['seconds']/60:.2f} / {r['requests']} / {r['tools']} / {'是' if r['abstained'] else '否'}" if r['included'] else '—')
    lines.append('| '+incident[-4:]+' | '+' | '.join(cells)+' |')
lines += ['', '| 架构 | 完成数 | 总分钟 | 平均分钟 | 请求总数（平均） | 工具总数（平均） | 弃答数 | 输出根因数 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
for variant, label in zip(VARIANTS, LABELS):
    d=totals[variant]; n=d['completed']
    lines.append(f"| {label} | {n} | {d['seconds']/60:.2f} | {d['seconds']/60/n:.2f} | {d['requests']}（{d['requests']/n:.2f}） | {d['tools']}（{d['tools']/n:.2f}） | {d['abstained']} | {n-d['abstained']} |")
lines += ['', '## 逐例解读', '',
 '- **3001**：Full 唯一输出根因；15.54 分钟、20 请求、15 工具，比同案完成的 NoVerifier 更省；Fixed 最快但弃答。Single 排除。',
 '- **3002**：NoVerifier 唯一输出根因；Fixed 用更少资源弃答。Full、Single 均排除，不能判断 Verifier 在此例的收益。',
 '- **3003**：仅 Fixed、NoVerifier 完成，均弃答；Fixed 2.75 分钟、7 请求、7 工具，低于 NoVerifier 16.25 分钟、29 请求、23 工具。Full、Single 排除。',
 '- **3004**：NoVerifier 输出根因；Single 弃答且耗时更长，两者均 28 请求；Fixed 更快但弃答。Full 排除。',
 '- **3005**：仅 Full 完成，58.79 分钟、46 请求、37 工具后弃答；没有可用的跨架构配对结果。',
 '- **3006**：Single、Fixed、NoVerifier 均弃答；Fixed 1.84 分钟最低；NoVerifier 比 Single 更快（19.28 对 47.53 分钟）。Full 排除。',
 '- **3007**：Single、Fixed、NoVerifier 均弃答；Fixed 最省。Single 工具更多（28 对 18），但比 NoVerifier 耗时短（25.00 对 40.67 分钟），工具数不能直接解释延迟。Full 排除。',
 '- **3008**：Full、Single、Fixed 均弃答；Full 比 Single 更快，但请求略多（34 对 33）；Fixed 最省。NoVerifier 排除。',
 '- **3009**：仅 Single、Fixed 完成且均弃答；Single 43.73 分钟、41 请求、28 工具，Fixed 3.34 分钟、8 请求、7 工具。Full、NoVerifier 排除。',
 '- **3010**：Full、NoVerifier 均弃答；NoVerifier 略快且请求/工具更少（32/24 对 37/29）。Single、Fixed 排除。', '',
 '## 解释边界', '',
 '24 个完成运行包含 21 次弃答、3 次输出根因。输出根因不等于根因命中；原归档没有独立标签语义评估，本报告不将 RESOLVED 改称正确诊断。', '',
 '没有四架构全部完成的样例，分组平均值来自不同样例集合，只能描述本次完成运行；不能据此证明架构整体优劣或 Verifier 的因果收益。Fixed 在有完成结果的同案比较中均最快，但八次均弃答。', '',
 '排除的 16 槽不是已证实的网络/API 服务故障：归档核查为 10 次 BAD_ARGS、2 次 STRUCTURED_OUTPUT_INVALID、1 次 FINDING_IDENTITY_MISMATCH、3 次 BUDGET_EXHAUSTED。后者按冻结终态排除，不在这里重分类或推断确实触及硬上限。', '',
 '## 排除清单', '', '| 槽位 | 样例 | 架构 | 冻结终止原因 |', '|---|---|---|---|']
for r in rows:
    if not r['included']:
        lines.append(f"| {r['slot']} | {r['incident'][-4:]} | {r['variant']} | {r['termination']['reason']} |")
lines += ['', '复算脚本：compare.py；逐槽指标与输入 SHA256：comparison.json。只读原始产物，无 API 请求、无重跑。']
(OUT/'comparison.zh-CN.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
print('\n'.join(lines[:27]))
