"""Write bridge response envelopes from served raw JSON without editing the content.

The served content is copied verbatim. The envelope binding fields (session_id,
request_id, request_sha256) are read from the matching request file so the bridge
can verify request/response binding. This script only assembles the envelope; it
never rewrites, trims, or repairs the model output.
"""

import argparse
import json
import pathlib
import time


def watch(bridge_dir, seconds, interval):
    """Return (pending, run finished, counts) once work appears or time is up.

    pending entries are (request_id, request_file_size_bytes).
    """
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
    request = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(
        request["messages"], ensure_ascii=False, separators=(",", ":")
    )
    prep = pathlib.Path(prep_dir)
    prep.mkdir(parents=True, exist_ok=True)
    parts = []
    for index, chunk in enumerate(_chunks(text, chunk_bytes)):
        out = prep / (path.stem + ".part-%02d.json" % index)
        out.write_text(chunk, encoding="utf-8")
        parts.append((out, len(chunk.encode("utf-8"))))
    return parts


def build(bridge_dir, serve_dir, request_ids):
    bridge = pathlib.Path(bridge_dir)
    serve = pathlib.Path(serve_dir)
    (bridge / "responses").mkdir(parents=True, exist_ok=True)
    report = []
    for request_id in request_ids:
        request_path = bridge / "requests" / (request_id + ".json")
        raw_path = serve / (request_id + ".raw.json")
        if not request_path.is_file():
            raise SystemExit("missing request file: " + str(request_path))
        if not raw_path.is_file():
            raise SystemExit("missing raw output file: " + str(raw_path))
        request = json.loads(request_path.read_text(encoding="utf-8"))
        content = raw_path.read_text(encoding="utf-8").strip()
        envelope = {
            "session_id": request["session_id"],
            "request_id": request["request_id"],
            "request_sha256": request["request_sha256"],
            "content": content,
        }
        out_path = bridge / "responses" / (request_id + ".json")
        out_path.write_text(
            json.dumps(envelope, ensure_ascii=False), encoding="utf-8"
        )
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
        return
    if not args.serve_dir or not args.requests:
        raise SystemExit("--serve-dir and --requests are required unless --watch is used")
    for request_id, size, valid in build(args.bridge_dir, args.serve_dir, args.requests):
        print("WROTE " + request_id + " content_len=" + str(size) + " " + valid)


if __name__ == "__main__":
    main()
