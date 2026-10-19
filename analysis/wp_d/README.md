# WP-D 只读汇总工具

实验结束后的显式替换：输入根目录可提供 `final-selection.json`，以 slot、original_out、selected_out 和 excluded_attempts 指定用户授权的最终结果。冻结 run-order 不改，原运行 ID 不改；替换目标必须有完整 scope/result/verification，且不得越出输入目录。被排除目录即使仍在磁盘也不计入最终行。`selection_basis` 标明口径，`selected_replacement` / `frozen_original_dir` 保留来源。存在替换时请使用 `by_variant_selected_attempts`；旧兼容字段 `by_variant_original_attempts` 此时也表示选定单元，不再代表原始尝试统计。未提供该文件时维持原逻辑。

此目录独立于冻结的 `src/`、`scripts/`、`configs/`、`prompts/` 和数据。
仅用 Python 标准库，不导入项目运行时，不读取 `.env`、API key 或私有 Oracle，不调用网络或工具。
输入目录只读；输出强制位于本目录的 `reports/` 下且必须全新，不能覆盖旧汇总或原始产物。

项目根目录执行一次（不会轮询）：

```powershell
.venv\Scripts\python.exe -B analysis/wp_d/summarize.py results/v16/wp-d/matrix-20261017-01 --out analysis/wp_d/reports/after-pilot-01
```

输出：`summary.json`（逐尝试、原始尝试分组、输入哈希和读取错误）、`attempts.csv`（含人工复核列）、
`summary.md`。CSV 中空值表示未知，JSON 中使用 null。不要将 unknown 求和为零。
运行中读取只是一次非原子快照，部分文件可能尚未写完；完成后使用新输出目录重新生成。
脚本不会持续监测，也不会根据文件缺失判断进程存活。

分类先检查完整性、协议、源码和身份，再区分 runtime_failure、normal_abstention_candidate、
diagnosis_candidate。候选不代表正确；`diagnosis_correct`、`evidence_supported`、
`abstention_appropriate` 留给独立评估/人工复核，不自动接触答案。
超时等事件可能出现在最终成功的调查中，不能仅按 provider_failures 将整次结果判为运行失败。

有 `run-order.json` 时保留所有预定单元（本批预期 12 个）；未列入排期的尝试单独列出，
不自动推断父尝试，不择优替换原记录。汇总分组只统计原排期，额外成本可从所有行另外核算。
没有排期文件时只列已发现产物，不声称矩阵完整。耗时采用 trace 首尾事件差，不等于进程总耗时。
source/protocol 指纹是保存的元数据比较，不代表重新验证磁盘上的冻结源码。
多个不同指纹须复核可比性；缺失指纹也不代表一致。

本批是开发可见 pilot；T6/T5 前置重跑已由用户豁免，严格 G1a 缺口仍保留。
