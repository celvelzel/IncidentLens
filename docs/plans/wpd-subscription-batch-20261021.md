# WP-D ChatGPT 订阅批量入口

接入完成，尚未运行或验证批量实验。通过现有 Python supervisor 自动调度官方 `codex exec`，无需另一个 coding agent 人工驱动。此路径使用 ChatGPT 登录额度，与 Platform API 分开记录，不作为 G1a 直接 API 证据。

固定 `gpt-5.6-luna`、`low` 推理、禁止 API key 回退。订阅批次默认 4 槽并发，`codex-subscription-protocol.json` 的 `jobs` 可设为 1–8；这是本地调度上限，不代表账号服务端并发承诺。Dev10 × 4 个变体，共 40 槽；沿用预算、随机顺序、失败停止、日志、心跳、槽位租约和输出哈希校验。模型权限及账号额度仍由服务端决定。

每槽拥有独立进程、输出目录和租约，每次模型调用拥有独立临时工作目录及临时会话；共用官方登录缓存，不复制或读取凭据。槽内工作流原本允许的并行调用保持不变，因此 `jobs` 限制的是同时运行的案例槽数，不是账号层面的总请求数。出现失败后停止派发新槽，已启动槽继续收尾；不会自动重试整个失败案例。Windows 强制停止会优先终止该 worker 的进程树，以清理其 Codex 子进程。

并发适配仅经静态检查；已补充离线调度测试用例但本次未运行，也未做真实并发调用验证。若服务端限流，仍可能失败并停止派发，需要根据后续证据降低 `jobs`；不宣称限流重试或额度足够已验证。变更 `jobs` 后需准备新的批次目录。

以下仅为后续操作命令，本次未执行。请在项目根目录运行，选择新的输出目录：

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'src')
$P = '.venv/Scripts/python.exe'
$Out = 'results/v16/wp-d/subscription-dev10-UNIQUE'
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/codex-subscription-plan.json --out $Out --prepare

# 以下命令启动真实订阅调用，待单独授权实验时执行。
& $P -B scripts/run_wpd_batch.py --plan configs/wp_d/codex-subscription-plan.json --out $Out --execute
```

`--prepare` 只读取配置、可行性回执和公共数据并冻结输入，不构造 provider、不启动 Codex。启动时需已安装官方 Codex CLI 且已使用 ChatGPT 登录。现有两次合成可行性通过并不代表整批实验已验证。

批次保留 `batch-state.json`、`batch-events.jsonl`、`supervisor-status.json`、每槽 stdout/stderr 和案例工件。写入输出目录的 `STOP_REQUESTED` 文件可请求停止；恢复前移除该文件，再使用相同执行命令追加 `--resume`。中断槽需另加 `--retry-interrupted`，失败槽需另加 `--retry-failed`，均保留旧尝试并新建尝试，不恢复案例内部状态。配置、源代码、公共数据或可行性回执变化时应准备新批次。

温度是否生效、底层 HTTP 次数和实际订阅扣减仍不可验证；保留这些限制。未开启正式实验，不自动提交或推送。
