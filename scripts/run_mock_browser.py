"""Start a local dashboard, run Mock browser acceptance, and always stop it."""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def main():
    out = Path("results/ci/browser")
    out.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # This acceptance uses fixtures only; do not inherit provider credentials.
    for key in list(env):
        if key.startswith("INCIDENT_LENS_"):
            env.pop(key)
    env.update(
        REPLAY_BASE_URL="http://127.0.0.1:8766",
        WP_C_BROWSER_OUT=str(out),
        PYTHON_DOTENV_DISABLED="1",
    )
    with (out / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "incident_lens.web", "--port", "8766"],
            env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(120):
                if server.poll() is not None:
                    raise RuntimeError("Dashboard exited; see results/ci/browser/server.log")
                try:
                    with urllib.request.urlopen(env["REPLAY_BASE_URL"], timeout=1):
                        break
                except OSError:
                    time.sleep(0.25)
            else:
                raise TimeoutError("Dashboard did not become ready")
            subprocess.run(["node", "tests/web/browser.cjs"], env=env, check=True)
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    main()
