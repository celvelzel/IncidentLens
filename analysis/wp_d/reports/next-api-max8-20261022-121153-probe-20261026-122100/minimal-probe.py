"""One standalone minimal diagnostic probe against the frozen provider.

No slot replacement, no retries, no project/incident/Oracle/history data.
Replicates the request shape of the original batch and the 2026-10-23 probe:
model, temperature, messages, response_format (json_schema), thinking.
"""

import ipaddress
import json
import os
import time
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

MODEL = os.environ["INCIDENT_LENS_MODEL"]
API_KEY = os.environ["INCIDENT_LENS_API_KEY"]
BASE_URL = os.environ["INCIDENT_LENS_BASE_URL"]

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}

BODY = {
    "model": MODEL,
    "temperature": 0.0,
    "messages": [
        {
            "role": "system",
            "content": "Return a NEW output object, not the input state. "
            "The required output JSON Schema is:\n" + json.dumps(SCHEMA),
        },
        {"role": "user", "content": json.dumps({"task": "health check"})},
    ],
    "response_format": {
        "type": "json_schema",
        "json_schema": {"name": "ProbeResult", "strict": True, "schema": SCHEMA},
    },
    "thinking": {"type": "disabled"},
}

# The local NO_PROXY carries "[::1]" (bracketed), which httpx turns into the
# unparseable mount "all://*[::1]" (Invalid port). Mirror httpx's own NO_PROXY
# mapping, strip brackets so "::1" maps to the valid "all://[::1]", and drop
# entries that still fail. Proxy routing for the API host is unchanged
# (trust_env=True via 127.0.0.1:7892), matching the frozen provider.
def _httpx_mount_key(hostname):
    if "://" in hostname:
        return hostname
    try:
        ipaddress.IPv4Address(hostname.split("/")[0])
        return f"all://{hostname}"
    except ValueError:
        pass
    try:
        ipaddress.IPv6Address(hostname.split("/")[0])
        return f"all://[{hostname}]"
    except ValueError:
        pass
    if hostname.lower() == "localhost":
        return f"all://{hostname}"
    return f"all://*{hostname}"


kept = []
dropped = []
original_no_proxy = os.environ.get("NO_PROXY", "")
for entry in original_no_proxy.split(","):
    entry = entry.strip()
    if not entry:
        continue
    if entry.startswith("[") and entry.endswith("]"):
        entry = entry[1:-1]
    try:
        httpx.URL(_httpx_mount_key(entry))
    except Exception:
        dropped.append(entry)
        continue
    kept.append(entry)
sanitized = ",".join(kept)
os.environ["NO_PROXY"] = sanitized
os.environ["no_proxy"] = sanitized

result = {
    "purpose": "one standalone minimal diagnostic, no slot replacement, no retries",
    "time_utc": datetime.now(timezone.utc).isoformat(),
    "model": MODEL,
    "request_fields": sorted(BODY.keys()),
    "request_contains_private_project_data": False,
    "no_proxy_sanitized": {
        "original": original_no_proxy,
        "kept": kept,
        "dropped": dropped,
        "reason": 'bracketed "[::1]" is unparseable by httpx; brackets stripped, routing unchanged',
    },
}

url = BASE_URL + "/chat/completions"
started = time.perf_counter()
response = httpx.post(
    url,
    json=BODY,
    headers={"Authorization": "Bearer " + API_KEY},
    timeout=120.0,
    trust_env=True,
)
elapsed = time.perf_counter() - started

result["status"] = response.status_code
result["elapsed_seconds"] = elapsed
result["response_headers"] = {
    k: v
    for k, v in response.headers.items()
    if k.lower() in {"content-type", "x-request-id", "date", "server"}
}

try:
    envelope = response.json()
except ValueError:
    envelope = None

if response.status_code >= 400:
    result["error"] = envelope.get("error") if isinstance(envelope, dict) else None
    result["usage"] = None
else:
    result["error"] = None
    result["choices"] = envelope.get("choices") if isinstance(envelope, dict) else None
    result["usage"] = envelope.get("usage") if isinstance(envelope, dict) else None

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "minimal-probe.json"), "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2, ensure_ascii=False)

print(json.dumps(result, indent=2, ensure_ascii=False))
