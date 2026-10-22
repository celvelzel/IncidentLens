# 本地 Git 状态与旧工作目录清理记录

日期：2026-10-22。

- 唯一注册工作树为项目根目录，分支 main，跟踪 origin/main；没有其他当前聊天的托管工作树附件。
- 已删除过时本地分支 codex/v14-c、codex/v15-c、feat-switch-deepseek-NMdFdU。未合并历史先保存在 archive/20261022/v14-c、archive/20261022/v15-c、archive/20261022/deepseek-worktree 三个标签中，随本次推送保存。没有删除远端分支。
- 两个已有 stash 保持原样，未 pop、drop 或 clear。
- `.worktrees/v14-clean-checkout` 是独立旧检出仓库，不是已注册 worktree；工作区干净，忽略文件只有缓存和 egg-info。其全部 refs 中有 6 个提交未被主仓库现有 refs 覆盖，已先生成并验证本地 `.git/cleanup-archives/v14-clean-checkout-20261022.bundle`，保留完整历史。该 bundle 仅本地保存，不随源码提交。
- `.worktrees/v14-reproduce-env` 是该旧复现用 Python 3.13.5 虚拟环境。未发现引用这两个目录的 Python 进程。
- 自动审批审查拒绝了两个目录的递归删除命令，返回 blocked by policy，没有更详细原因；未绕过限制。因此这两个忽略目录仍保留，本次磁盘目录清理未完成。
- Trae 模型切换工作树路径 `C:/Users/RickyMa/.trae-cn/worktrees/IncidentLens/feat-switch-deepseek-NMdFdU` 已不存在，Git 中也没有其注册项。

本次不修改历史实验文件、不删除现用 .venv/.env/local_oracles，不启动模型批测。
