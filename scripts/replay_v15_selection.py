"""Replay saved ACTION_SELECTED public snapshots with no model/tool execution."""

import argparse
import json
from pathlib import Path

from incident_lens.evaluation.active_evidence.replay import replay_selection


def trace_events(value):
    if isinstance(value, list):
        events = value
    elif isinstance(value, dict):
        state = value.get("state", value)
        if not isinstance(state, dict) or "events" not in state:
            raise ValueError("trace must contain events or state.events")
        events = state["events"]
    else:
        raise ValueError("unsupported trace envelope")
    if not isinstance(events, list):
        raise ValueError("trace events must be a list")
    return events


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace", required=True, type=Path)
    a = p.parse_args()
    value = json.loads(a.trace.read_bytes())
    events = trace_events(value)
    print(
        json.dumps(
            [
                replay_selection(e["details"])
                for e in events
                if e.get("event_type") == "ACTION_SELECTED"
            ]
        )
    )


if __name__ == "__main__":
    main()
