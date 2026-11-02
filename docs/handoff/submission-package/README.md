# 提交材料交接包（Submission Package Handoff）

**日期**：2026-11-02　**用途**：把 COMP5584 小组提交所需的全部演示与讲稿材料集中放在交接文件夹，方便未参与制作的成员直接取用。

> 这里是**发布副本**。编辑请改 `presentation/`、`docs/`、`submission/` 下的源文件后重新复制；
> 幻灯片由 `presentation/build_deck.py` 一键生成，不要手改 `.pptx`。

## 内容清单

| 文件 | 用途 |
| --- | --- |
| `IncidentLens_Deck.pptx` | 21 页 16:9 **可编辑**幻灯片（主线 15 页 + 备份 6 页），每页含演讲者备注 |
| `IncidentLens_Deck.pdf` | 幻灯片的 PDF 导出（917,076 字节），现场机器缺字体时的后备 |
| `Presentation_Script.md` | 英文逐页讲稿 + 中文演讲者备注、计时、转场、演示提示；六人分配，总时长 9:57 |
| `QA_Preparation.md` | 10 个预答问题、快速应答表、记忆数字表、Mock 演练 |
| `RUN_GUIDE.md` | `docs/RUN_GUIDE.md` 的副本：安装、全部命令、变体、预算、replay、测试、故障排查 |
| `SUBMISSION_CHECKLIST.md` | 提交清单：课程要求核对、打包规则、临交前十分钟检查 |
| `Individual_Contribution_Statement.md` | 贡献声明：成员 1–2（YANG Ziting、MA Jiyuan）的职责已填入，百分比与成员 3–6 行由小组补齐后导出 PDF |

## 前端演示网站：启动方式与代码目录

**代码目录**：`src/incident_lens/web/`
- `__main__.py` — Starlette 服务入口（默认端口 8022）
- `static/` — 前端资源（原生 JavaScript ES modules + hash 路由 SPA，中文界面）
  - `static/js/app.js` — 路由与页面壳（6 条路由：总览 / 新建调查 / 痕迹档案库 / 运行详情 / 系统设计 / 评估结果）
  - `static/js/replay-panels.js` — 运行详情/replay 面板：时间线、假设看板、证据登记、FinalizeGate 时间线
  - `static/js/knowledge.js` — 评估视图的静态快照数据（标注 RECORDED BATCH）

**启动**（仓库根目录，已装好 `.venv` 时）：

```bash
.venv/Scripts/python.exe -m incident_lens.cli web --port 8022
```

然后浏览器打开 `http://127.0.0.1:8022`。健康检查：`http://127.0.0.1:8022/api/health`。

**演示预跑**（现场演示前先跑好，跑入新目录避免覆盖）：

```bash
.venv/Scripts/python.exe -m incident_lens.cli run --case incident_001 --provider mock --variant dynamic --cache-mode off --out results/demo-live
.venv/Scripts/python.exe -m incident_lens.cli run --case incident_006 --provider mock --variant dynamic --cache-mode off --out results/demo-abs
```

`incident_001` 应 `RESOLVED`、`incident_006` 应 `INCONCLUSIVE`；详尽流程、备用方案与录制规范见 `RUN_GUIDE.md` 与 `docs/DEMO_GUIDE.md`。

演示用的已入库 trace（可作 Recorded Replay）：`results/acceptance/demo-live-20261102/trace.json`（与幻灯片第 9 页截图同一条 trace）、`results/acceptance/demo001/`、`results/acceptance/demo006/`。

## 核对基线

- 幻灯片：2026-11-02 由 `presentation/build_deck.py` 构建，PDF 经 WPS 导出，21 页全部渲染并目检（第 01/04/06/08/09/19 页逐张检查）。
- 测试：2026-11-02 全量 pytest `1179 passed, 3 skipped, 0 failed`（463.23 s，exit 0）。
- 一致性审计：`analysis/submission/consistency_check.py` → PASS（C1–C6）。
