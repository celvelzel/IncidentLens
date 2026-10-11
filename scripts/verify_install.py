"""Build a wheel and validate it in a fresh, retained virtual environment."""

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results/acceptance/install"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    wheels = out / "wheels"
    wheels.mkdir(exist_ok=True)
    commands = []
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("VIRTUAL_ENV", None)

    def run(arguments, cwd=out):
        process = subprocess.run(
            arguments, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        commands.append(
            {
                "command": [str(a) for a in arguments],
                "exit_code": process.returncode,
                "output": process.stdout,
            }
        )
        (out / "install-log.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
        if process.returncode:
            raise RuntimeError(f"Installation smoke failed; inspect {out / 'install-log.json'}")

    run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(root)])
    environment = out / "environment"
    if environment.exists():
        raise ValueError("Use a new --out path; existing verification environments are preserved")
    venv.create(environment, with_pip=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheel = next(wheels.glob("incident_lens-*.whl"))
    run([str(python), "-m", "pip", "install", "-r", str(root / "requirements.lock"), str(wheel)])
    run([str(python), "-m", "pip", "check"])
    run([str(python), "-m", "incident_lens.cli", "check-environment"])
    run(
        [str(python), "-m", "incident_lens.cli", "validate-data", "--data-root", str(root / "data")]
    )
    run(
        [
            str(python),
            "-m",
            "incident_lens.cli",
            "run",
            "--case",
            "incident_001",
            "--provider",
            "mock",
            "--data-root",
            str(root / "data"),
            "--cache-mode",
            "off",
            "--out",
            str(out / "smoke"),
        ]
    )
    run(
        [str(python), "-m", "incident_lens.cli", "replay", "--trace", str(out / "smoke/trace.json")]
    )
    print(json.dumps({"success": True, "commands": len(commands), "artifacts": str(out)}))


if __name__ == "__main__":
    main()
