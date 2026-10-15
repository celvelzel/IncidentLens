# V1.6 replay demonstration

Existing Web and /api/replay reused. Prefix playback has first/previous/play/pause/next/last and1x/2x/4x; recorded workflow/task/event/hypothesis views and authorized evidence provenance inspector. Missing history says not recorded. Real structured events only; no generated dialogue or inferred hidden reasoning. Final state never fills in earlier report or evidence. Private labels remain outside UI.

Implementation/demo instructions and worker screenshots: ../ui/v16-replay.md. Start `.venv/Scripts/python.exe -m incident_lens.cli web --port 8767`, then open http://127.0.0.1:8767/#/run?path=results%2Fv16%2Fpreflight%2Fm0-20261015-01%2Fmock-positive%2Ftrace.json . This is clearly labelled recorded Mock, not live success. Follow the2–3minute saved event demonstration in the UI document, confirming actual event order instead of narrating nonexistent turns.

Lead actual-backend browser receipt: results/v16/integration/20261015-01/browser-integrated.json. Three /api/replay responses200, no interception,0/api/run requests,0page errors. Success uses the real saved G0 Mock run; missing and injected-provider-failure fixtures are copied without modifying their trace content into that integration directory. Desktop1440x1000 and narrow390x844 screenshots retained there. Node10tests and backend11tests independently passed before final QA. Browser fixture-only worker checks are distinguished from this actual API check.

G3 passed independent integrated review for Mock engineering; no fresh live-success trace exists. The injected failure is an offline test fixture, never evidence of an actual external provider outage. Very large trace performance and real-provider reliability are unverified.

Final G3 engineering acceptance: PASS. Sourcec69ac16 Node13+full950passed3skipped; actual nonintercepted browser3traces200, no/api/run/pageerrors. Final screenshots and receipt under results/v16/final-qa/20261015-02/browser-final/; docs/ui/v16-evidence/ updated from these captures after resize transitions settled. Live-success evidence remains absent.
