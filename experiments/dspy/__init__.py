"""Offline task optimization and evidence-grounded evaluation."""

import os

# LiteLLM otherwise fetches a price catalog merely on import. We use neither its
# transport nor its inferred prices; keep offline runs strictly offline.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
