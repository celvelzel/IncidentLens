"""Write bridge response envelopes from served raw JSON without editing the content.

The served content is copied verbatim. The envelope binding fields (session_id,
request_id, request_sha256) are read from the matching request file so the bridge
can verify request/response binding. This script only assembles the envelope; it
never rewrites, trims, or repairs the model output.
"""

import argparse
import hashlib
import json
import math
import pathlib
import re
import time

from incident_lens.evaluation.run_io import atomic_bytes, atomic_json


def read_request(path):
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("request must be a regular file")
    request = json.loads(path.read_bytes())
    original = {key: value for key, value in request.items() if key != "request_sha256"}
    actual = hashlib.sha256(json.dumps(original, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode("utf-8")).hexdigest()
    if actual != request.get("request_sha256"):
        raise ValueError("request digest mismatch")
    return request


def watch(bridge_dir, seconds, interval):
    """Return (pending, run finished, counts) once work appears or time is up.

    pending entries are (request_id, request_file_size_bytes).
    """
    if not math.isfinite(seconds) or seconds < 0 or not math.isfinite(interval) or interval <= 0:
        raise ValueError("watch duration must be finite/nonnegative and interval positive")
    bridge = pathlib.Path(bridge_dir)
    run_dir = bridge.parent
    deadline = time.monotonic() + seconds
    while True:
        requests = {p.stem: p for p in (bridge / "requests").glob("*.json")}
        responses = {p.stem for p in (bridge / "responses").glob("*.json")}
        pending = sorted(
            (stem, requests[stem].stat().st_size)
            for stem in set(requests) - responses
        )
        finished = (run_dir / "verification.json").is_file()
        if pending or finished or time.monotonic() >= deadline:
            return pending, finished, len(requests), len(responses)
        time.sleep(interval)


def _chunks(text, size):
    """Split text into byte-bounded chunks, preferring newline boundaries."""
    if type(size) is not int or size < 4:
        raise ValueError("chunk size must allow a complete UTF-8 character (at least 4 bytes)")
    data = text.encode("utf-8")
    chunks = []
    start = 0
    total = len(data)
    while start < total:
        end = min(start + size, total)
        if end < total:
            while end > start and (data[end] & 0xC0) == 0x80:
                end -= 1
            if end <= start:
                end = min(start + size, total)
            newline = data.rfind(b"\n", start, end)
            if newline > start:
                end = newline + 1
        chunks.append(data[start:end].decode("utf-8"))
        start = end
    return chunks


def prepare(request_path, prep_dir, chunk_bytes):
    """Write the request's messages array as ordered small part files.

    The request payload is never printed to stdout; only part paths/sizes are.
    """
    path = pathlib.Path(request_path)
    request = read_request(path)
    text = json.dumps(
        request["messages"], ensure_ascii=False, separators=(",", ":")
    )
    prep = pathlib.Path(prep_dir)
    prep.mkdir(parents=True, exist_ok=True)
    parts = []
    for index, chunk in enumerate(_chunks(text, chunk_bytes)):
        out = prep / (path.stem + ".part-%02d.json" % index)
        atomic_bytes(out, chunk.encode("utf-8"))
        parts.append((out, len(chunk.encode("utf-8"))))
    atomic_json(prep / (path.stem + ".manifest.json"), {
        "schema_version": 1, "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "messages_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "parts": [{"name": p.name, "bytes": size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p, size in parts],
        "instruction": "Read all parts in order, concatenate literal contents without separators. "
                       "The concatenated messages array is the entire model input. "
                       "Serve repair requests by the same procedure. No operator hints or edits.",
    })
    return parts


def build(bridge_dir, serve_dir, request_ids):
    bridge = pathlib.Path(bridge_dir)
    serve = pathlib.Path(serve_dir)
    (bridge / "responses").mkdir(parents=True, exist_ok=True)
    report = []
    for request_id in request_ids:
        if re.fullmatch(r"req-[0-9]{4,}(?:-repair)?", request_id) is None:
            raise ValueError("invalid request ID")
        request_path = bridge / "requests" / (request_id + ".json")
        raw_path = serve / (request_id + ".raw.json")
        if not request_path.is_file():
            raise SystemExit("missing request file: " + str(request_path))
        if not raw_path.is_file():
            raise SystemExit("missing raw output file: " + str(raw_path))
        request = read_request(request_path)
        # read_bytes avoids newline translation; preserve whitespace verbatim.
        content = raw_path.read_bytes().decode("utf-8")
        envelope = {
            "session_id": request["session_id"],
            "request_id": request["request_id"],
            "request_sha256": request["request_sha256"],
            "content": content,
        }
        out_path = bridge / "responses" / (request_id + ".json")
        if out_path.is_symlink() or getattr(out_path, "is_junction", lambda: False)():
            raise ValueError("response must be a regular file")
        if out_path.exists():
            if json.loads(out_path.read_bytes()) != envelope:
                raise FileExistsError("refusing to replace an already served response")
        else:
            atomic_json(out_path, envelope, exclusive=True)
        try:
            json.loads(content)
            valid = "ok"
        except ValueError:
            valid = "NOT_JSON"
        report.append((request_id, len(content), valid))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-dir", required=True)
    parser.add_argument("--serve-dir")
    parser.add_argument("--requests", nargs="+")
    parser.add_argument("--watch", type=float)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--prepare")
    parser.add_argument("--prep-dir")
    parser.add_argument("--chunk-kb", type=float, default=40.0)
    args = parser.parse_args()
    if args.prepare:
        if not args.prep_dir:
            raise SystemExit("--prep-dir is required with --prepare")
        parts = prepare(args.prepare, args.prep_dir, int(args.chunk_kb * 1024))
        print("PREPARED " + str(len(parts)) + " parts")
        for out, size in parts:
            print("PART " + str(out) + " bytes=" + str(size))
        return
    if args.watch is not None:
        pending, finished, total_req, total_resp = watch(
            args.bridge_dir, args.watch, args.interval
        )
        print(
            "WATCH pending=" + json.dumps(pending) + " finished=" + str(finished)
            + " req=" + str(total_req) + " resp=" + str(total_resp)
        )
        if args.prep_dir:
            for request_id, size in pending:
                if size > 60 * 1024:
                    for part, part_size in prepare(
                        pathlib.Path(args.bridge_dir) / "requests" / (request_id + ".json"),
                        args.prep_dir, int(args.chunk_kb * 1024),
                    ):
                        print("PART " + str(part) + " bytes=" + str(part_size))
        return
    if not args.serve_dir or not args.requests:
        raise SystemExit("--serve-dir and --requests are required unless --watch is used")
    for request_id, size, valid in build(args.bridge_dir, args.serve_dir, args.requests):
        print("WROTE " + request_id + " content_len=" + str(size) + " " + valid)


if __name__ == "__main__":
    main()
