"""Explicit project-local transport options; no implicit provider fallback."""

import os


def provider_options(response_format=None, thinking=None, request_timeout=None):
    return dict(
        response_format_mode=response_format
        or os.getenv("INCIDENT_LENS_RESPONSE_FORMAT", "json_schema"),
        thinking=thinking or os.getenv("INCIDENT_LENS_THINKING") or None,
        timeout=request_timeout
        if request_timeout is not None
        else float(os.getenv("INCIDENT_LENS_REQUEST_TIMEOUT", "180")),
    )
