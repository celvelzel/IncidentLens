"""Fingerprint retest code/configuration without reading credentials or oracles."""

import hashlib


def retest_snapshot(project):
    paths = [*(project / "src").rglob("*.py"), *(project / "scripts").glob("*.py"),
             *(project / "configs").rglob("*.yaml"), project / "pyproject.toml"]
    return {str(p.relative_to(project)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def snapshot_changes(before, after):
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
