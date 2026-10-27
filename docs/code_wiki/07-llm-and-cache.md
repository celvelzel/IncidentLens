# 07 · LLM 抽象、结构化输出与语义缓存

相关代码：[`llm/`](../../src/incident_lens/llm)、[`cache/`](../../src/incident_lens/cache)。

## 1. Provider 抽象

```python
class LLMProvider(ABC):
    model_id = "unknown"
    temperature = 0.0
    request_guard = None      # 运行时注入：申请物理请求许可
    token_observer = None     # 运行时注入：观察 token

    @abstractmethod
    async def structured_call(self, role, system_prompt, user_payload, output_model):
        """返回已校验的模型对象 + measured usage"""
```

`json_payload(value)` 递归把 Pydantic/嵌套结构转为 JSON 兼容 dict，所有 Provider 共用。

### 1.1 三种实现

| 实现 | model_id | 用途 |
| --- | --- | --- |
| `MockProvider` | `deterministic-public-policy-v1` | 离线确定性回归 |
| `RealChatProvider` | 用户配置 | OpenAI 兼容 `/chat/completions` |
| `CodexSubscriptionProvider` | Codex CLI | 通过本机 `codex` CLI 订阅调用 |

**永不自动回退**：`real` 失败不会静默切到 Mock；缺失配置直接 `PROVIDER_CONFIGURATION_REQUIRED`。

## 2. `RealChatProvider`（[`provider.py`](../../src/incident_lens/llm/provider.py) L51）

### 2.1 构造与校验

必填：`endpoint`、`api_key`、`model`。

校验：

- endpoint 必须是绝对 HTTP(S) URL；
- `structured_repair_retries ∈ {0,1}`；
- `response_format_mode ∈ {json_schema, json_object}`；
- `thinking ∈ {None, enabled, disabled}`；
- `temperature` 有限，`timeout > 0`。

特殊行为：`genai.comp.polyu.edu.hk` 不使用系统代理（`_trust_env=False`），其余 endpoint 保留代理环境变量。

### 2.2 两条调用路径

```python
async def structured_call(...):
    if self.recovery.enabled:
        return await self._reliable_call(...)
    return await self._legacy_call(...)
```

| 路径 | 特点 |
| --- | --- |
| `_legacy_call` | 直接 POST；解析 → 校验 → 可选一次结构化修复；usage 归一 |
| `_reliable_call` | 逻辑 call_id、permit 申请/对账、失败分类、传输重试、修复预算、STOP guard、预算快照 |

### 2.3 `model_parameters`（缓存与实验指纹）

```python
{
  "temperature", "response_format", "thinking",
  "structured_repair_retries", "request_timeout_seconds",
  "provider_recovery", "targeted_structured_repair",
  "capability_profile"
}
```

该 dict 会被 `SemanticCache` 哈希进命名空间，任何参数变化都会导致缓存失效。

## 3. 结构化输出（[`structured_output.py`](../../src/incident_lens/llm/structured_output.py)）

### 3.1 `output_messages(system_prompt, user_payload, schema)`

生成**单一**结构化提示：

- 明确要求只输出 JSON；
- 把 JSON Schema 作为约束嵌入；
- 用户 payload 以 JSON 文本传入；
- 不暴露思维链或秘密。

### 3.2 `strict_schema(output_model)`

把 Pydantic JSON Schema 转成严格模式：

- 所有 object 的 `additionalProperties = False`；
- `_require_all_properties` 递归确保 required 覆盖所有属性；
- 适配 `$defs` / `anyOf` / 数组。

### 3.3 `validate_response(data, output_model)`

1. 校验响应 envelope（choices/message/content）；
2. `json.loads`；
3. `output_model.model_validate`；
4. 失败抛 `StructuredOutputError`，包含 `category`、`phase`、安全的 schema 路径。

`StructuredOutputError` 的分类：

`INVALID_JSON`、`SCHEMA_VALIDATION_FAILED`、`DOMAIN_VALIDATION_FAILED`、`RESPONSE_TRUNCATED`。

### 3.4 `repair_message(error)`

只给出错误路径与期望类型，**不回显模型原文**，避免把注入内容再喂回去。修复调用最多 1 次；`targeted_structured_repair=True` 时只发送失败字段路径。

## 4. 错误分类（[`errors.py`](../../src/incident_lens/llm/errors.py)）

### 4.1 `FailureCategory`

`RATE_LIMITED`、`TRANSIENT_SERVER_ERROR`、`TRANSPORT_TIMEOUT`、`NETWORK_UNAVAILABLE`、`AUTHENTICATION_FAILED`、`INVALID_REQUEST`、`UNSUPPORTED_RESPONSE_FORMAT`、`INVALID_JSON`、`SCHEMA_VALIDATION_FAILED`、`DOMAIN_VALIDATION_FAILED`、`RESPONSE_TRUNCATED`、`CANCELLED`、`REQUEST_BUDGET_EXHAUSTED`、`WALL_BUDGET_EXHAUSTED`、`TOKEN_BUDGET_EXHAUSTED`、`UNKNOWN_PROVIDER_ERROR`、`QUOTA_EXHAUSTED`。

### 4.2 `classify_http`

| 状态 | 分类 | 可重试 |
| --- | --- | --- |
| 429 | `RATE_LIMITED` | 是（但 `insufficient_quota` → `QUOTA_EXHAUSTED` 否） |
| 408 | `TRANSPORT_TIMEOUT` | 是 |
| 500/502/503/504 | `TRANSIENT_SERVER_ERROR` | 是 |
| 401/403 | `AUTHENTICATION_FAILED` | 否 |
| 其他 4xx | `INVALID_REQUEST` | 否 |

`Retry-After` 支持秒数与 HTTP-date，上限 86400 秒。

安全约束：

- **绝不读取 response body 做分类**；
- `provider_error_code` 只保留 `SAFE_ERROR_CODES` 白名单中的精确代码；
- 不把原始错误文本写入 trace。

### 4.3 `classify_transport`

- `asyncio.CancelledError` → `CANCELLED`（phase=`cancel`，由调用方传播）；
- `httpx.TimeoutException` → `TRANSPORT_TIMEOUT`；
- `httpx.NetworkError` → `NETWORK_UNAVAILABLE`。

## 5. 恢复策略（[`orchestration/recovery.py`](../../src/incident_lens/orchestration/recovery.py)）

### 5.1 `RecoveryConfig`

| 字段 | 默认 |
| --- | --- |
| `enabled` | `False` |
| `max_transport_retries` | 2 |
| `max_structured_repairs` | 1 |
| `max_physical_attempts_per_call` | 4 |
| `initial_backoff_seconds` | 0.5 |
| `max_backoff_seconds` | 4.0 |
| `jitter_mode` | `none`（`seeded` / `full`） |
| `retry_http_statuses` | `[408, 429, 500, 502, 503, 504]` |
| `reserve_verifier_requests` | 0 |
| `min_request_time_seconds` | 5.0 |
| `safety_margin_seconds` | 0.0 |
| `format_capability` | `json_object` |

### 5.2 `decide_http_retry`

判定顺序（任一失败即 `FAIL`）：

1. STOP 或 `CANCELLED` → `ABORT_STOP`；
2. recovery 关闭 → `recovery_disabled`；
3. 分类不可重试 → `non_retryable_failure`；
4. HTTP 状态不在白名单 → `http_status_not_enabled`；
5. 传输重试次数超限；
6. 物理尝试次数超限；
7. 剩余 permit ≤ `reserve_verifier_requests`；
8. stage 预算或 token 预算为 0；
9. 退避 + 最小请求时间 + 安全边际 > 剩余 wall clock。

通过则 `RETRY_HTTP`，延迟 = `min(max_backoff, initial * 2^attempt)`，并取 `max(delay, Retry-After)`。

`RecoveryDecision` 固定包含 `action`、`reason`、`delay_seconds`、剩余 permit/秒数，便于 trace 解释。

## 6. 传输退避（[`transport_retry.py`](../../src/incident_lens/llm/transport_retry.py)）

`compute_backoff(attempt, retry_after, config, rng)`：

- 指数：`initial * 2^attempt`，封顶 `max_backoff`；
- jitter：`none` / `seeded`（可复现随机）/ `full`（全抖动）；
- 最终 `max(delay, retry_after or 0)`。

## 7. Usage 记账（[`usage.py`](../../src/incident_lens/llm/usage.py)）

| 函数 | 作用 |
| --- | --- |
| `token_value(value)` | 把 `None`/非法值安全转成 0 或保留 |
| `normalize_usage(value)` | 兼容 `prompt_tokens` / `input_tokens` 等字段命名 |
| `begin_request(usage)` | 物理请求开始，累加 `actual_http_requests` |
| `record_usage(usage, reported)` | 记录单次响应 token |
| `refresh_usage(usage)` | 重算 total / measured_total / `tokens_complete` |
| `aggregate_usage(calls)` | 跨调用聚合 |

usage 的 `source ∈ {model, cache, mock}`，`llm_calls` 是逻辑调用数，`actual_http_requests` 是物理请求数。两者分开才能区分重试成本。

## 8. Codex 订阅 Provider（[`codex_subscription.py`](../../src/incident_lens/llm/codex_subscription.py)）

- `resolve_cli` 在 PATH/常见安装位置查找 `codex`；
- `inspect_auth` 检查登录状态，不读取/输出 token；
- 在隔离临时目录执行 CLI，传入结构化 schema；
- `decode_events` 解析 NDJSON 事件流，提取最终 JSON 与 usage；
- `safe_diagnostic` 只保留白名单诊断字段；
- 失败信息走统一的 `FailureInfo`。

## 9. 语义缓存（[`cache/`](../../src/incident_lens/cache)）

### 9.1 定位

缓存**只允许调查者的局部解释**跨请求复用。可缓存的 `task_type`：

```text
summarize_log_slice
interpret_metric_window
summarize_change_diff
interpret_database_window
```

角色提示映射：`logs→summarize_log_slice`、`metrics→interpret_metric_window`、`changes→summarize_change_diff`、`database→interpret_database_window`。`single` 上下文可代表这四个角色；其他角色直接 `PermissionError`。

`_authorize` 还会检查每条记录的 `source_type` 是否属于该角色的本地域（metrics 在拥有 DB 工具时额外允许 `database`，logs 只允许 `logs` 等）。

### 9.2 三种模式

| 模式 | 行为 |
| --- | --- |
| `off` | 不查不写 |
| `exact` | 题目归一化后精确匹配，相似度 1.0 |
| `semantic` | 嵌入 + 余弦相似度，阈值 ≥ 0.95 |

`CachePolicy`：

```python
mode="off"
similarity_threshold=0.95   # 只允许 0.95..1.0
ttl_hours=24.0
allowed_task_types=四类
```

### 9.3 命名空间

`CacheNamespace` 包含：

`workspace_id`、`incident_id`、`agent_role`、`task_type`、`evidence_snapshot_sha256`、`dataset_revision`、`prompt_version`、`model_id`、`model_parameters_hash`、`output_schema_version`、`tool_acl_version`。

因此以下任一变化都会 miss：

- 证据内容或数据集版本；
- prompt 版本（`roles-v12-...`）；
- 模型 ID / 温度 / response format / 重试配置；
- 输出 schema 版本；
- ACL 版本；
- 角色或任务类型。

### 9.4 命中流程（`SemanticCacheAdapter.explain`）

```text
1. _authorize：context 必须是 Registry 签发；task.role 必须匹配；
   allowed_tools 不能越权；records 必须全部来自该 context 的 observed ledger，
   且内容逐字节等于账本记录（防止改动过的对象）。
2. namespace：证据快照 + 数据集 + prompt + 模型参数 + schema + ACL → SHA-256。
3. task_signature：task 去掉 task_id/question 后的哈希，避免不同措辞串用。
4. enabled = mode != off ∧ task_type 白名单 ∧ ids 非空。
5. 遍历 store.candidates(namespace_digest, task_signature)：
   - namespace_json 不一致 → 删除，INVALIDATED(namespace_corrupt)
   - 超 TTL 或未来时间 → 删除，INVALIDATED(expired)
   - embedding_backend 不一致 → 跳过（不删除）
   - 向量损坏 → 删除，INVALIDATED(invalid_vector)
   - exact：question 归一化相等 → 1.0；semantic：余弦相似度
   - 相似度 < 阈值 → 跳过
   - safe_equivalent(question, cached_question) 失败 → 继续，最终 miss 原因记 safety_guard
   - 响应 SHA-256 完整性校验
   - _ground(rebind=True)：反序列化 AnalysisOutput，校验 incident/role/引用 ⊆ 本次 ids，
     并把 finding_id/task_id/run_id 重绑到当前任务
   - 空引用结果视为无效 → 删除，INVALIDATED(schema_or_grounding)
   - record_hit → CACHE_HIT
6. 未命中 → 调用模型 → _ground（严格身份匹配）→ 再次 _authorize（模型执行期间授权可能变化）
   → 若结果有引用则写入缓存。
```

### 9.5 防投毒措施

| 风险 | 对策 |
| --- | --- |
| 缓存未观测证据 | `_authorize` 要求 ⊆ observed ledger，且内容一致 |
| 跨角色/跨任务复用 | namespace 含 role/task_type/task_signature |
| 过期/时钟回拨 | TTL + `created_at > now` 判为失效 |
| 嵌入后端漂移 | `embedding_backend` 必须一致 |
| 响应被篡改 | `response_sha256` 完整性校验 |
| 语义近似但语义反转 | `safe_equivalent` 安全检查 + 高阈值 |
| 缓存解释引用旧证据 | `_ground` 要求引用 ⊆ 当前 ids，否则失效 |
| 模型执行期间权限变化 | 写入前再次 `_authorize` |

### 9.6 存储（[`store.py`](../../src/incident_lens/cache/store.py)）

SQLite 表 `cache_entries`：

`cache_key`（PK）、`namespace_digest`、`namespace_json`、`task_signature`、`question`、`exact_question`、`embedding_backend`、`vector_json`、`response_json`、`response_sha256`、`created_at`、`ttl_seconds`、`hits`。

方法：`candidates(namespace_digest, task_signature)`、`put(...)`、`record_hit(key)`、`delete(key)`、`close()`。默认数据库路径由 CLI/Web 指定（`--cache-db`）。

### 9.7 嵌入后端（[`embeddings.py`](../../src/incident_lens/cache/embeddings.py)）

- `tokenize`：小写、去标点、规范化空白；
- `safe_equivalent`：阻止否定/数值/时间方向被语义相似掩盖（例如 "not"、"no"、数字、`before/after`）；
- `FakeEmbedder`：确定性哈希向量，零依赖，用于测试/离线；
- `SentenceTransformerBackend`：懒加载，仅在需要时导入重依赖；
- `cosine`：纯 Python 实现。

### 9.8 缓存事件

`CACHE_HIT` / `CACHE_MISS` / `INVALIDATED`，details 包含：

`cache_mode`、`cache_namespace_digest`、`agent_role`、`task_id`、`evidence_snapshot_sha256`、`embedding_backend`、`cache_similarity`、`cache_validated`、`cache_invalidation_reason`、`cache_lookup_ms`、`llm_calls_avoided`。

这些字段让评估可以精确统计缓存收益与失效原因。

## 10. 常见排错

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `PROVIDER_CONFIGURATION_REQUIRED` | 缺 endpoint/api_key/model | 配置 `.env`，不要期待 Mock 回退 |
| 一直 `UNSUPPORTED_RESPONSE_FORMAT` | 模型不支持 json_schema | 用 `--response-format json_object` |
| `Structured repair exhausted LLM budget` | 修复次数耗尽 LLM 预算 | 提高 `--max-llm-calls` 或修 schema |
| 缓存始终 miss | prompt/model/ACL/证据版本变化 | 查看 `cache_namespace_digest` |
| `CACHE_HIT` 但结果异常 | 不应发生；检查 `cache_validated` | 删除缓存库重跑 |
