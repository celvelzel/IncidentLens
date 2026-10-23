# CI 可选依赖检测修复 — 2026-10-21

原 PR 检查：[Offline CI #4](https://github.com/celvelzel/IncidentLens/actions/runs/39620527142)。
Linux 和 Windows 的基础 Python 任务各有 5 个失败，均为
`AttributeError: module 'dspy' has no attribute 'Signature'`。
DSPy 专项、Ruff、JavaScript 和 Mock browser 任务已经通过。

基础 Python 任务按设计只安装 `.[dev]`，DSPy 专项安装 `.[dev,dspy]`。
Pytest 收集测试时可将 tests 目录加入导入路径；未安装 SDK 时，`tests/dspy/`
仍能被 Python 作为名为 `dspy` 的 namespace package 导入。因此原
`pytest.importorskip("dspy")` 未跳过优化器测试，却加载不到 SDK 的 Signature。

修复使用 `importlib.metadata.version("dspy")` 检查实际安装的 SDK distribution，
不存在时只跳过依赖该 SDK 的 5 项测试；安装后仍执行四个优化器及标注门槛检查。
DSPy 专项 CI 另显式执行 `from dspy import Signature`，确保 SDK 缺失或损坏时任务失败。
运行时逻辑、测试断言和基础任务的依赖范围均未改变。

验证分别使用干净的基础环境和含 DSPy 的环境，而不是只在后者复跑：

```bash
python -m venv /tmp/incidentlens-core
/tmp/incidentlens-core/bin/pip install -r requirements.lock -e '.[dev]'
INCIDENT_LENS_OFFLINE_TESTS=1 /tmp/incidentlens-core/bin/python -m pytest -q
INCIDENT_LENS_OFFLINE_TESTS=1 .venv/bin/python -m pytest -q tests/dspy
```

基础环境另使用 Node 22，与项目 CI 一致。原 `validation.json` 保留对提交
`61b2c03` 的历史验收记录；此修复只改变可选依赖检测和专项 CI 的安装检查。
