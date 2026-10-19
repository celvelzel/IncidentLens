# WP-D 修复离线验收与冻结记录

2026-10-19，用户授权保存旧版冻结提交、执行离线验收、通过后合入本地主分支并清理修复工作树。

## 最终结果

- 完整离线套件：**1033 passed, 3 skipped，0 failed，0 errors**。
- 跳过项均因 Windows 不允许创建符号链接：祖先路径符号链接、公共工具数据符号链接、可选数据库符号链接。
- Ruff 检查本次修改的 Python 文件通过；`git diff --check` 通过。
- 未执行真实模型调用、连通性测试或真实矩阵补跑。HTTP 故障测试使用 MockTransport。
- 验收进程启用 HTTP 目标 URL 与 socket 两层外网拦截；允许本地回环。单独自检确认本地代理不能绕过目标 URL 检查。最终套件未发生外网尝试。
- 实际导入路径已确认是修复工作树的 `src/incident_lens`，而非复用虚拟环境的旧 editable install。

日志与机器可读记录位于 `results/acceptance/wp-d-repair-offline-20261019/`：

- `offline-suite-final.log`、`offline-suite-final.xml`：最终完整结果。
- `validation.json`：计数、跳过原因、运行路径、测试命令及源码/测试指纹。
- `freeze-validation.json`：冻结标签与归档完整性。
- `network-guard-selftest.json`：离线保护自检。
- 首轮失败和修复后回归日志保留，未覆盖或删除。

## 验收发现与处理

首轮相关检查为 296 passed / 4 failed；首轮完整套件为 1016 passed / 17 failed / 3 skipped。
定位并处理后，受影响的 149 项检查通过，再执行完整套件得到上述最终结果。

1. 新增嵌套用量/Verifier 指标使用普通字典字符串写入 CSV，经过排序 JSON 重载后字节顺序改变，导致 resume 比对失败。统一改用排序 JSON 序列化，新增恢复一致性回归。
2. 新逻辑保留失败响应中合法的 usage；原用例一方面提供 usage，另一方面期待 unknown。现在明确区分有用量和无用量的故障响应，两种场景均保留断言。
3. 原物理计费测试显式关闭业务重试，以隔离被测试的物理请求序列；新的恢复用例独立验证 HTTP 重试，未撤销预算或未知计费检查。
4. 复核完成和最终化之间新增 REVIEW_EFFECT。边界测试改为按实际 REVIEW 的事件 ID 校验，仍禁止插入额外模型调用或协调决策。
5. runner 测试替身补齐新的用量契约，并验证 measured-usage.json 输出。

## 旧版冻结

`wpd-freeze-v1` 是 annotated tag，最终指向 **4010255a70dea28521994dd5788c7ac3bd0db18e**。
旧版源码此前含未提交改动，因此先保存源码快照提交 `6233106`，随后补充归档清单说明；标签不指向新的修复代码。

`results/acceptance/wp-d-freeze-v1/` 包含：

- `source-snapshot.zip`：727 个文件的精确字节归档，避免 Git 文本换行转换影响历史指纹恢复。
- `manifest.json`：逐文件 SHA-256、归档摘要及范围说明。

归档摘要为 `594aabe36a786d596ad553c694887ac3a7d750b94f602d9ba9b0ede4f58b21bd`，727 项逐文件校验均通过。
没有 `.env` 或 `local_oracles`；包含仓库原有的离线样例 ground_truth，以保存离线样例的可复现性。

此版本匹配 slot 4、8、11、12 的 postfix 补跑源码。旧矩阵的其他单元使用更早版本，保留其 scope 和指纹；
不能把标签解释为整个旧矩阵原本就是同版本公平比较。原始 WP-D 运行目录与结果没有重写。

恢复旧版时，在单独目录检出标签，再把该标签附带的 source-snapshot.zip 解压到同一目录，核对 manifest；
不要把旧归档覆盖到已经合入修复的主项目目录。

## 边界

离线验收确认修复与现有回归兼容，不证明真实提供方已经恢复，也不改判 slot 5/9 或其他真实案例。
后续真实实验必须重新冻结新源码、提示词、配置和数据；新旧矩阵分开报告。
