# Nine-minute offline demonstration

Run commands from the repository root with its installed `.venv` interpreter.

1. **0:00–1:00** Show the public evidence boundary and five mechanisms.
   Run `python -m incident_lens.cli validate-data` and `list-cases`.
2. **1:00–3:30** Run `python -m incident_lens.cli run --case incident_001 --provider mock --cache-mode off --out results/demo001`.
   Show PostgreSQL suspicion, normal database observations, Verifier challenge,
   actual change ID and backend pool diff in the trace.
3. **3:30–5:00** Start `streamlit run src/incident_lens/ui/app.py --server.address 127.0.0.1`.
   Load the saved trace with Recorded Replay. Show the first REVIEW and following
   DECISION, PostgreSQL REJECTED, backend SUPPORTED and the report citations.
4. **5:00–6:00** Run incident_006. Show intentional INCONCLUSIVE, missing
   evidence and stop reason rather than a guessed cause.
5. **6:00–7:00** Show logs→config denied by isolation tests and explain issued
   contexts, actual-query provenance and role-specific provider input.
6. **7:00–8:00** Show four-variant CSV results with separate denominators and
   Mock labels. Cache off/cold/warm has 15/15/11 requests, four warm hits, same
   report and nine tools. Local timing does not establish billing/latency savings.
7. **8:00–9:00** Show tests, fresh installation log and limitations: synthetic
   templates, five-mechanism rules, live LLM results pending and semantic review
   not yet performed.

This is a runnable demo guide, not a claim that a video was recorded/submitted.
