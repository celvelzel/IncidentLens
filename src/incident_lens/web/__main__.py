"""Serve the IncidentLens dashboard: python -m incident_lens.web [--host ...] [--port ...]."""

import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog="incident-lens-web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8022)
    args = parser.parse_args(argv)

    import uvicorn

    uvicorn.run("incident_lens.web.server:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
