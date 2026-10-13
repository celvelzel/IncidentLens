"""Generic causal dynamics and observation encoders, never a held-out scenario catalog."""

from .world import encode, simulate

__all__ = ["encode", "simulate"]
