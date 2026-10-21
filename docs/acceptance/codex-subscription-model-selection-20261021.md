# ChatGPT subscription model selection — 2026-10-21

Owner authorized selecting the lowest-cost supported model, superseding the prior exact gpt-6-luna-light pin.

Selected: `gpt-5.6-luna`, reasoning `low`, no fallback. Formal experiments remain disabled.

Local visible model metadata: gpt-6.1-sol, gpt-6-astra, gpt-6-sol, gpt-6-luna, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna. Catalog visibility alone does not prove account entitlement. Astra was not invoked.

Official Standard credit rates per million input/cached-input/output tokens: GPT-6 Luna 2.5/0.25/12.5; GPT-5.6 Luna 5/0.5/30. Source: https://learn.chatgpt.com/docs/pricing . These rates do not establish exact included-subscription debits.

The single gpt-6-luna synthetic invocation was rejected as unavailable for ChatGPT login. Receipt: results/acceptance/codex-subscription-luna-feasibility-20261021/feasibility.json .

The gpt-5.6-luna structured JSON and task ACL schema probes both passed. Receipt: results/acceptance/codex-subscription-5.6-luna-feasibility-20261021/feasibility.json . No incident tools executed, no formal experiments started. Eleven offline contract tests passed. Earlier acceptance documentation is historical and superseded for current model selection by this record and the current config.
