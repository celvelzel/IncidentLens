# WP-C：3–5 分钟真实调查 Demo

## 启动与入口

本次交付保留在独立 worktree / `codex/wp-c-real-replay`，尚未合并到原工作区。直接使用已验收版本（不调用收费模型）：

```powershell
Set-Location 'C:/Users/RickyMa/.codex/worktrees/wp-c-real-replay/IncidentLens'
$env:PYTHONPATH="$PWD/src"
& 'C:/Develop/python_projects/COMP5584_Agents/IncidentLens/.venv/Scripts/python.exe' -m incident_lens.web --port 8797
```

打开 `http://127.0.0.1:8797/#/run?path=results%2Fv16%2Fwp-c-real-replay%2Ft5%2Ftrace.json&demo=1`。也可进入 `#/library`，搜索 `incident_2001`，核对 REAL / full / `run-801a52cff3a5491aaf5df79b8f543614` 对应行，点“演示回放”。合并到原仓库后可使用原始档案的直接入口：

`http://127.0.0.1:8797/#/run?path=results%2Fv16%2Flive-e2e%2Fg1a-20261015-01%2Fincident-2001-full%2Ftrace.json&demo=1`

本次独立 worktree 验收使用逐字节公开副本，直接入口的 path 为 `results%2Fv16%2Fwp-c-real-replay%2Ft5%2Ftrace.json`。worktree 无独立 venv 时运行原仓库 `.venv/Scripts/python.exe`，同时保持 `PYTHONPATH` 指向当前 worktree 的 `src`。不需要密钥、Oracle、实时 Provider 或 `/api/run`。真实档案缺失时页面报错，不生成替代 REAL Trace。

## 现场讲解顺序

| 时间 | 操作 | 可核对的讲解 |
|---|---|---|
| 0:00–0:30 | 保持位置 0，展开来源元数据 | “这是 REAL LLM 的已录制调查，初始只知道公开观察窗口。103 个事件；来源检查发现 graph.py 漂移，所以不是完全冻结的正式实验。token / cost 未知。” |
| 0:30–1:00 | “首次调度”，选 Changes / Metrics | “Coordinator 分派基线指标与变更调查。这里是原始问题、理由和判别标准，经共享状态发布结果，没有虚构聊天。” |
| 1:00–1:25 | “配置变更证据”，点 Evidence ID | “公开 config 记录池从 20 降到 2、并发 120。Inspector 显示来源工具/Agent、事故时间与执行时间；当前尚无最终报告。” |
| 1:25–2:05 | “首次证据不足审查”，展开 REVIEW | “Verifier 认为因果链有缺口，提出 blocking 与 optional 检查。Logs 在这里是建议，没实际派发。接下来实际补查 Backend metrics 与数据库连接。” |
| 2:05–2:40 | “竞争假设 · postgres_connection_exhaustion” | “数据库连接 30/100，后端 waiters 118。PostgreSQL 假设首次被保存时已为 REJECTED，我们没有补造早期 OPEN 状态。查看真实支持/反对证据。” |
| 2:40–3:10 | “首次 FinalizeGate 阻断” | “sufficient 不等于立即通过。Gate 因另一个竞争假设未解决而拒绝 finalization。” |
| 3:10–3:40 | “竞争假设 · backend_resource_saturation” | “Coordinator 后来拒绝将下游饱和现象当作根因；配置回退证据指向更具体机制。点击状态历史能回到提交事件和原始理由。” |
| 3:40–4:20 | “最终审查”，再“最终报告” | “核对四次 Review、最终接受、STOP 与成功终止。最终报告有五步因果链与五条支持证据，点击引用检查来源。” |
| 4:20–4:40 | 展开可靠性，再回首步 | “三个 timeout 都有按 call_ids 关联的恢复。回首步后报告、证据和完整下载重新锁定；此次回放没有调用模型。” |

可用 Play/Pause、1×/2×/4×、Previous/Next 与数字 Jump 补充逐事件演示。语义章节在缺失时禁用；不能对其他档案承诺一定存在同样章节。演示时优先选择章节，103 个事件全速串播会掩盖审查和状态提交的区别。

## 留存证据

本次实际浏览器结果与截图：`results/v16/wp-c-real-replay/browser-final/receipt.json`、`01-source-drift-dark.png`、各 `chapter-*.png`、`evidence-provenance.png`、`final-report-dark.png`、`final-report-light.png`、`mobile-light.png`、`landscape-light.png`。数据和截图位于 ignored results，仅作本地验收；未提交私有运行文件，也未录制/提交演示视频。脚本时长设计为 3–5 分钟，尚无人类现场计时证据。
