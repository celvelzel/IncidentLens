# Codex subscription tool isolation repair — 2026-10-25

The four first attempts on Dev incident_3001 exposed unexpected MCP activity in
Full and Dynamic no verifier. Those attempts remain failures; their artifacts
under results/timing/dev3001-20261025-01 are not rewritten as successful runs.

## Cause and repair

The desktop child-process environment included CODEX_APP_TOOLS_PIPE_PATH and
host session identities. Ignoring config.toml did not isolate that transport.
The installed CLI (0.164.0-alpha.11.1) also bundles gpt-5.6-luna with
tool_mode=code_mode_only. Disabling the older code_mode switch alone did not
prevent exposure of functions.exec, functions.wait and functions.request_user_input.
Disabling the host without changing that local presentation produced a startup
error notice; that intermediate repair was rejected during verification.

The final provider removes desktop tool transport/session identity variables,
disables code_mode_host and other tool features, and explicitly supplies an empty
MCP configuration. It preserves login location, proxy settings and sandbox
environment markers. It derives a per-call catalog from the installed CLI's
local `debug models --bundled` output and changes only tool_mode to direct and
node_repl_disabled to true for the exact selected model. Model identity, bundled
instructions and remaining model metadata are preserved. Missing, ambiguous or
unreadable bundled models fail closed, without model/API fallback.

The local catalog override is a supported CLI setting:
[OpenAI configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
The effective override and disabled tools are recorded in request parameters;
the exact local catalog is retained with each call.

Event validation still rejects every tool event, every error (including startup
error items), and missing/duplicate turn completion. No warning exception is
present in the final implementation. Unexpected behavior in another CLI release
therefore remains a failed call, rather than being silently accepted.

## Validation

- 42 targeted offline tests passed. They cover actual launch arguments/environment, successful
  structured output, rejection of an MCP event even with a valid output file,
  model-metadata preservation, missing-model rejection, proxy/security-marker
  preservation, and batch/bridge integration.
- A live canary asked for available callable tools and invited using a computation
  tool if available. Final output was value=5, available_tools=[]; its complete
  sanitized event stream contained only thread start, turn start, agent message
  and turn completion. No tool/error events occurred. Duration: 15.50 seconds.
- Evidence: results/acceptance/codex-tool-isolation-20261025/direct-canary-result.json.
  Intermediate unsuccessful probes are retained in the same directory.
- Both existing structured JSON and task ACL schema probes passed in
  structured-probes-retry/feasibility.json (19.15s and 14.96s). The first
  structured-probes invocation failed remotely and remains retained; it is not
  counted as a successful first attempt or a tool-isolation failure.

This validates the CLI adapter on the installed version. It is not OS-level
oracle isolation, a rerun of the four investigation variants, or a quality claim.
Any follow-up experiment must use a fresh source lock, feasibility receipt and
output directory; the previous frozen batch cannot be resumed with changed code.
