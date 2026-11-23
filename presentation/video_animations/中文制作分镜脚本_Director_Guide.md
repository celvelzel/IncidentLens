# IncidentLens 10 分钟视频制作与分镜脚本（中文导演版）

> **配套使用说明**：
> - **这份中文文档**给你做拍摄、录屏、剪辑和给 ChatGPT 下 Prompt 用（画面、操作、剪辑节奏全中文）；
> - **英文提词稿**保留在 [video_presentation_script_10min.md](file:///Users/songxiaowen/.gemini/antigravity/brain/05703cbb-3389-49f5-ac71-826198b52baa/video_presentation_script_10min.md)，录配音时直接照着里面的 `[Voiceover]` 读，**两份文档的 9 个段落和时间戳 100% 一一对应**。

---

## 一、全片节奏与素材规划（总长 10:00）

- **实机录屏（4 段，共约 4 分 55 秒）**：终端操作 + 浏览器 Web 控制台（最能体现工程真实感，老师最买账）
- **ChatGPT 制作动画（4 段，共约 3 分 35 秒）**：用 HTML5/SVG 浏览器全屏 1080p 录屏（画面文字用英文，配合你的英文口播）
- **精简 PPT 静止页（2 页，共约 1 分 30 秒）**：局限性反思页 + 总结致谢页

| 时间 | 段落 | 画面类型 | 这一段你在镜头里/剪辑时要做什么 |
| --- | --- | --- | --- |
| **00:00–00:50** | 1. 开场痛点 | **动画 #1** + 封面页 | 对比通用 Agent 乱编结论 vs IncidentLens 三条硬契约 |
| **00:50–02:10** | 2. 架构与四变体 | **动画 #2** | 演示动态派单闭环、权限隔离、`FinalizeGate` 和 4 种对照架构 |
| **02:10–03:00** | 3. **实机 Demo 1** | **终端录屏** | 跑数据校验 + 工具权限隔离单测 + 505 项回归 + 110/110 故障矩阵 |
| **03:00–04:30** | 4. **实机 Demo 2** | **终端录屏** | 现场用 OhMyGPT (`hy4-flash` 关思考) 跑真实案例 + 展示 DeepSeek `4014`（抗误导成功）vs `4018`（主动弃权） |
| **04:30–06:20** | 5. **实机 Demo 3** | **浏览器录屏** | 打开本地 Web 控制台 `127.0.0.1:8022`，逐面板演示“已定稿”和“主动弃权”两条轨迹的纯离线回放 |
| **06:20–07:05** | 6. **实机 Demo 4** | **动画 #3** + **代码/终端** | 展示防泄漏回执机制 + 切到代码/终端展示我们抓出并修复 `leading_review_consistency` Bug 的实证 |
| **07:05–08:55** | 7. 核心实验数据 | **动画 #4**（动态图表） | 依次呈现 DeepSeek 144 槽位主表 → `hy4-flash` 开/关思考对比 → 无思考下 `Single` 0/5 vs `Dynamic` 5/6 |
| **08:55–09:35** | 8. 局限与改进 | **PPT 三栏页** | 客观说明 0 误判的规则耦合边界，提出支持集评分、OOD 与按需 Verifier |
| **09:35–10:00** | 9. 总结收尾 | **PPT 致谢页** | 3 点收束 + 致谢 |

---

## 二、逐段分镜制作指南（与英文稿精确同步）

### 第 1 段：开场痛点与核心主张（00:00–00:50）
- **画面安排**：
  - `00:00–00:35`：播放 **ChatGPT 动画 #1**（左半边：通用 Agent 乱编根因、被红色扫描线打上“伪造引用/无权限边界/从不弃权”；右半边：IncidentLens 弹出三条发光契约）。
  - `00:35–00:50`：切入深色封面页（大字标题 + 你的姓名/学号/课程名）。
- **对应英文口播要点**：引出生产事故复盘最怕“编故事”，亮出 IncidentLens 三大契约（有据可依、只读权限隔离、证据不足主动弃权 `INCONCLUSIVE`），预告全片内容。

---

### 第 2 段：系统架构与四种对照模式（00:50–02:10）
- **画面安排**：
  - `00:50–01:40`：播放 **ChatGPT 动画 #2 前半段**——LangGraph 闭环：公开摘要 → Coordinator 按缺口动态派 1–2 个带权限钥匙的专家 → 汇入共享证据板 → 进入红色盾牌 `FinalizeGate`（4 条确定性勾选）→ 缺证据就回流补查，全过则输出 `RESOLVED`。
  - `01:40–02:10`：播放 **ChatGPT 动画 #2 后半段**——四张架构卡片并排：`Single`、`Fixed-4`、`Dynamic（主架构⭐）`、`Full（+ 独立 Verifier）`。
- **对应英文口播要点**：讲清 4 类专家分工、两道防线（ACL 权限 + 确定性 `FinalizeGate` 不信模型自报置信度），以及为什么要同预算对比 4 种架构。

---

### 第 3 段：实机 Demo 1 —— 数据校验、权限隔离与可靠性测试（02:10–03:00）
- **录屏准备**：终端深色主题，字号调到 **16–18pt**，清屏（`clear`）后从仓库根目录开始录。
- **操作顺序与剪辑提示**：
  1. `02:10–02:22`：敲 `.venv/bin/python -m incident_lens.cli validate-data`，停顿 2 秒圈出 `"ok": true`。
  2. `02:22–02:38`：敲 `.venv/bin/pytest tests/isolation/test_tool_acl.py -v`，鼠标圈出 logs 调配置被拦截的用例全部 `PASSED`。
  3. `02:38–02:50`：敲 `.venv/bin/pytest tests/unit tests/evaluation tests/reliability tests/isolation -q`（跑点点的时候剪辑 **2 倍速**，停在绿色的 **`505 passed, 1 skipped`** 上 2 秒）。
  4. `02:50–03:00`：打印 `results/offline-reliability-eval/summary.json` 头部，高亮 **`110 / 110 matrix_passed`**。
- **对应英文口播要点**：展示工程底座扎实——公开数据无泄漏、越权调用会被运行时拦截、505 项单测与 110 项故障注入矩阵全绿。

---

### 第 4 段：实机 Demo 2 —— 终端真机跨模型排查对比（03:00–04:30）
- **录屏准备**：提前试跑确认网络畅通；录实时运行时，等待 API 返回的 30–50 秒可在剪辑里 **3x–4x 加速**并右上角加小标签 `3x Speed`，命令行和最终结果切回 `1x` 正常速度！
- **操作顺序与剪辑提示**：
  1. `03:00–03:45`：现场执行 OhMyGPT（腾讯 `hy4-flash` 关思考 + `json_schema`）真机排查：
     ```bash
     .venv/bin/python -m incident_lens.cli run \
       --case incident_001 --provider ohmygpt \
       --response-format json_schema --thinking disabled \
       --variant dynamic --out results/demo_video_hy4
     ```
     跑完后 `cat results/demo_video_hy4/report.md`，用鼠标上下扫过：`status: RESOLVED`、`culprit_service`、`failure_mode` 和真实证据引用 ID 列表。
  2. `03:45–04:30`：运行一段简短打印命令（见下方清单），同屏展示刚跑完的官方 DeepSeek `deepseek-flash` 两个硬化集代表结果：
     - **`incident_4014`（误导性变更）**：圈出系统顶住同服务干扰变更，47 秒锁定 `postgres_lock_contention`；
     - **`incident_4018`（缺失证据）**：圈出系统查了 12 次工具后老实输出 `INCONCLUSIVE`，不瞎猜。
- **对应英文口播要点**：强调这是真模型实机运行而非 Mock，对比“抗误导定位成功”和“缺证据体面弃权”两种核心行为。

---

### 第 5 段：实机 Demo 3 —— 本地 Web 控制台录制回放（04:30–06:20）
- **录屏准备**：提前执行 `.venv/bin/python -m incident_lens.cli web --port 8022`，浏览器打开 `http://127.0.0.1:8022`，缩放调到 **115%**，关掉无关浏览器标签页。提前保证档案库里至少有 1 条 `RESOLVED`（如 `demo_video_hy4`）和 1 条 `INCONCLUSIVE`（如 `demo_video_abstain`）。
- **鼠标点击与停留节奏**：
  1. `04:30–04:45`：停在 Trace Archive 总览页，鼠标圈一下顶部的 **`Recorded Replay — no provider calls`** 标识。
  2. `04:45–05:10`：点进 **已解决轨迹（`RESOLVED`）**，滑过 **时间线面板**：鼠标依次指 `DECISION` → `TASK_ASSIGNED` → `TOOL_CALL` → `MERGE` → `DIAGNOSIS_ACCEPTED`。
  3. `05:10–05:30`：点开 **假设演化面板**：展示多个竞争假设如何随着新证据收敛到唯一根因。
  4. `05:30–05:50`：在报告区 **点击一条引用 ID**，让画面直接跳转/高亮到对应的原始日志或配置 diff 记录（这一步视觉效果极佳！）。
  5. `05:50–06:02`：滑到底部 **停止协议与资源账本**：圈出 `WORKFLOW_STOP_REQUESTED` → `STOP_ACK` → `NORMAL_TERMINATION` 以及 HTTP 请求/Token 计数。
  6. `06:02–06:20`：切回档案库点开 **弃权轨迹（`INCONCLUSIVE`）**：圈出 `root_cause: null`、未关闭的证据缺口说明、以及正常的 `NORMAL_TERMINATION` 状态（不是报错崩溃）。
- **对应英文口播要点**：带观众沉浸式逛一遍可视化审计界面，证明每条结论可溯源、每笔消耗有账本、弃权与报错边界分明。

---

### 第 6 段：实机 Demo 4 —— 防泄漏评测协议 + 实战挖 Bug 修复（06:20–07:05）
- **画面安排**：
  - `06:20–06:42`：播放 **ChatGPT 动画 #3**（左侧公开数据 vs 右侧锁住的 Oracle 保险箱，跑完生成 SHA-256 完成回执才解锁打分，技术失败强制留在分母里）。
  - `06:42–07:05`：切到代码编辑器 + 终端分屏：
    - 编辑器高亮 `src/incident_lens/llm/structured_output.py` 第 31–57 行（展示我们把 `leading_review_consistency` 和 `task_tool_acl` 加入 `_SAFE_TYPES` 和 `_SAFE_REPAIR_HINTS`）；
    - 终端跑 `.venv/bin/pytest tests/unit/test_structured_output_v13.py -k leading_review -v`，亮出绿色的 `1 passed`；
    - 屏幕右下角弹出醒目对比贴片：**`Verify 崩溃率：修复前 8/12 → 修复后 0/144`**。
- **对应英文口播要点**：讲清楚 IncidentBench 为什么可信，顺势讲出最加分的“真实排障修复故事”——把小组代码切到官方 DeepSeek API 跑实验时，定位到 `leading_review_consistency` 错误被消音的暗坑，修复后 9/9 恢复、全量 144 槽位零格式崩溃。

---

### 第 7 段：全量与跨模型核心实验数据（07:05–08:55）
- **画面安排**：播放 **ChatGPT 动画 #4**（三幕动态数据大屏，按键盘 `1`、`2`、`3` 配合口播节奏切换）：
  - `07:05–07:50`（场景 1）：**DeepSeek `deepseek-flash` 硬化集 144 槽位主表 + 帕累托气泡图**
    - 高亮 `Dynamic`：**31/36 (86.1%)**、113.6k Token、56.4s（比 `Single` 省 42.6% Token、比 `Full` 省 39.5% Token、对 `Fixed-4` 18 胜 0 负）；弹出 **`0 False Resolutions (0/137)`** 徽章。
  - `07:50–08:25`（场景 2）：**混元 `tencent/hy4-flash` 开思考 vs 关思考消融（24 槽位）**
    - 动态进度条对比：`48.0 min → 12.6 min`（快 3.8 倍），完成率 `45.8% → 95.8%`（6 次 900s 超时清零），质量 `7/24 → 13/24`。
    - 配合口播解释核心原因：**多智能体是串行工具探索循环，开思考拖慢单步 5–8 倍直接撞墙钟预算，关思考把时间换成了多轮实地查证**。
  - `08:25–08:55`（场景 3）：**最炸裂的跨模型对比（`hy4-flash` 关思考，24 槽位）**
    - 柱状图对比：`Single` 跌到 **1/6（可识别 0/5 崩盘！254k Token）**，而 **`Dynamic` 拉升到 5/6 (83.3%) 且 Token、耗时双双腰斩（−51%）**！
    - 底部弹出特写框：**跨模型共性发现——DeepSeek 和 `hy4-flash` 上，`Dynamic` 丢掉的反事实案例 `incident_4035` 都被 `Full`（Verifier）救回！**
- **对应英文口播要点**：用硬核数据层层递进：单模型全量胜出 → 跨模型反直觉发现（关思考反而更强）→ 轻量模型上多智能体的能力放大效应 → 引出按需 Verifier。

---

### 第 8 段：客观局限与改进方向（08:55–09:35）
- **画面安排**：一张排版干净的 **PPT 三栏卡片页**（全英文短句，配合口播逐栏高亮）：
  1. **Validity Boundary（效度边界）**：0 误判很大程度归功于 `FinalizeGate` 7 条硬规则与合成数据的耦合；人工语义复核待补。
  2. **Evaluation Upgrades（评估升级）**：自动接入 Oracle 里的 `acceptable_support_sets` 打分、把统计 Bootstrap 基准切到 `Dynamic`、引入开放 OOD 真实脱敏日志。
  3. **On-Demand Verifier（按需审核）**：平时走低成本 `Dynamic`，只在竞争/反事实高歧义信号出现时触发 1 次 Verifier。
- **对应英文口播要点**：主动点出系统边界和后续路线，体现研究严谨度（学术汇报极易拿高分）。

---

### 第 9 段：总结与致谢（09:35–10:00）
- **画面安排**：简洁收尾页（3 条精炼结论 + 项目名 `IncidentLens` + `Thank You & Q&A`）。
- **对应英文口播要点**：一句话总结核心价值，礼貌致谢结束。

---

## 三、实机录屏一站式命令（提前跑一遍熟手）

在 `/Users/songxiaowen/.gemini/antigravity/scratch/IncidentLens` 目录下依次执行：

```bash
# 提前准备：生成一条离线弃权轨迹用于 Demo 3 Web 回放
.venv/bin/python -m incident_lens.cli run \
  --case incident_006 --provider mock --cache-mode off \
  --variant dynamic --out results/demo_video_abstain

# === 录 Demo 1（02:10–03:00）===
.venv/bin/python -m incident_lens.cli validate-data
.venv/bin/pytest tests/isolation/test_tool_acl.py -v
.venv/bin/pytest tests/unit tests/evaluation tests/reliability tests/isolation -q
cat results/offline-reliability-eval/summary.json | head -n 25

# === 录 Demo 2（03:00–04:30）===
# 真机跑 OhMyGPT hy4-flash（关思考）：注意如重录需换新目录名
.venv/bin/python -m incident_lens.cli run \
  --case incident_001 --provider ohmygpt \
  --response-format json_schema --thinking disabled \
  --variant dynamic --out results/demo_video_hy4
cat results/demo_video_hy4/report.md

# 打印官方 DeepSeek 144 槽位里的 incident_4014（抗误导成功）与 incident_4018（主动弃权）
.venv/bin/python -c "
import json
from pathlib import Path
for cid in ('incident_4014', 'incident_4018'):
    st = json.loads(Path(f'results/repro-deepseek-flash-hardened144/states/{cid}.dynamic.json').read_text())
    r = st['report']
    print(f'=== {cid} (dynamic / deepseek-flash) ===')
    print('Status:', r['status'], '| Stop:', r['stop_reason'], '| Tools:', st['tool_calls_used'])
    print('Root Cause:', r.get('root_cause'))
    print('Citations:', r.get('supporting_evidence_ids'))
"

# === 录 Demo 3（04:30–06:20）===
.venv/bin/python -m incident_lens.cli web --port 8022
# 浏览器访问 http://127.0.0.1:8022（缩放 115%）

# === 录 Demo 4（06:20–07:05）===
.venv/bin/pytest tests/unit/test_structured_output_v13.py -k leading_review -v
```

---

## 四、给 ChatGPT 的 4 段动画指令（中文下达需求，生成英文画面以匹配英文口播）

> **操作方法**：把下面每段话复制给 ChatGPT，让它生成**单文件 HTML5/SVG 动画**，保存为 `.html` 后用 Chrome/Safari 全屏打开（1920×1080），按 `Shift + Command + 5` 录屏即可。画面文字全是清晰的英文矢量字，和你读的英文稿完美统一！

### 给 ChatGPT 的指令 #1：开场痛点对比动画（35 秒）

```text
请帮我写一个单文件、自包含的 HTML5 + SVG + CSS/JS 演示动画（1920x1080 自适应，深色科技背景 #0F172A，配色使用理大红 #A02337、青绿 #10B981、琥珀黄 #F59E0B、警戒红 #EF4444），页面底部带一个极简的播放/暂停/重播控制条（支持空格键控制），总时长 35 秒。
重要：因为我的汇报是全英文的，动画里出现的所有文字标签必须使用清晰大号的英文（Inter/Arial 字体）。

分镜要求：
1. [0-12秒] 左侧卡片标题 "Generic LLM Agent"：涌入一堆报错日志（Gateway 504、DB Timeout、Redis Spike），Agent 迅速弹出一个虚假结论框 "Root Cause: Primary DB Crash"；随后一道红色验真扫描线扫过，弹出 3 个红色警报标签："Fabricated Citation ID"、"Unbounded Data Access"、"Never Abstains"。
2. [12-26秒] 过渡到右侧卡片 "IncidentLens (Evidence-Driven Multi-Agent)"，三条发光契约依次弹出：
   - （青绿）Cite Observed Evidence Only (Verified Tool Record IDs)
   - （天青）Read-Only Role ACL Isolation
   - （琥珀黄）Abstain Explicitly (INCONCLUSIVE when evidence is missing)
3. [26-35秒] 左右定格，画面中央浮现主标题横幅："IncidentLens: Evidence-Driven Multi-Agent Root Cause Analysis"。
```

### 给 ChatGPT 的指令 #2：多智能体闭环与四架构对比动画（60 秒）

```text
请生成一个单文件 HTML5 + SVG/JS 矢量动画（1920x1080，深蓝灰底 #0F172A，主高亮色 #A02337，带底部播放/暂停/重播控制，总长 60 秒）。动画里的全部文字必须用清晰简洁的英文。

分两幕：
【第一幕 0-38秒：Dynamic 动态排查闭环】
- 顶部节点 "Public Incident Summary" 发出光点流入 "Coordinator"。
- 第一轮：Coordinator 动态点亮两个带权限钥匙图标的专家卡片："Logs (query_logs)" 和 "Database (locks/connections)"，另外两个 "Metrics" 和 "Changes" 保持暗色休眠。
- 发光的证据数据包（标着 E-003、E-007）流入中央 "Shared Evidence Board"。
- 数据流进入底部的理大红盾牌 "FinalizeGate (Deterministic)"，依次打勾 4 项规则：
  [✓] >= 2 Independent Sources  [✓] Cause-Specific Discriminator  [✓] Temporal Compatibility  [✓] No Unresolved Rival / Contradiction
- 演示第 1 轮有 1 项标黄未通过 → 光点回流到 Coordinator → 激活 "Changes (config_diff)" → 第 2 轮 4 项全绿 → 输出 "RESOLVED (Grounded Report)"。

【第二幕 38-60秒：四种对照架构并排对比】
切出 4 张横向卡片，用微动效展示数据流动区别：
1. Single：1 个大圆节点杂乱连着全部 4 类工具。
2. Fixed-4：4 个专家一次性并行跑完就结束，没有回流环（小字：Cheapest, High False Abstention）。
3. Dynamic（PRIMARY ⭐ 高亮发光边框）：按缺口动态派 1-2 专家 + 确定性 FinalizeGate。
4. Full (Dynamic + Verifier)：在 Dynamic 回路中多插入一个紫色节点 "Independent LLM Verifier"。
```

### 给 ChatGPT 的指令 #3：防泄漏评测机制 + 实战 Bug 修复动画（25 秒）

```text
请生成一个单文件 HTML5 + SVG/JS 动画（1920x1080，深色底 #0F172A，总长 25 秒，带播放/重播控制，画面文字全部用英文）。

前半段 [0-12秒] — Anti-Leakage Evaluation（防泄漏评测）：
- 左侧 "Runtime Sandbox (public/ only)" 和右侧上锁的保险箱 "local_oracles/ (Private Ground Truth)" 中间有一道发光隔离墙 "Zero Runtime Access"。
- 动画演进：Agent 跑完 → 落盘 state.json → 生成一枚带绿色指纹的 "SHA-256 Completion Receipt" → 凭回执离线解锁保险箱打分，并把红标 "Technical Failures" 留在分母框内（标注 "Failure-Inclusive Scoring"）。

后半段 [12-25秒] — Hidden Bug Discovery & Fix（真实排障修复对比）：
- 左右对照动画：
  - BEFORE（红色）：ReviewOutput 触发 `leading_review_consistency` → 被白名单吞成 `$: validation_error` → 模型修复重试继续撞墙 → 8/12 Single & Full slots crash!
  - AFTER（青绿色）：Safe error whitelisted + explicit static repair hint + prompt invariant → 9/9 crashed slots recover → 0/144 format crashes on full DeepSeek run!
```

### 给 ChatGPT 的指令 #4：144 槽位全量 & 跨模型实验数据动态大屏（95 秒）

```text
请帮我写一个单文件 HTML5 + SVG 动态数据大屏（1920x1080，深色学术汇报风 #0F172A，用理大红 #A02337 高亮 Dynamic 主架构，总长 95 秒，支持按键盘 1/2/3 切换场景也支持自动连播）。画面内所有文字用英文，请严格使用以下真实数据，禁止篡改任何数字：

【场景 1 (0-35秒)：Official DeepSeek `deepseek-flash` Hardened Dev36 (144 Slots)】
- 左侧动态柱状图（质量成功率）+ 右侧帕累托散点图（横轴平均 Token 越左越省，纵轴质量越高越好）：
  - Dynamic (Primary ⭐)：31/36 (86.1%)，113,645 avg tokens，56.4s
  - Single：28/36 (77.8%)，197,986 avg tokens，76.5s
  - Full (+Verifier)：27/36 (75.0%)，187,781 avg tokens，67.0s
  - Fixed-4：13/36 (36.1%)，36,478 avg tokens，17.3s
- 弹出三个发光徽章："0 False Resolutions (0/137)"、"-42.6% Tokens vs Single"、"-39.5% Tokens vs Full"、"Dynamic vs Fixed-4: +18 / -0 paired"。

【场景 2 (35-60秒)：Tencent `hy4-flash` Thinking ON vs OFF (24 Slots)】
- 对比进度条动效：
  - Thinking ON (default CoT)：48.0 min wall time | 11/24 (45.8%) completion | 6 wall-clock timeouts (900s) | 7/24 quality
  - Thinking OFF (`thinking: disabled`)：12.6 min wall time (3.8x faster) | 23/24 (95.8%) completion | 0 timeouts | 13/24 quality
- 底部小字结论："Serial multi-round tool loops benefit more from fast exploration than slow per-step CoT."

【场景 3 (60-95秒)：Cross-Model Capability Amplification (`hy4-flash`, Thinking OFF)】
- 四根动态生长柱状图 + Token 对比标注：
  - Single：1/6 (16.7% — 0/5 on identifiable cases!) | 254k tokens | 174s
  - Fixed-4：3/6 (50.0%) | 40k tokens | 28s
  - Dynamic (⭐ 脉冲高亮)：5/6 (83.3%) | 124k tokens (-51%) | 86s (-51%)
  - Full：4/6 (66.7%) | 264k tokens | 146s
- 底部特写框："Cross-Model Discovery: On BOTH DeepSeek & hy4-flash, counterfactual case incident_4035 was missed by Dynamic and rescued by Full (Verifier) -> Motivation for On-Demand Verifier."
```
