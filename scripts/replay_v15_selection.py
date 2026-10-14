"""Replay saved ACTION_SELECTED public snapshots with no model/tool execution."""

import argparse
import json
from pathlib import Path

from incident_lens.evaluation.active_evidence.replay import replay_selection


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trace", required=True, type=Path)
    a = p.parse_args()
    value = json.loads(a.trace.read_bytes())
    events = value if isinstance(value, list) else value.get("events", [])
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
