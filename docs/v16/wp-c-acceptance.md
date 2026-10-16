# WP-C：验收记录

日期：2026-10-16。范围为真实 T5 的离线 Web 回放展示、必要只读元数据 API、相关测试和四份 WP-C 文档。未运行收费模型、未改 Agent 算法 / Oracle / Provider / FinalizeGate / 评分，未提交本地运行产物。旧 G3 和研究 Gate 文档不被本记录覆盖。

## 已执行验证

在独立 worktree `codex/wp-c-real-replay`，`PYTHONPATH` 指向 worktree/src，Python 使用原仓库已有 `.venv/Scripts/python.exe`。

```powershell
$env:WP_C_REAL_TRACE='results/v16/wp-c-real-replay/t5/trace.json'
node --experimental-default-type=module --test tests/web/*.test.mjs
python -m pytest -q tests/integration/test_web.py tests/integration/test_web_replay_metadata.py tests/integration/test_v16_artifact_boundaries.py
python -m ruff check src/incident_lens/web/server.py tests/integration/test_web_replay_metadata.py
git diff --check
$env:WP_C_BROWSER_OUT='results/v16/wp-c-real-replay/browser-final'
node --experimental-default-type=module tests/web/browser-real.cjs
```

| 验证 | 实际结果 / 证据 |
|---|---|
| Node | 21 passed、0 skipped、0 failed；包括真实 T5 全部 104 个位置的前缀重建、时间顺序、完整最终状态、模型失败计数、commit/proposal、书签位移、来源与 HTML 安全。`node-tests-final.log` |
| Python API / boundaries | 27 passed，15.98s；metadata allowlist、corrupt/missing/shape、companion identity/result binding、unsafe companion、不构造 provider、不执行 graph。`backend-tests-final.log`；此前 Coordinator 独立运行较早版本 24 passed |
| Ruff / whitespace | Coordinator `ruff check src scripts tests` 和 `git diff --check` exit 0 |
| 实际浏览器 | `browser-final/receipt.json` passed=true；真实本地 server，intercepted=false，0 page errors，0 `/api/run` requests |
| 浏览器覆盖 | T5 103 事件、4 REVIEW、书签与跳转、4×播放暂停、Previous/Next、角色选择、类别过滤、5 步因果链、报告下载与 rewind 重新锁定、Inspector 清空、来源漂移、档案库 Demo 链接；3 个保存的 Mock/缺失/故障 fixture 和缺失/损坏 Trace 通过实际 API。1×/2×/4×选项均已实现，本次自动浏览器播放使用 4× |
| 布局 | 实际 1440×1000 深/浅主题，390×844 窄屏、844×390 横屏，reduced-motion；无水平溢出；13 张截图保留并人工查看关键 desktop/mobile/inspector 图 |
| 完整 pytest | 冻结源码最终全量 **960 passed、3 skipped，336.15s，exit 0**：`full-pytest-frozen.log` / `.exit`。三项 skip 为 Windows symlink 权限限制。首轮 955 passed、2 failed、3 skipped，404.08s；两项失败为并行 UI 修改触发 protocol / benchmark lock drift，原日志 `full-pytest.log` 保留。最终 214 个源码/测试文件指纹复核无变化：`frozen-source-verification.json` |
| 独立 QA | `/root/qa` 只读代码/API/真实浏览器审查通过，无未解决 P0/P1/P2；其发现的 workflow/timeline role 选择器冲突已修复并验证。21 Node、24 API 独立通过，最终 Inspector 改动再次审阅；收据 `independent-qa.md`。审查者未最终复审四份文档、未独立跑全量，均由 Coordinator 接手 |

原始运行、失败重试和最终证据均保留在 `results/v16/wp-c-real-replay/`。首轮 browser/ 捕捉到 DECISION 后、TASK_ASSIGNED 前角色未显示，已修正；browser-02/ 因测试脚本未展开分类的 details 而超时，已修正测试操作；browser-03/ 成功后改进 Inspector 可读性，最终 browser-final/ 再次通过。不覆盖失败证据。

## Completion 对照

| 完成条件 | 状态 |
|---|---|
| 真实 T5 Trace 完整加载、103 顺序事件与无模型重执行 | PASS：实际 API / browser / reducer |
| 工作流、真实决策/任务/数据流可追溯 | PASS：包含“建议未执行”区分 |
| 4 次 Review 可核对 | PASS：1 insufficient / 3 sufficient，版本、理由和 checks 可查 |
| 两个竞争假设排除可追溯 | PASS：PostgreSQL 首见即 rejected；resource saturation 在提交事件 92 rejected |
| 最终 RCA 引用真实公开证据 | PASS：5 步链、5 支持引用；不是 Oracle 准确率认证 |
| 无未来调查状态泄漏 / 虚构交流 | PASS（所测范围）：前缀观察、commit history、报告/下载 gate、seek 清 Inspector |
| Timeout / Recovery / Provenance | PASS：3 对 call ID 关联、常显 SOURCE DRIFT、unknown 数值保留 |
| 3–5 分钟演示 | 脚本与章节已交付；未声称有人类现场计时或录屏 |
| 自动化与实际浏览器 | PASS：21 Node、27 API/boundaries、960 全量 Python（3 个平台 skip）、实际后端 browser |
| 独立 QA 无阻塞 | PASS：代码/API/浏览器范围无未解决工程问题；文档核对与全量回归由 Coordinator 完成 |

WP-C Completion：**PASS（本任务工程与录制 Demo 范围）**。Coordinator 已逐项核对四份文档、实际产物、最终 diff、测试与浏览器证据；独立代码/API/浏览器 QA 无未解决工程阻塞。3–5 分钟脚本与可操作章节已交付，尚无人类现场计时或视频，且本结论不改变研究/正式实验的上游 Gate。

## 交付位置与任务接续

独立分支 `codex/wp-c-real-replay`，worktree 为 `C:/Users/RickyMa/.codex/worktrees/wp-c-real-replay/IncidentLens`；本次不合并或覆盖原工作区的并行 WP-B / Agent 改动。只提交 Web、必要只读 API、相关测试和四份文档，不提交 ignored results。启动与当前可用入口以 `wp-c-demo-walkthrough.md` 为准。

本次启用了用户明确指定的 multi-agent-orchestration：只读 Trace Scout、单个 worktree Implementer、独立只读 Reviewer；无共享 checkout 并行写。子 Agent 在交付代码及 QA 结论后达到额度限制，Coordinator 接续完成文档核对、冻结全量回归、产物/源码哈希复核与提交检查。原失败日志、成功重跑及审查范围边界均保留。

## 剩余限制

T5 是单次 development-visible 真实运行，发生源码漂移，不支持冻结实验、四架构优势、整体准确率或供应商可靠率主张。companion 只有内部一致性校验、没有签名。大 Trace 性能、屏幕阅读器、全部设备、现场 3–5 分钟计时和录屏未验收。真实 Windows symlink 权限限制保留既有说明；unsafe companion 回归用拒绝解析模拟覆盖。真实运行 JSON / protocol / 截图均留本地 ignored results，不能作为可公开提交的数据包。
