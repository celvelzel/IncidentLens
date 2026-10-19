"""Diagnostic storage faults must not replace business failures or suppress retries."""

import ctypes
import json
import os
from types import SimpleNamespace

import pytest

from incident_lens.llm import ProviderError
from incident_lens.orchestration.graph import InvestigationRun
from incident_lens.orchestration.observability import RunJournal
from incident_lens.tools import EvidenceProvider


@pytest.fixture
def journal(tmp_path):
    journal = RunJournal(tmp_path / "journal", {})
    # Deterministic fault injection without heartbeat racing the test.
    journal.stop.set()
    journal.thread.join(timeout=2)
    yield journal
    journal.close()


async def test_permission_error_cannot_replace_provider_timeout_or_prevent_retry(journal, monkeypatch):
    run = InvestigationRun(
        SimpleNamespace(), EvidenceProvider("data"), "incident_001", journal=journal,
    )
    replace = os.replace

    def deny_status(source, target):
        if str(target).endswith("status.json"):
            raise PermissionError("injected file sharing denial")
        return replace(source, target)

    monkeypatch.setattr(os, "replace", deny_status)
    calls = 0

    async def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderError("PROVIDER_TIMEOUT", {})
        return "completed"

    result = await run.retry_transient(run.state, "coordinate-1", "coordinator", "coordinate", operation)
    assert result == "completed" and calls == 2
    assert [r.status for r in run.task_manager.records] == ["FAILED", "COMPLETED"]
    assert journal.health()["degraded"] and journal.health()["events_complete"]
    assert journal.health()["active_io_errors"]["status.json"]["type"] == "PermissionError"
    monkeypatch.setattr(os, "replace", replace)
    run.event(run.state, "DIAGNOSTIC_STORAGE_RECOVERED")
    assert not journal.health()["active_io_errors"]
    saved_health = json.loads((journal.root / "status.json").read_text())["observability"]
    assert saved_health["degraded"] and not saved_health["active_io_errors"]
    events = [json.loads(line) for line in journal.root.joinpath("events-0001.jsonl").read_text().splitlines()]
    assert sum(e["kind"] == "TASK_ASSIGNED" for e in events) == 2


def test_atomic_recovers_short_sharing_conflict(journal, monkeypatch):
    replace = os.replace
    calls = 0

    def transient(source, target):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise PermissionError("injected sharing conflict")
        return replace(source, target)

    monkeypatch.setattr(os, "replace", transient)
    assert journal.atomic("status.json", {"recovered": True})
    assert calls == 3
    saved = json.loads((journal.root / "status.json").read_text())
    assert saved["recovered"] is True
    assert not saved["observability"]["degraded"]
    assert not journal.health()["degraded"]


def test_event_stream_failure_is_nonfatal_but_marks_journal_incomplete(journal, monkeypatch):
    fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("disk failure")))
    assert journal.append("TASK_FAILED", {}) is False
    assert not journal.health()["events_complete"]
    assert journal.sequence == 0
    monkeypatch.setattr(os, "fsync", fsync)
    assert journal.append("LATER_EVENT", {}) is False
    assert journal.atomic("status.json", {"observability": journal.health()})
    assert not json.loads((journal.root / "status.json").read_text())["observability"]["events_complete"]


def test_failed_checkpoint_keeps_last_committed_pointer(journal, monkeypatch):
    run = InvestigationRun(SimpleNamespace(), EvidenceProvider("data"), "incident_001", journal=journal)
    run.event(run.state, "MERGE")
    committed = journal.status["checkpoint"]
    replace = os.replace

    def deny_checkpoint(source, target):
        if "checkpoints" in str(target):
            raise PermissionError("checkpoint locked")
        return replace(source, target)

    monkeypatch.setattr(os, "replace", deny_checkpoint)
    run.event(run.state, "MERGE")
    assert journal.status["checkpoint"] == committed
    assert journal.health()["degraded"]


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics")
def test_real_windows_reader_cannot_abort_task_failed_event(journal):
    from ctypes import wintypes

    run = InvestigationRun(SimpleNamespace(), EvidenceProvider("data"), "incident_001", journal=journal)
    run.task_manager.assign("coordinate-1", "coordinator")
    run.task_manager.start("coordinate-1")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str((journal.root / "status.json").resolve()),
                                0x80000000, 1, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        run.task_manager.fail("coordinate-1", "PROVIDER_TIMEOUT")
        assert run.task_manager.can_retry("coordinate-1")
        run.task_manager.assign("coordinate-1", "coordinator")
        assert journal.health()["degraded"]
    finally:
        kernel.CloseHandle(handle)
