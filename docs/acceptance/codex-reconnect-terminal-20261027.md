# Codex reconnect terminal handling

The subscription transport previously rejected every top-level error event before inspecting terminal completion. It now accepts explicit `Reconnecting... N/M` or `Reconnecting... waiting for network` notices only when followed by exactly one completed turn. Any turn.failed, unknown error, error after completion, missing/duplicate completion, or unexpected tool activity still blocks. Output JSON must still pass the existing schema and domain validation. No additional invocation or transport retry is introduced; underlying HTTP attempts remain unknown.

Every exited CLI process now writes events.json and remote-diagnostic.json before exit-code/event validation. Diagnostics retain event order, bounded fixed error categories and message hashes, without message text, reasoning, agent output or raw stderr. Existing synthetic-only opt-in diagnostics are unchanged. Malformed JSON lines are counted. Original incident3002 results and scores remain unchanged; historical terminal events cannot be reconstructed.

Validation: 35 offline transport/repair tests and 17 parallel-batch tests passed; Ruff and git diff --check passed. Includes recovered completion usage, failed terminal despite output, unknown error, post-completion error, missing/duplicate completion, tool isolation, and persisted redacted failure metadata with diagnostic mode disabled.
