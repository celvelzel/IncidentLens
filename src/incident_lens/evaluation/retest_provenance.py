"""Fingerprint retest code/configuration without reading credentials or oracles."""

import hashlib


def retest_snapshot(project):
    paths = [*(project / "src").rglob("*.py"), *(project / "scripts").glob("*.py"),
             *(project / "configs").rglob("*.yaml"), *(project / "configs/wp_d").rglob("*.json"),
             *(project / "prompts").rglob("*.md"), project / "pyproject.toml"]
    for name in ("requirements.lock", "analysis/wp_d/serve_bridge_response.py"):
        if (project / name).is_file():
            paths.append(project / name)
    return {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def snapshot_changes(before, after):
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
