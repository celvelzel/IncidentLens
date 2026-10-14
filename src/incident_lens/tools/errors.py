"""Expected query misses are distinct from unavailable or corrupt sources."""


class QueryNotFoundError(LookupError):
    """The requested public entity does not exist in this case."""


class InvalidSourceError(RuntimeError):
    """An authorized source could not be decoded into evidence records."""
