"""Runtime architecture names and their frozen historical aliases.

The primary architecture is ``dynamic``: dynamic specialist selection with
deterministic grounding gates and no independent Verifier. ``full`` is the
ablation control that adds the Verifier review, displayed as
"dynamic (with verifier)".

``dynamic_no_verifier`` is the name used by every saved WP-D batch, trace,
protocol and analysis file before the rename. It is kept as an accepted alias
so historical artifacts keep replaying and re-scoring; it is never written for
new runs.
"""

DYNAMIC = "dynamic"
FULL = "full"
SINGLE = "single"
FIXED = "fixed"

RUNTIME_VARIANTS = (SINGLE, FIXED, DYNAMIC, FULL)

# Historical spellings, in the order they were introduced.
LEGACY_ALIASES = {
    "dynamic_no_verifier": DYNAMIC,
    "no_verifier": DYNAMIC,
}

# ``dynamic`` is the primary architecture; it runs without an independent
# Verifier, which the documentation states explicitly. ``full`` is the ablation
# control and is labelled by contrast with it.
DISPLAY_LABELS = {
    SINGLE: "Single",
    FIXED: "Fixed-4",
    DYNAMIC: "Dynamic",
    FULL: "Dynamic (with verifier)",
}

# Benchmark condition names are a frozen contract: saved protocol.json files
# must still validate, so these never change. Only the runtime alias does.
BENCHMARK_TO_RUNTIME = {
    "strong_single_equivalent_tools": SINGLE,
    "fixed_four_equivalent_tools": FIXED,
    "dynamic_no_verifier": DYNAMIC,
    FULL: FULL,
}


def normalize_variant(name):
    """Return the canonical runtime name, or raise for an unknown variant."""
    if name in RUNTIME_VARIANTS:
        return name
    try:
        return LEGACY_ALIASES[name]
    except KeyError:
        raise ValueError("Unknown variant") from None


def is_known_variant(name):
    return name in RUNTIME_VARIANTS or name in LEGACY_ALIASES


def canonical_name(name):
    """Map a legacy alias to its canonical name, leaving anything else alone.

    Use this when grouping saved rows: an unrecognized variant keeps its own
    group instead of being silently folded into another architecture.
    """
    return LEGACY_ALIASES.get(name, name)


def display_label(name):
    """Label a variant for reports and UI; unknown names pass through.

    A legacy name resolves to the same label as its canonical form. Saved
    artifacts keep their recorded spelling, so callers that display both
    should also show the raw value.
    """
    canonical = LEGACY_ALIASES.get(name, name)
    return DISPLAY_LABELS.get(canonical, str(name))
