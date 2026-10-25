# HPC 上运行新的 WP-D 40 槽位实验

本指南可直接交给 HPC Agent。新入口在 `hpc/run_wpd.py`，复用原 `scripts/run_wpd_batch.py` 和调查流程，不修改已有代码、提示词、预算、内部重试或本机历史结果。
新模型按用户提供的 `Atria-Dawn` 配置；这是待真实探测验证的 API ID，不能将名称存在等同于接口可用。服务商仍为 Intern InkStone。新结果是独立模型条件，不能直接替换旧 deepseek 批次的失败槽位，也不预设 Full 胜出。

## 1. 拉取独立分支

仓库：`https://github.com/celvelzel/IncidentLens.git`；分支：`codex/hpc-wpd`。

```bash
git clone --single-branch --branch codex/hpc-wpd https://github.com/celvelzel/IncidentLens.git IncidentLens-hpc
cd IncidentLens-hpc
git rev-parse HEAD
```

已有专用但尚未创建实验的 checkout 可运行 `bash hpc/sync.sh /absolute/path/to/IncidentLens-hpc`。脚本只允许正确远端、正确分支、干净目录并快进；存在 `results/hpc-wpd` 时拒绝更新。要获取后续新版本，另建 checkout。**实验 init 后不能 git pull、切分支、改文件或更新依赖**；恢复必须使用同一绝对路径、提交及依赖环境。

## 2. 环境与凭据

需要 Linux、Git、Python 3.11+，建议 Python 3.13，与原运行尽量一致。无需 GPU；计算节点必须可以出站访问 HTTPS 服务商接口。先遵循集群规定加载 Python/module、分区、账户及网络代理；不要绕过网络政策。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
# 使用集群的秘密注入机制，或在交互终端安全输入；不要写入 Git/日志/Slurm 文件。
read -rsp 'API key: ' INCIDENT_LENS_API_KEY; echo
export INCIDENT_LENS_API_KEY
export INCIDENT_LENS_BASE_URL=https://discovery-api.intern-ai.org.cn/v1
export INCIDENT_LENS_MODEL=Atria-Dawn
export INCIDENT_LENS_THINKING=disabled
export RUN_ID=atria-dawn-dev40-$(date -u +%Y%m%dT%H%M%SZ)
export HPC_CHECKOUT="$PWD"
```

不要复制本机 `.env`、results、local_oracles 或私人分析目录。公开 Dev10 数据已经跟随 Git；原先未跟踪的运行记录不应迁移为新实验输入。不要用 `set -x` 或打印环境变量。依赖安装失败时停止并报告，不自行改锁定版本。read 输入方式要求 Bash；作业的密钥导出方式遵循集群安全要求。

## 3. 离线初始化，真实 readiness，准备 40 槽位

```bash
.venv/bin/python hpc/run_wpd.py init --run-id "$RUN_ID" --model Atria-Dawn --jobs 2
.venv/bin/python hpc/run_wpd.py probe --run-id "$RUN_ID"
.venv/bin/python hpc/run_wpd.py prepare --run-id "$RUN_ID"
```

- init 不发请求。新目录为 `results/hpc-wpd/$RUN_ID`；已有目录拒绝覆盖。输入复制自当前版本 API plan/protocol/runtime，只改新模型、protocol ID、外部槽位并发和路径。Dev10 × single/fixed/dynamic_no_verifier/full × 1，共 40 个 slot，随机顺序种子 14100。默认并发 2，可在 init 明确指定 1..8；之后固定。
- 预算保留 8 轮、40 工具、64 请求许可、7200 秒/调查、1200 秒/请求；temperature=0、cache off、json_schema、thinking disabled、既有内部传输退避及结构修复不变。并发 2 不等于 HTTP 并发 2，因为 dispatch 内部可并行。
- probe **会消耗真实 API 请求**，使用同一 provider adapter 与配置验证严格结构化响应。成功才写 readiness，不伪造、不覆盖。失败仅保存脱敏错误类型；停止并报告，不自动循环探测，也不自动切模型/格式/思考参数。成功不保证 40 槽位不再出现 429。
- 如果 `Atria-Dawn` 是展示名而非真实 API ID，应核对服务商控制台后，在新的 run ID 用正确 `--model` 初始化，并同步 INCIDENT_LENS_MODEL；不得修改已冻结输入。若该模型不支持现有协议，应先报告，不私自改协议迁就。
- prepare 只冻结输入、实际依赖版本、端点摘要、readiness 和 40 槽位顺序，不运行调查。确认 manifest 的 order 恰为 40 且全是预期 Dev10 四组。

## 4. 运行或提交 Slurm

先确认集群计算节点可访问 API；readiness 最好在与实际作业相同的网络环境运行。

```bash
# 交互分配的计算节点：
.venv/bin/python hpc/run_wpd.py run --run-id "$RUN_ID"
# 或按集群规则指定 partition/account/QOS；模板默认不申请 GPU：
sbatch --export=ALL hpc/wpd.slurm
```

模板是 **单节点、单 supervisor**，不要对 40 槽位使用 Slurm array、多个 MPI rank 或同时执行两份 supervisor。按集群规范调整模板资源参数应在 init 前完成并提交，或使用 sbatch 命令参数。默认 48 小时只是调度模板；40 调查在并发 2 下的 wall 上界约 40 小时加启动/退出余量，实际时长及费用不保证。若分区时限不足，按恢复流程分段运行。模板默认日志位于被 Git 忽略的 results/。若另选位置，可提交时使用 `--output=/absolute/path/outside/checkout/wpd-%j.out`；不要在 checkout 的其他位置产生未跟踪日志，否则干净目录校验会拒绝恢复。

## 5. 暂停、恢复与失败

```bash
# 请求 supervisor 停止；保留所有记录：
touch "results/hpc-wpd/$RUN_ID/batch/STOP_REQUESTED"
# 确认旧作业和所有 worker 都退出后，移除停止标记：
rm "results/hpc-wpd/$RUN_ID/batch/STOP_REQUESTED"
.venv/bin/python hpc/run_wpd.py resume --run-id "$RUN_ID"
# Slurm 恢复：
HPC_MODE=resume sbatch --export=ALL --output=/absolute/path/outside/checkout/wpd-%j.out hpc/wpd.slurm
```

resume 只跳过已完成项并继续未开始项，不恢复单次调查快照，不自动为失败/中断项创建新 attempt。原 supervisor 会在技术失败后暂停派发，活动项结束后退出非零。**不要看到 429 就循环 resume；先报告并确认服务商恢复。** 若确需补跑失败/中断槽位，另行授权并制定逐槽尝试清单，本入口不开放自动 retry 参数。Slurm 超时可能强制结束进程，远端请求是否已计费可能未知；不能保证零重复费用。

## 6. 汇总与交接

```bash
.venv/bin/python hpc/run_wpd.py summary --run-id "$RUN_ID" > /absolute/path/outside/checkout/summary.json
```

summary 是批次状态清单，不能把 status=completed 当成根因正确。需逐槽核查 verification 的 termination、protocol_valid、source_unchanged、runtime_failure、stop_completion，区分 RESOLVED、INCONCLUSIVE、技术失败以及未运行/中断。保存整个会话目录、Slurm 日志、提交 SHA、Python/依赖版本、模型 ID、并发、readiness、batch-manifest、batch-state、events、每槽 trace/result/report/verification/measured-usage。token 未完整返回时报告实测下界，不估算成完整费用。

Agent 交付中文报告：40 槽位覆盖情况、四组结果矩阵、失败阶段和脱敏错误码、请求/token 及未知量、冻结校验、剩余 worker、是否具备实验设计要求的完整性。语义正确性仍需既有评估流程与独立标签，不在 runtime 引入 local_oracles。新模型/HPC 与原模型/本机结果独立报告，不能声称严格受控的模型因果提升。

本提交仅提供离线验证过的入口；未在真实 HPC/Slurm 或 Atria-Dawn 上执行。不要将离线测试当作服务商能力或实验完成证据。
