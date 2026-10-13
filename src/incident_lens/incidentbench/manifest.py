"""Hash locks and private salted label commitments."""

import hashlib
import json
import os
import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .oracle_store import canonical, safe_path


def digest_tree(root, *, source_only=False):
    root = safe_path(root)
    digest = hashlib.sha256()
    for item in sorted(root.rglob("*")):
        if source_only and ("__pycache__" in item.parts or item.suffix in {".pyc", ".pyo"}):
            continue
        path = safe_path(item)
        if path.is_dir():
            continue
        if not path.is_file():
            raise PermissionError("unsupported resource type")
        digest.update(item.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def create_lock(dataset, protocol):
    base = Path(__file__).resolve().parents[3]
    settings = protocol.model_dump(mode="json") if hasattr(protocol, "model_dump") else protocol
    dependencies = {}
    for package in ("pydantic", "langgraph", "httpx", "PyYAML", "numpy"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    dependency_digest = hashlib.sha256()
    for filename in ("pyproject.toml", "requirements.lock"):
        path = base / filename
        dependency_digest.update(filename.encode() + b"\0")
        dependency_digest.update(safe_path(path).read_bytes() if path.exists() else b"ABSENT")
    return {
        "scripts_sha256": digest_tree(base / "scripts", source_only=True),
        "dependency_lock_sha256": dependency_digest.hexdigest(),
        "python_version": platform.python_version(),
        "installed_dependencies": dependencies,
        "version": 1,
        "sealed": False,
        "public_sha256": digest_tree(dataset),
        "protocol_sha256": hashlib.sha256(canonical(settings)).hexdigest(),
        "source_sha256": digest_tree(base / "src", source_only=True),
        "prompt_sha256": digest_tree(base / "prompts"),
        "config_sha256": digest_tree(base / "configs"),
    }


def verify_lock(lock, dataset, protocol):
    current = create_lock(dataset, protocol)
    if any(lock.get(key) != value for key, value in current.items() if key != "sealed"):
        raise ValueError("benchmark lock drift")
    return True


def label_commitment(oracle_root, salt):
    if len(salt) < 32:
        raise ValueError("private commitment salt must have 32 bytes")
    return hashlib.sha256(digest_tree(oracle_root).encode() + salt).hexdigest()


def check_private_git(oracle_root, repository):
    root = safe_path(oracle_root)
    repo = safe_path(repository)
    if not root.is_relative_to(repo):
        return True
    for path in root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(repo).as_posix()
            tracked = (
                subprocess.run(
                    ["git", "ls-files", "--error-unmatch", "--", relative],
                    cwd=repo,
                    capture_output=True,
                ).returncode
                == 0
            )
            ignored = (
                subprocess.run(
                    ["git", "check-ignore", "-q", "--", relative], cwd=repo, capture_output=True
                ).returncode
                == 0
            )
            if tracked or not ignored:
                raise PermissionError("private labels must be untracked and ignored")
    return True


def seal_dataset(dataset, protocol, oracle_root, salt_path, readiness):
    from .citation_review import validate_truth_reviews
    from .validator import validate_dataset

    if protocol.blindness_level != "independent_label_owner":
        raise ValueError("formal seal requires independent label ownership")
    if (
        not protocol.formal
        or not readiness.get("provider_compatible")
        or not readiness.get("independent_label_owner")
    ):
        raise ValueError("formal seal requires provider readiness and independent label owner")
    audit = validate_dataset(dataset, oracle_root)
    if not audit["ok"]:
        raise ValueError("dataset audit failed")
    metadata = json.loads(safe_path(Path(dataset) / "public_case_index.json").read_bytes())
    if isinstance(metadata, dict):
        metadata = metadata["cases"]
    test_core = [row for row in metadata if row["split"] == "test" and row["cohort"] == "core"]
    if not test_core:
        raise ValueError("formal seal requires nonempty Frozen Test core")
    root = safe_path(oracle_root)
    check_private_git(root, Path(__file__).resolve().parents[3])
    oracle_paths = list(root.rglob("benchmark_oracle.json"))
    if not oracle_paths:
        raise ValueError("formal seal requires reviewed labels")
    for path in oracle_paths:
        oracle = json.loads(safe_path(path).read_bytes())
        review_path = path.with_name("truth_reviews.json")
        if oracle.get("annotator_status") == "pending" or not review_path.exists():
            raise ValueError("formal seal requires authentic double review")
        validate_truth_reviews(oracle, json.loads(safe_path(review_path).read_bytes()))
    salt_path = Path(salt_path).absolute()
    if ".." in salt_path.parts:
        raise PermissionError("unsafe private salt path")
    ancestor = salt_path.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    safe_path(ancestor)
    salt_resolved = salt_path.resolve()
    if salt_resolved.is_relative_to(safe_path(dataset)):
        raise PermissionError("private salt cannot be in public output")
    repository = Path(__file__).resolve().parents[3]
    if salt_resolved.is_relative_to(repository):
        relative = salt_resolved.relative_to(repository).as_posix()
        tracked = (
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", relative],
                cwd=repository,
                capture_output=True,
            ).returncode
            == 0
        )
        ignored = (
            subprocess.run(
                ["git", "check-ignore", "-q", "--", relative],
                cwd=repository,
                capture_output=True,
            ).returncode
            == 0
        )
        if tracked or not ignored:
            raise PermissionError("private salt must be untracked and ignored")
    if not salt_path.exists():
        salt_path.parent.mkdir(parents=True, exist_ok=True)
        with salt_path.open("xb") as stream:
            stream.write(os.urandom(32))
            stream.flush()
            os.fsync(stream.fileno())
    salt = safe_path(salt_path).read_bytes()
    lock = create_lock(dataset, protocol)
    lock.update(
        sealed=True,
        label_commitment=label_commitment(root, salt),
        blindness_level=protocol.blindness_level,
    )
    return lock
