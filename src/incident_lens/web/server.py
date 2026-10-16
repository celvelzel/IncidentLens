"""REST API and static SPA dashboard; never reads evaluation truth."""

import json
import logging
import os
import stat
import time
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from incident_lens.artifacts import load_replay, save_run
from incident_lens.llm.config import provider_options
from incident_lens.orchestration.report import render_report
from incident_lens.schemas.workflow import WorkflowOptions
from incident_lens.security.context import ROLE_TOOL_ACL

ROOT = Path(__file__).resolve().parents[3]
RESULTS_ROOT = (ROOT / "results").resolve()
STATIC_DIR = Path(__file__).resolve().parent / "static"

logger = logging.getLogger("incident_lens.web")
load_dotenv(ROOT / ".env")

_trace_cache: dict[tuple[str, int], dict] = {}


def error_response(code, message, status=400):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _evidence_provider():
    from incident_lens.tools import EvidenceProvider

    return EvidenceProvider(ROOT / "data")


def _resolve_trace_path(rel):
    """Resolve a client-supplied trace path strictly inside the results tree."""
    raw = Path(rel)
    candidate = raw if raw.is_absolute() else ROOT / rel
    candidate = candidate.resolve()
    if not candidate.is_relative_to(RESULTS_ROOT):
        raise PermissionError("path escapes the results directory")
    if candidate.name != "trace.json":
        raise PermissionError("only trace.json files are accessible")
    return candidate


def _resolve_download_file(path):
    """Reject links/reparse points in downloads, including every ancestor."""
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if part.is_symlink() or (
            getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise PermissionError("linked artifacts cannot be downloaded")
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(RESULTS_ROOT.resolve()):
        raise PermissionError("artifact escapes results directory")
    return resolved


def _trace_summary(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (str(path), stat.st_mtime_ns)
    cached = _trace_cache.get(key)
    if cached is not None:
        return cached
    try:
        trace = json.loads(path.read_text(encoding="utf-8-sig"))
        state = trace.get("state") or {}
        report = state.get("report") or {}
        summary = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "incident_id": state.get("incident_id"),
            "run_id": state.get("run_id"),
            "provider": trace.get("provider"),
            "variant": trace.get("variant"),
            "cache_mode": trace.get("cache_mode"),
            "status": report.get("status"),
            "rounds": state.get("round_index"),
            "tool_calls_used": state.get("tool_calls_used"),
            "llm_calls_used": state.get("llm_calls_used"),
            "elapsed_ms": trace.get("elapsed_ms"),
            "modified_at": stat.st_mtime,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None
    _trace_cache[key] = summary
    return summary


def _list_trace_summaries():
    summaries = []
    seen = set()
    if RESULTS_ROOT.exists():
        for path in RESULTS_ROOT.rglob("trace.json"):
            summary = _trace_summary(path)
            if summary is None:
                continue
            summaries.append(summary)
            seen.add((str(path), path.stat().st_mtime_ns))
    for key in [k for k in _trace_cache if k not in seen]:
        _trace_cache.pop(key, None)
    summaries.sort(key=lambda item: item["modified_at"], reverse=True)
    return summaries


class RunRequest(BaseModel):
    incident_id: str = Field(pattern=r"^incident_[0-9]{3,}$")
    provider: Literal["mock", "real"] = "mock"
    cache_mode: Literal["off", "exact", "semantic"] = "off"
    response_format: Literal["json_schema", "json_object"] | None = None
    thinking: Literal["enabled", "disabled"] | None = None
    timeout: float | None = Field(default=None, ge=1.0)
    workflow: WorkflowOptions = Field(default_factory=WorkflowOptions)


class ReplayRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


async def api_health(request):
    return JSONResponse({"ok": True})


async def api_meta(request):
    config = {}
    config_path = ROOT / "configs/system.yaml"
    try:
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = loaded
    except (OSError, ValueError):
        logger.warning("system config unreadable; using schema defaults")
    budget = {
        "max_rounds": config.get("max_rounds", 4),
        "max_tool_calls": config.get("tool_calls_limit", 12),
        "max_llm_calls": config.get("llm_calls_limit", 16),
        "max_wall_seconds": config.get("time_limit_seconds", 600),
    }
    provider_defaults = None
    provider_settings_error = None
    try:
        defaults = provider_options()
        if defaults["response_format_mode"] not in ("json_schema", "json_object"):
            raise ValueError("invalid response format")
        if defaults["thinking"] not in (None, "enabled", "disabled"):
            raise ValueError("invalid thinking mode")
        if not 1 <= defaults["timeout"] < float("inf"):
            raise ValueError("invalid request timeout")
        provider_defaults = defaults
    except ValueError:
        provider_settings_error = "Invalid project-local provider request settings"
    return JSONResponse(
        {
            "budget": budget,
            "acl": {role: list(tools) for role, tools in ROLE_TOOL_ACL.items()},
            "provider_defaults": provider_defaults,
            "provider_settings_error": provider_settings_error,
        }
    )


async def api_cases(request):
    try:
        cases = _evidence_provider().list_cases()
    except (OSError, ValueError, PermissionError) as exc:
        logger.error("case listing failed: %s", exc)
        return error_response("data_error", "Public evidence cannot be loaded", status=500)
    return JSONResponse([case.model_dump(mode="json") for case in cases])


async def api_run(request):
    try:
        payload = RunRequest.model_validate(await request.json())
    except (ValidationError, json.JSONDecodeError) as exc:
        return error_response("invalid_request", str(exc))

    from incident_lens.llm.mock import MockProvider
    from incident_lens.llm.provider import ProviderError, RealChatProvider
    from incident_lens.orchestration.graph import run_investigation

    try:
        if payload.provider == "mock":
            model = MockProvider()
        else:
            options = provider_options(payload.response_format, payload.thinking, payload.timeout)
            model = RealChatProvider(
                os.getenv("INCIDENT_LENS_BASE_URL"),
                os.getenv("INCIDENT_LENS_API_KEY"),
                os.getenv("INCIDENT_LENS_MODEL"),
                **options,
            )
        cache = None
        if payload.cache_mode != "off":
            from incident_lens.cache.policy import CachePolicy
            from incident_lens.cache.semantic import SemanticCacheAdapter

            cache = SemanticCacheAdapter(
                CachePolicy(mode=payload.cache_mode),
                ROOT / "results/ui-cache.sqlite",
                _evidence_provider().dataset_revision,
            )
        started = time.monotonic()
        from incident_lens.schemas import Budget

        limits = (
            Budget(max_llm_calls=24, max_tool_calls=24, max_rounds=6)
            if payload.workflow.profile == "incident_response"
            else None
        )
        state = await run_investigation(
            payload.incident_id,
            model,
            ROOT / "data",
            budget=limits,
            cache=cache,
            workflow=payload.workflow,
        )
        output_dir = RESULTS_ROOT / "ui" / state.run_id
        trace = save_run(
            state,
            output_dir,
            payload.provider,
            cache_mode=payload.cache_mode,
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
    except ProviderError as exc:
        logger.warning("provider error during run: %s", exc.code)
        return error_response(exc.code, "Provider request failed", status=502)
    except (ValueError, OSError) as exc:
        logger.error("run failed: %s: %s", type(exc).__name__, exc)
        return error_response("run_failed", "Configuration or data error", status=500)
    return JSONResponse(
        {
            "trace": trace,
            "report_md": render_report(state.report),
            "path": str((output_dir / "trace.json").relative_to(ROOT)).replace("\\", "/"),
            "recorded": False,
        }
    )


async def api_traces(request):
    return JSONResponse(_list_trace_summaries())


async def api_replay(request):
    try:
        payload = ReplayRequest.model_validate(await request.json())
    except (ValidationError, json.JSONDecodeError) as exc:
        return error_response("invalid_request", str(exc))
    try:
        path = _resolve_trace_path(payload.path)
        trace, state = load_replay(path)
    except PermissionError as exc:
        return error_response("forbidden_path", str(exc), status=403)
    except (ValueError, OSError, KeyError) as exc:
        logger.warning("replay rejected for %s: %s", payload.path, exc)
        return error_response("invalid_trace", "Invalid recorded trace")
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    return JSONResponse(
        {"trace": trace, "report_md": render_report(state.report), "path": rel, "recorded": True}
    )


async def api_download(request):
    rel = request.query_params.get("path", "")
    kind = request.query_params.get("kind", "trace")
    try:
        trace_path = _resolve_trace_path(rel)
    except PermissionError as exc:
        return error_response("forbidden_path", str(exc), status=403)
    except OSError:
        return error_response("not_found", "Trace not found", status=404)
    run_dir = trace_path.parent.name
    if kind == "trace":
        target, filename = trace_path, f"{run_dir}-trace.json"
    elif kind == "report":
        target = trace_path.parent / "report.md"
        filename = f"{run_dir}-report.md"
    else:
        return error_response("invalid_request", "Unknown download kind")
    try:
        target = _resolve_download_file(target)
        if not target.is_file():
            return error_response("not_found", "Artifact not found", status=404)
    except PermissionError:
        return error_response("forbidden_path", "Unsafe artifact path", status=403)
    except OSError:
        return error_response("not_found", "Artifact not found", status=404)
    try:
        trace, state = load_replay(trace_path)
    except (ValueError, OSError, KeyError):
        return error_response("invalid_trace", "Invalid recorded trace")
    # Serve only validated in-memory data. A sibling markdown file may have been
    # edited or contaminated independently of the trace; regenerate its content.
    content = json.dumps(trace, ensure_ascii=False, indent=2) if kind == "trace" else (
        render_report(state.report)
    )
    return Response(
        content,
        media_type="application/json" if kind == "trace" else "text/markdown",
        headers={"Content-Disposition": f"attachment; filename*=utf-8''{quote(filename)}"},
    )


routes = [
    Route("/api/health", api_health),
    Route("/api/meta", api_meta),
    Route("/api/cases", api_cases),
    Route("/api/run", api_run, methods=["POST"]),
    Route("/api/traces", api_traces),
    Route("/api/replay", api_replay, methods=["POST"]),
    Route("/api/download", api_download),
    Mount("/", app=StaticFiles(directory=STATIC_DIR, html=True), name="static"),
]

app = Starlette(routes=routes)
