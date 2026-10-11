"""SQLite WAL storage with per-operation connections and atomic writes."""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep, time


class SQLiteCacheStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = monotonic() + 15
        while True:
            try:
                self._initialize()
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or monotonic() >= deadline:
                    raise
                sleep(0.02)

    def _initialize(self):
        with self.connection() as db:
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS explanations (
                cache_key TEXT PRIMARY KEY, namespace_digest TEXT NOT NULL,
                namespace_json TEXT NOT NULL, task_signature TEXT NOT NULL,
                question TEXT NOT NULL, exact_question TEXT NOT NULL,
                embedding_backend TEXT NOT NULL, vector_json TEXT NOT NULL,
                response_json TEXT NOT NULL, created_at REAL NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                response_sha256 TEXT NOT NULL, ttl_seconds REAL NOT NULL)""")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(explanations)")}
            if "response_sha256" not in columns:
                db.execute(
                    "ALTER TABLE explanations ADD COLUMN response_sha256 TEXT NOT NULL DEFAULT ''"
                )
            if "ttl_seconds" not in columns:
                db.execute(
                    "ALTER TABLE explanations ADD COLUMN ttl_seconds REAL NOT NULL DEFAULT 0"
                )
            db.execute(
                "CREATE INDEX IF NOT EXISTS explanations_namespace ON explanations(namespace_digest)"
            )

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def candidates(self, namespace_digest, task_signature):
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM explanations WHERE namespace_digest=? AND task_signature=? ORDER BY created_at DESC",
                    (namespace_digest, task_signature),
                )
            ]

    def put(
        self,
        *,
        cache_key,
        namespace_digest,
        namespace_json,
        task_signature,
        question,
        exact_question,
        embedding_backend,
        vector,
        response_json,
        ttl_seconds,
    ):
        with self.connection() as db:
            db.execute(
                """INSERT INTO explanations
                (cache_key,namespace_digest,namespace_json,task_signature,question,exact_question,
                 embedding_backend,vector_json,response_json,created_at,response_sha256,ttl_seconds)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(cache_key) DO UPDATE SET namespace_json=excluded.namespace_json,
                question=excluded.question,exact_question=excluded.exact_question,
                embedding_backend=excluded.embedding_backend,vector_json=excluded.vector_json,
                response_json=excluded.response_json,created_at=excluded.created_at,hit_count=0,
                response_sha256=excluded.response_sha256,ttl_seconds=excluded.ttl_seconds""",
                (
                    cache_key,
                    namespace_digest,
                    namespace_json,
                    task_signature,
                    question,
                    exact_question,
                    embedding_backend,
                    json.dumps(list(vector)),
                    response_json,
                    time(),
                    hashlib.sha256(response_json.encode()).hexdigest(),
                    ttl_seconds,
                ),
            )

    def record_hit(self, cache_key):
        with self.connection() as db:
            db.execute(
                "UPDATE explanations SET hit_count=hit_count+1 WHERE cache_key=?", (cache_key,)
            )

    def delete(self, cache_key):
        with self.connection() as db:
            db.execute("DELETE FROM explanations WHERE cache_key=?", (cache_key,))
