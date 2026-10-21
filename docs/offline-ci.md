# Offline continuous integration

Every push and pull request runs `.github/workflows/ci.yml` on GitHub-hosted
runners. No repository secrets or model credentials are needed.

| Job | Coverage |
| --- | --- |
| Ruff | `python -m ruff check src tests scripts` |
| Python / Ubuntu and Windows | Full pytest discovery, Python 3.13, Node 22 available for embedded JS checks |
| JavaScript and Mock browser | All `tests/web/*.test.mjs`, then headless Chromium Mock replay acceptance |

Python jobs fetch full Git history because the reliability tests load a frozen
provider implementation using `git show`. Both operating systems are needed:
Windows junction/sharing tests intentionally skip on Linux, while link tests can
skip when the runner does not grant the required OS privilege. Pytest prints skip
reasons and uploads JUnit XML; browser screenshots and server logs are retained
for seven days, including on failure.

With `INCIDENT_LENS_OFFLINE_TESTS=1`, an autouse pytest fixture rejects external
socket connections in the pytest process (loopback remains available). Child
processes do not inherit this Python monkeypatch. The suite uses Mock providers
and HTTP MockTransport fixtures; provider class/file names containing `real`
do not mean those fixtures call a real service. CI does not supply credentials
or a local `.env` file; `PYTHON_DOTENV_DISABLED=1` also disables dotenv loading.
Browser acceptance blocks requests outside its local
dashboard origin and asserts that no `/api/run` request occurs.

## Local reproduction

From the repository root, install Python 3.13 and Node 22, then run:

```powershell
python -m pip install -r requirements.lock
python -m pip install -e '.[dev]'
npm ci
npx playwright install chromium
python -m ruff check src tests scripts
$env:INCIDENT_LENS_OFFLINE_TESTS = '1'
$env:PYTHON_DOTENV_DISABLED = '1'
python -m pytest -ra --junitxml=results/ci/pytest.xml
npm test
python scripts/run_mock_browser.py
```

On Linux, use `npx playwright install --with-deps chromium`,
`export INCIDENT_LENS_OFFLINE_TESTS=1`, and `export PYTHON_DOTENV_DISABLED=1`.
The browser runner starts and stops its
own dashboard at `127.0.0.1:8766`; keep that port free. Output goes to
`results/ci/browser/`. `CHROMIUM_PATH` and `PLAYWRIGHT_MODULE` remain optional
local overrides; CI uses the npm-locked Playwright and its managed Chromium.
Run Python/UI suites serially within one checkout: the Streamlit replay test
selects from the shared `results/` tree, so concurrent suites can change its
options during selection. GitHub jobs use separate checkouts and pytest runs
serially inside each job.

The saved-artifact JS regression uses the committed Mock success trace by
default. `WP_C_REAL_TRACE` can still select an existing recorded trace without
making model requests.

## Deferred coverage

Real-provider evaluation scripts and the historical `tests/web/browser-real.cjs`
acceptance are not executed here. The latter makes no model requests itself,
but asserts details of a specific, untracked real-provider trace and companion
artifacts under `results/v16/wp-c-real-replay/`; it is not the Mock browser suite.
Live API smoke tests, scheduled model evaluations, deployment, and required
branch checks are separate follow-up work.
