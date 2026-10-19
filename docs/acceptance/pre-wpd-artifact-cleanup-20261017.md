# WP-D 前产物整理清单

日期：2026-10-17。状态：盘点完成；删除命令被自动审批拦截，未执行删除。

用户已授权跳过本轮 T6 和冻结 T5 重跑，直接由另一个 Agent 执行 WP-D。
该决定是实验准入调整，不将历史失败改为真实调用成功，也不补齐严格 G1a。

## 必须保留

- `results/incidentbench/` 的已验收三例 pilot、数据、锁、协议、真实调用记录。
- `results/v16/live-e2e/` 与 `results/v16/t6-closure/20261016-static-01/t6-real*`：
  保留超时、循环、引用错误等不同失败机制的原始 trace、scope、result、verification、报告和观测目录。
- `results/v16/t6-closure/20261016-static-01/` 中的冻结源码、补丁、来源哈希、readiness、
  审核记录、历史审计、批准协议和测试日志。首次源码漂移失败日志有归因价值，不删除。
- WP-B 验收记录、历史版本验收报告、所有安装 `install-log.json`、smoke 输出、项目文档。
- 实际试验属于推理调查及验收产物；此次未识别到需要删除的训练权重。

## 可删除的重建缓存

以下各目录中的 `environment/`（历史安装验收虚拟环境）和 `wheels/`（构建安装包缓存），
保留其父目录中的安装日志及 smoke 输出。删除前检查无进程使用目标、路径未越界且非重解析目录。

- `results/fresh-clone-final-install/`
- `results/fresh-clone-freeze-install/`
- `results/fresh-clone-install/`
- `results/install-verification-1/`
- `results/v13-eval/20261013-final-install/`
- `results/v13-eval/20261013-fresh-install/`
- `results/v13-eval/20261013-frozen-final-install/`
- `results/v15/final-install-20261014/`
- `results/v15/final-install-20261014-r2/`
- `results/v16/final-qa/20261015-01/clean-install/`
- `results/v16/final-qa/20261015-02/clean-install/`

另可删除 `results/v16/t6-closure/20261016-static-01/dev-pilot-public/`：
这是未采用的 3001/3002/3003 子集副本，原始 `data/incidentbench_v16_dev/` 仍保留。
`dev-pilot-preparation.json` 和旧 draft 保留为选择变更依据，不可作为当前执行协议。

## 执行边界

本轮未运行测试、未发起真实模型请求，未修改实验记录或源码。
清理没有完成：自动审批在命令执行前拦截了递归删除，未返回具体政策理由；不得据此声称空间已释放。
执行 Agent 开始 WP-D 前应从当前源码重新冻结，确认新观测代码及三例选择，勿复用旧源码锁。
