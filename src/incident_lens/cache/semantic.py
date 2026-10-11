"""Only grounded local explanations may cross the cache boundary."""

import hashlib
import json
import re
from time import perf_counter, time

from incident_lens.agents.service import AnalysisOutput
from incident_lens.cache.policy import CacheNamespace, CachePolicy
from incident_lens.schemas import EvidenceRecord
from incident_lens.security.context import ROLE_TOOL_ACL

from .embeddings import FakeEmbedder, cosine, safe_equivalent
from .store import SQLiteCacheStore

ROLE_TASK_TYPES = {
    "logs": "summarize_log_slice",
    "metrics": "interpret_metric_window",
    "changes": "summarize_change_diff",
}


def canonical_json(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def normalized_question(question):
    return re.sub(r"\s+", " ", question.strip().lower())


class SemanticCacheAdapter:
    def __init__(self, policy: CachePolicy, db_path, dataset_revision: str, embedder=None):
        self.policy = policy.model_copy(deep=True)
        self.dataset_revision = dataset_revision
        self.embedder = embedder or FakeEmbedder()
        self.store = SQLiteCacheStore(db_path)
        self.prompt_version = "roles-v1"
        self.output_schema_version = "schema-v1"
        self.tool_acl_version = "ACLv1"

    def namespace(self, context, task, records, provider):
        task_type = ROLE_TASK_TYPES.get(task.role)
        if task_type is None:
            raise PermissionError("only local investigator explanations are cacheable")
        snapshot = digest(
            {
                "dataset_revision": self.dataset_revision,
                "records": sorted(
                    [record.model_dump(mode="json") for record in records],
                    key=lambda record: record["evidence_id"],
                ),
            }
        )
        model_id = "model-" + digest(str(provider.model_id))
        parameters = getattr(
            provider, "model_parameters", {"temperature": getattr(provider, "temperature", None)}
        )
        return CacheNamespace(
            workspace_id=context.workspace_id,
            incident_id=context.incident_id,
            agent_role=context.role,
            task_type=task_type,
            evidence_snapshot_sha256=snapshot,
            dataset_revision=self.dataset_revision,
            prompt_version=self.prompt_version,
            model_id=model_id,
            model_parameters_hash=digest(parameters),
            output_schema_version=self.output_schema_version,
            tool_acl_version=self.tool_acl_version,
        )

    @staticmethod
    def _authorize(context, task, records, registry):
        observed = registry.observed_ids(context)  # validates server-issued object identity first
        if context.role not in (task.role, "single") or task.role not in ROLE_TASK_TYPES:
            raise PermissionError("task is outside context role")
        if not set(task.allowed_tools).issubset(context.allowed_tools) or not set(
            task.allowed_tools
        ).issubset(ROLE_TOOL_ACL[task.role]):
            raise PermissionError("task tool ACL cannot elevate context")
        actual = {record.evidence_id: record for record in registry.get_observed_records(context)}
        ids = set()
        for record in records:
            if not isinstance(record, EvidenceRecord) or record.evidence_id not in observed:
                raise PermissionError("cache input contains unobserved evidence")
            allowed_sources = {
                "logs": {"logs"},
                "metrics": {"metrics", "topology"},
                "changes": {"changes", "configs"},
            }[task.role]
            if record.source_type not in allowed_sources:
                raise PermissionError("evidence is outside local task role")
            if record.incident_id != context.incident_id or canonical_json(
                record
            ) != canonical_json(actual[record.evidence_id]):
                raise PermissionError("cache input does not match queried evidence")
            if record.evidence_id in ids:
                raise ValueError("duplicate cache evidence")
            ids.add(record.evidence_id)
        return ids

    @staticmethod
    def _ground(output, context, task, ids, *, rebind=False):
        # JSON parsing also detects malformed/mutated cached Pydantic instances.
        result = AnalysisOutput.model_validate_json(
            output if isinstance(output, str) else output.model_dump_json()
        )
        finding = result.finding
        if finding.incident_id != context.incident_id or finding.role != task.role:
            raise ValueError("cached explanation role or incident mismatch")
        citations = finding.evidence_ids + [
            eid
            for hypothesis in result.hypotheses
            for eid in hypothesis.support_ids + hypothesis.against_ids
        ]
        if not set(citations).issubset(ids):
            raise ValueError("explanation cites evidence outside the current snapshot")
        if rebind:
            payload = result.model_dump(mode="json")
            payload["finding"].update(
                finding_id="finding-" + task.task_id,
                task_id=task.task_id,
                run_id=context.run_id,
                incident_id=context.incident_id,
                role=task.role,
            )
            result = AnalysisOutput.model_validate_json(json.dumps(payload))
        elif finding.run_id != context.run_id or finding.task_id != task.task_id:
            raise ValueError("fresh explanation identity mismatch")
        return result

    async def explain(
        self, context, task, records, registry, provider, execute_model_async, emit_callback
    ):
        started = perf_counter()
        ids = self._authorize(context, task, records, registry)
        namespace = self.namespace(context, task, records, provider)
        namespace_json = canonical_json(namespace)
        namespace_digest = digest(namespace)
        task_signature = digest(
            {
                key: value
                for key, value in task.model_dump(mode="json").items()
                if key not in ("task_id", "question")
            }
        )
        exact = normalized_question(task.question)
        details = dict(
            cache_mode=self.policy.mode,
            cache_namespace_digest=namespace_digest,
            agent_role=context.role,
            task_id=task.task_id,
            evidence_snapshot_sha256=namespace.evidence_snapshot_sha256,
            embedding_backend=self.embedder.backend_id,
        )

        def emit(kind, *, reason=None, similarity=None, hit=False, avoided=0):
            emit_callback(
                kind,
                **details,
                cache_similarity=similarity,
                cache_hit=hit,
                cache_validated=hit,
                cache_invalidation_reason=reason,
                cache_lookup_ms=(perf_counter() - started) * 1000,
                llm_calls_avoided=avoided,
            )

        enabled = (
            self.policy.mode != "off"
            and namespace.task_type in self.policy.allowed_task_types
            and bool(ids)
        )
        vector = (
            self.embedder.embed(task.question) if enabled and self.policy.mode == "semantic" else []
        )
        reason = (
            "off"
            if self.policy.mode == "off"
            else "empty_evidence"
            if not ids
            else "not_allowlisted"
            if not enabled
            else "not_found"
        )
        if enabled:
            for row in self.store.candidates(namespace_digest, task_signature):
                if row["namespace_json"] != namespace_json:
                    self.store.delete(row["cache_key"])
                    emit("INVALIDATED", reason="namespace_corrupt")
                    continue
                if (
                    time() - row["created_at"]
                    > min(self.policy.ttl_hours * 3600, row["ttl_seconds"])
                    or row["created_at"] > time()
                ):
                    self.store.delete(row["cache_key"])
                    emit("INVALIDATED", reason="expired")
                    continue
                if self.policy.mode == "exact":
                    similarity = 1.0 if row["exact_question"] == exact else 0.0
                else:
                    if row["embedding_backend"] != self.embedder.backend_id:
                        continue
                    try:
                        similarity = cosine(vector, json.loads(row["vector_json"]))
                    except (ValueError, TypeError):
                        self.store.delete(row["cache_key"])
                        emit("INVALIDATED", reason="invalid_vector")
                        continue
                if similarity < self.policy.similarity_threshold:
                    continue
                if not safe_equivalent(task.question, row["question"]):
                    reason = "safety_guard"
                    continue
                try:
                    if (
                        hashlib.sha256(row["response_json"].encode()).hexdigest()
                        != row["response_sha256"]
                    ):
                        raise ValueError("cached response integrity mismatch")
                    result = self._ground(row["response_json"], context, task, ids, rebind=True)
                    if not result.finding.evidence_ids:
                        raise ValueError("empty cached explanation")
                except (ValueError, TypeError):
                    self.store.delete(row["cache_key"])
                    emit("INVALIDATED", reason="schema_or_grounding", similarity=similarity)
                    continue
                self.store.record_hit(row["cache_key"])
                emit("CACHE_HIT", similarity=similarity, hit=True, avoided=1)
                return result
        emit("CACHE_MISS", reason=reason)
        result = self._ground(await execute_model_async(), context, task, ids)
        # No stale identity can be used if authorization changed during model execution.
        self._authorize(context, task, records, registry)
        if enabled and result.finding.evidence_ids:
            self.store.put(
                cache_key=digest(
                    [namespace_digest, task_signature, exact, self.embedder.backend_id]
                ),
                namespace_digest=namespace_digest,
                namespace_json=namespace_json,
                task_signature=task_signature,
                question=task.question,
                exact_question=exact,
                embedding_backend=self.embedder.backend_id,
                vector=vector,
                response_json=result.model_dump_json(),
                ttl_seconds=self.policy.ttl_hours * 3600,
            )
        return result
