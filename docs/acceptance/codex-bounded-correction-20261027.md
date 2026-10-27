# Codex structured-output correction and optional query pagination

The subscription adapter previously terminated immediately when a completed CLI response violated a Pydantic domain validator. A coordinator could assign a valid tool to the wrong specialist, pass the JSON Schema shape, and fail local ACL validation before investigation began.

`CodexSubscriptionProvider` now permits one correction by default (`structured_repair_retries=0|1`). Schema/JSON validation failures return fixed, bounded diagnostics and the previous output as untrusted data, retaining the original schema, input and role ACL. Assignment ACL validation has a dedicated error category with an actionable explanation. No invalid task is dispatched, no permissions are widened, and no output is silently trimmed. A second invalid response terminates with the original failure category.

Each physical correction uses the existing request guard, stop checks, token observer and reconciler. Logical-call usage aggregates both physical attempts, including failed output and repair, while retaining incomplete-token accounting. Per-attempt artifacts and a logical-call audit are preserved. Budget denial before a correction does not add a model invocation. Transport failures and unexpected tool activity do not trigger this correction path.

ToolRegistry additionally honors an optional validated `offset` argument and returns a cumulative next cursor. Existing argument models without offset retain their original behavior. New raw telemetry views can use this to retrieve all source rows without treating truncation as an exhausted query.

Offline validation covers ACL error → corrected proposal, repeated invalid output bounded to two physical requests, budget denial retaining first-attempt usage, correction opt-out, safe validator feedback, token/reconciler accounting, existing tool-activity rejection, and complete pagination with observation-ledger isolation. No paid model calls were made. A replay using the historical RCAEval pilot failure exercised the new transport with a scripted correction, not a remote model.

RCAEval-specific evidence inspection and the generic INFO-pattern/raw-row adapter extension are saved outside the production package in `research/rcaeval-pilot-20261026/evidence-audit-20261027` under the parent workspace. The original pilot snapshot and its results remain unchanged; fresh live evaluation must use a new batch with the new configuration recorded.
