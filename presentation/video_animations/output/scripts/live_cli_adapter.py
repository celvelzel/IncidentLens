"""Build-only compatibility adapter: classify live OhMyGPT artifacts as real.

The repository CLI accepts --provider ohmygpt, while artifacts.validate_metadata
accepts only real/mock. The investigation itself and all events remain untouched.
"""
import sys
import incident_lens.artifacts as artifacts
from incident_lens.cli import main

original=artifacts.save_run
def save_run(state, output, provider, *args, **kwargs):
    return original(state,output,'real' if provider=='ohmygpt' else provider,*args,**kwargs)
artifacts.save_run=save_run
raise SystemExit(main())
