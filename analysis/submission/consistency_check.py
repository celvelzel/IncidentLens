"""Mechanical cross-artifact consistency checks for the COMP5584 submission.

Runs C1-C6 from docs/submission/consistency_check.md and exits non-zero on any
failure. Read-only: it never edits a document.

Usage:
    .venv/Scripts/python.exe analysis/submission/consistency_check.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MARKDOWN = [
    "README.md",
    "docs/README.md",
    "docs/RUN_GUIDE.md",
    "docs/ARCHITECTURE.md",
    "docs/AGENT_DESIGN.md",
    "docs/EVALUATION.md",
    "docs/DEMO_GUIDE.md",
    "docs/LIMITATIONS.md",
    "docs/submission/rubric_alignment.md",
    "docs/submission/source_of_truth.md",
    "docs/submission/consistency_check.md",
    "presentation/Presentation_Script.md",
    "presentation/QA_Preparation.md",
    "submission/SUBMISSION_CHECKLIST.md",
]

BATCH_JSON = (
    ROOT / "results/v16/wp-d/full144-hardened-c4-20261101/final-success-comparison.json"
)

failures: list[str] = []


def fail(check: str, message: str) -> None:
    failures.append(f"{check}: {message}")


def slug(heading: str) -> str:
    """Approximate the anchor GitHub generates for a heading."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return text.replace(" ", "-")


# ---------------------------------------------------------------- C1 links
def check_links() -> None:
    for rel in MARKDOWN:
        path = ROOT / rel
        if not path.exists():
            fail("C1", f"missing document {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = match.group(1)
            if target.startswith(("http", "mailto", "#")):
                continue
            file_part, _, anchor = target.partition("#")
            if not file_part:
                continue
            resolved = path.parent / file_part
            if not resolved.exists():
                fail("C1", f"{rel} -> {target} does not resolve")
                continue
            if anchor and resolved.suffix == ".md":
                headings = re.findall(
                    r"^#+\s+(.*)$", resolved.read_text(encoding="utf-8"), re.M
                )
                anchors = {slug(h) for h in headings}
                if anchor not in anchors:
                    fail("C1", f"{rel} -> {target} anchor not found")


# ---------------------------------------------------------------- C2 markdown
def check_markdown() -> None:
    for rel in MARKDOWN:
        path = ROOT / rel
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()

        fences = sum(1 for line in lines if line.lstrip().startswith("```"))
        if fences % 2:
            fail("C2", f"{rel} has {fences} fence markers (odd)")

        previous_level = 0
        in_fence = False
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            match = re.match(r"^(#+)\s", line)
            if match:
                level = len(match.group(1))
                if previous_level and level > previous_level + 1:
                    fail("C2", f"{rel}:{number} heading skips a level")
                previous_level = level

        # table column counts
        header_cols = None
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("|") and stripped.endswith("|"):
                cols = len([c for c in stripped.split("|")[1:-1]])
                if header_cols is None:
                    header_cols = cols
                elif set(stripped) <= set("|-: "):
                    continue  # separator row
                elif cols != header_cols:
                    fail(
                        "C2",
                        f"{rel}:{number} table has {cols} columns, header has {header_cols}",
                    )
            else:
                header_cols = None


# ---------------------------------------------------------------- C3 numbers
def check_numbers() -> None:
    if not BATCH_JSON.exists():
        fail("C3", f"batch JSON missing at {BATCH_JSON}")
        return
    summary = json.loads(BATCH_JSON.read_text(encoding="utf-8"))
    records = summary["records"]
    variants = summary["summary"]

    completed = sum(1 for r in records if r.get("technical_completion"))
    failures_count = sum(1 for r in records if not r.get("technical_completion"))
    # A wrong root cause is an answered, non-abstained run scored False. A False
    # with abstained=True is an identifiable miss that correctly stayed silent.
    wrong_root = sum(
        1
        for r in records
        if r.get("root_cause_correct") is False and not r.get("abstained")
    )

    expected = {"slots": 144, "completed": 136, "failures": 8, "wrong_root": 0}
    actual = {
        "slots": len(records),
        "completed": completed,
        "failures": failures_count,
        "wrong_root": wrong_root,
    }
    for key, want in expected.items():
        if actual[key] != want:
            fail("C3", f"{key}: batch says {actual[key]}, documents claim {want}")

    if summary.get("batch_elapsed_s") != 16737.6:
        fail("C3", f"batch elapsed is {summary.get('batch_elapsed_s')}, docs claim 16737.6")

    # Quality by variant must match the published table. The summary block keys on
    # the CLI variant id, not on the display label used in the documents.
    published = {"single": 32, "fixed": 22, "dynamic": 33, "full": 30}
    for variant, want in published.items():
        row = next((v for v in variants if v["variant"] == variant), None)
        if row is None:
            fail("C3", f"variant {variant} missing from the batch summary")
            continue
        if row["quality_success"] != want:
            fail(
                "C3",
                f"quality {variant}: batch says {row['quality_success']}, docs claim {want}",
            )

    log = ROOT / "results/pytest-current.log"
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")
        if "1179 passed, 3 skipped" not in text:
            fail("C3", "pytest log no longer records 1179 passed, 3 skipped")
    else:
        fail("C3", "results/pytest-current.log missing")


# ---------------------------------------------------------------- C4 deck
def check_deck() -> None:
    try:
        from pptx import Presentation  # noqa: PLC0415
    except ImportError:
        fail("C4", "python-pptx not installed; cannot inspect the deck")
        return

    deck_path = ROOT / "presentation/IncidentLens_Final.pptx"
    if not deck_path.exists():
        fail("C4", "deck missing")
        return

    prs = Presentation(str(deck_path))
    if len(prs.slides) != 21:
        fail("C4", f"deck has {len(prs.slides)} slides, expected 21")

    script = (ROOT / "presentation/Presentation_Script.md").read_text(encoding="utf-8")
    sections = re.findall(r"^## \d+\.\s+(.+?)\s+—\s+slide\s+(\d+)", script, re.M)
    if len(sections) != 15:
        fail("C4", f"script maps {len(sections)} main-track slides, expected 15")

    for _, number in sections:
        index = int(number) - 1
        if index == 0:
            continue  # the title slide has no content-title textbox by design
        if index >= len(prs.slides):
            fail("C4", f"script references slide {number}, deck is shorter")
            continue
        has_title = False
        for shape in prs.slides[index].shapes:
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text.strip()
            if not text:
                continue
            if abs(shape.left / 914400 - 3.0) < 0.35 and shape.top / 914400 < 1.0:
                has_title = True
        if not has_title:
            fail("C4", f"slide {number} has no content title")


# ---------------------------------------------------------------- C5 timing
def check_timing() -> None:
    try:
        from pptx import Presentation  # noqa: PLC0415
    except ImportError:
        return

    deck_path = ROOT / "presentation/IncidentLens_Final.pptx"
    if not deck_path.exists():
        return

    prs = Presentation(str(deck_path))
    total = 0
    for index, slide in enumerate(prs.slides):
        if index >= 15:
            break
        if not slide.has_notes_slide:
            continue
        text = slide.notes_slide.notes_text_frame.text
        # Notes record the allocation in the header, e.g. "Opening (Speaker 1, 20 s):"
        # or "Speaker 3 (70 s, includes demo):". Only the header is searched so a
        # figure quoted later in the note cannot be mistaken for the timing.
        header = "\n".join(text.strip().splitlines()[:2])
        match = re.search(r"(\d+)\s*(?:s|min)\b", header)
        if not match:
            fail("C5", f"slide {index + 1} has no timing in its speaker-notes header")
            continue
        total += int(match.group(1))

    if not 480 <= total <= 600:
        fail("C5", f"main-track timing totals {total} s, outside 8-10 minutes")
    if total != 597:
        fail("C5", f"main-track timing totals {total} s, script claims 597 s")


# ---------------------------------------------------------------- C6 code
def check_code_contracts() -> None:
    cli = (ROOT / "src/incident_lens/cli.py").read_text(encoding="utf-8")
    if 'default="dynamic"' not in cli:
        fail("C6", "cli.py no longer defaults --variant to dynamic")
    if "Use a fresh output directory" not in cli:
        fail("C6", "cli.py no longer refuses a populated --out directory")

    web_main = (ROOT / "src/incident_lens/web/__main__.py").read_text(encoding="utf-8")
    if "8022" not in web_main:
        fail("C6", "web default port is no longer 8022")

    context = (ROOT / "src/incident_lens/security/context.py").read_text(encoding="utf-8")
    if "ROLE_TOOL_ACL" not in context:
        fail("C6", "ROLE_TOOL_ACL missing from security context")

    provider = (ROOT / "src/incident_lens/tools/provider.py").read_text(encoding="utf-8")
    for name in ("incident.json", "logs.jsonl", "metrics.csv", "changes.jsonl",
                 "configs.jsonl", "database.jsonl"):
        if name not in provider:
            fail("C6", f"PUBLIC_FILES no longer contains {name}")

    app_js = (
        ROOT / "src/incident_lens/web/static/js/app.js"
    ).read_text(encoding="utf-8")
    if "/^\\/evaluation$/" not in app_js:
        fail("C6", "the #/evaluation route is missing from app.js")

    config = (
        ROOT / "src/incident_lens/orchestration/config.py"
    ).read_text(encoding="utf-8")
    if 'runtime.get("max_attempts", 2)' not in config:
        fail("C6", "legacy profile default attempts are no longer 2")


# ---------------------------------------------------------------- main
def main() -> int:
    for check in (
        check_links,
        check_markdown,
        check_numbers,
        check_deck,
        check_timing,
        check_code_contracts,
    ):
        check()

    if failures:
        print(f"FAIL ({len(failures)} defect(s))")
        for line in failures:
            print(f"  {line}")
        return 1

    print("PASS: C1 links, C2 markdown, C3 numbers, C4 deck, C5 timing, C6 code contracts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
