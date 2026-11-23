# IncidentLens video delivery

Final video: IncidentLens_Presentation_10min.mp4 (1920×1080, 30 fps, H.264 + AAC).
All nine clips are in clips/; ElevenLabs voiceovers and their original versions are in ../voiceover_audio/.

## Verification

All 18,007 frames decoded successfully. All nine segment streams, frame counts, audio energy, and durations passed. Final audio measures approximately −16 LUFS throughout. The assembled video lasts 600.26 seconds. Tracked and staged git diffs are empty. All four animation hashes and modification timestamps match the baseline. The browser recording contains 21 real interactions, no JavaScript errors, and zero provider calls during replay.

## Factual adjustments to the supplied plan

- The actual Hunyuan incident_001 live investigation abstained. Its persisted output is shown unchanged, and segment 4 narration describes INCONCLUSIVE rather than an invented resolved outcome.
- The resolved browser walkthrough uses the original completed hy4-flash incident_4014 experiment, exported by the repository's validated artifact writer. Provenance is in resolved_trace_provenance.json.
- The original CLI accepted ohmygpt but rejected that label during artifact persistence. A build-only adapter saves the provider class as real. The initial invocation discarded its completed state; one replacement live run produced the artifacts. No tracked project source was changed.
- The requested -k leading_review selector matched no tests. The real -k review_leading regression test passed; both outputs are retained.
- The actual DeepSeek incident_4018 run used 15 tools, so narration and visuals use 15.
- The recorded stop request has no required active roles. The recording states that STOP_ACK is not required, rather than inserting a synthetic event.
- The existing 110/110 matrix lacked summary.json. Its summary was derived from the authentic saved fault-matrix.csv.
- A uniform pitch-preserving tempo adjustment brings the original voiceovers to the requested ten-minute duration. Segment 4 was regenerated to correct factual assumptions. Original and corrected raw ElevenLabs files are retained.

Full paths, exact durations, sizes, SHA-256 hashes, encoding, audio measurements, browser audit, source integrity, and production adjustments are in build_manifest.json. Build and verification scripts are retained in scripts/; generated stages are in stages/.
