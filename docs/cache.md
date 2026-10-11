# Local explanation cache

`SemanticCacheAdapter(policy, db_path, dataset_revision, embedder=None)` plugs into
`run_investigation(..., cache=adapter)`. Cache mode defaults to off. Architecture
comparisons must run without the cache; measure cache effects separately.

Only logs, metrics and changes local `AnalysisOutput` explanations are cacheable.
Tool planning, Coordinator decisions, Verifier reviews, board state and final
reports always execute normally. Each hit follows real current-run tool queries.
The runtime-issued context, role/task ACL, observed evidence IDs and complete
record contents are checked before lookup. Cached citations must be a subset of
that exact snapshot. Hits rebind finding IDs, task IDs and run IDs to the current
assignment; results still pass the normal merge and report grounding gates.

All eleven `CacheNamespace` fields match exactly before similarity is considered:
workspace, incident, role, task type, snapshot SHA256, dataset revision, prompt
version, model ID, model parameters hash, schema version and ACL version. The
entire task except its ID/question must also match (including filters and expected
discriminator). Maintainers must bump prompt/schema/ACL versions when contracts
change and supply a content-derived dataset revision. The experiment computes it
from public fixture files, without reading private labels.

SQLite uses WAL, per-operation connections, parameterized statements and atomic
upserts/hit counters. Rows retain creation time, TTL and response integrity digest.
Expired, malformed, citation-invalid or modified responses are invalidated. Old
rows without integrity/TTL metadata expire rather than being reused. The digest
checks accidental corruption; it is not authentication against an attacker who
can rewrite both data and digests in the local database.

Semantic mode uses NumPy cosine with threshold >= 0.95 plus a conservative
ordered canonical-token equality guard. Negations, numbers, comparisons and differing
content words reject reuse even when vector similarity is high. This deliberately
misses many legitimate paraphrases. `FakeEmbedder` handles a small documented
synonym vocabulary offline and is a test aid, not a learned semantic model.
`SentenceTransformerBackend` lazily imports the optional `sentence-transformers`
package and defaults to local files only. Install that optional package and model
separately to use it; CI never downloads model weights.

`CACHE_HIT`, `CACHE_MISS` and `INVALIDATED` events use source `cache` and include
similarity, namespace digest, evidence hash, role/task, lookup milliseconds and
avoided model calls. Actual model calls remain `LLM_CALL` events. Cache-off mode
still validates input authority before executing a fresh explanation.

Run from the repository root with its interpreter and source on PYTHONPATH:

```powershell
$env:PYTHONPATH = "$PWD/src"
python -m pytest tests/cache -q
python scripts/run_cache_eval.py --provider mock --out results/cache-experiment
```

The experiment runs off/cold/warm against one case, uses a new SQLite database for
each experiment and exports per-phase trace/result JSON, summary JSON and CSV.
It reports measured calls, hit rate, avoided calls, wall time and tokens when the
provider supplies them. Missing tokens/cost and unreviewed semantic error reuse
rate remain null. Mock results establish offline behavior only. Real mode requires
`LLM_ENDPOINT`, `LLM_API_KEY` and `LLM_MODEL`; credentials are never exported.
Latency includes graph, tools and embedding, so local mock timing cannot predict
real provider savings. Report equality checks deterministic output consistency,
not semantic correctness of every claim.
