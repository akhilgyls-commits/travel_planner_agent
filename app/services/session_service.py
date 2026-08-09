"""
Session management service.

The LangGraph checkpointer already persists conversation state per
thread_id, but we need a lightweight registry to:
  - generate/validate session ids
  - track simple metadata (created_at, last_active_at, destination)
  - enforce TTL-based expiry for an in-memory deployment
  - give the API a clean place to raise "session not found" errors

For production/multi-instance deployments, swap this in-memory registry
(and the LangGraph MemorySaver) for a persistent backend (Redis,
Postgres) -- the interface here is intentionally small so that's a
localized change.
"""
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SessionMeta:
    session_id: str
    destination: str
    created_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)


class SessionNotFoundError(Exception):
    pass


class SessionService:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionMeta] = {}
        self._lock = Lock()

    def create_session(self, destination: str) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = SessionMeta(session_id=session_id, destination=destination)
        logger.info("session.created", extra={"session_id": session_id, "destination": destination})
        return session_id

    def touch(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].last_active_at = time.time()

    def exists(self, session_id: str) -> bool:
        self._evict_expired()
        with self._lock:
            return session_id in self._sessions

    def get(self, session_id: str) -> SessionMeta:
        self._evict_expired()
        with self._lock:
            meta = self._sessions.get(session_id)
        if meta is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found or has expired.")
        return meta

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
        logger.info("session.deleted", extra={"session_id": session_id})

    def register_existing(self, session_id: str, destination: Optional[str] = None) -> None:
        """Used when a client supplies a session_id that already exists in the
        LangGraph checkpointer but not yet in our local registry (e.g. after
        an app restart with an external checkpoint store)."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionMeta(
                    session_id=session_id, destination=destination or "unknown"
                )

    def _evict_expired(self) -> None:
        ttl = get_settings().session_ttl_seconds
        now = time.time()
        with self._lock:
            expired = [sid for sid, meta in self._sessions.items() if now - meta.last_active_at > ttl]
            for sid in expired:
                del self._sessions[sid]
        if expired:
            logger.info("session.evicted", extra={"count": len(expired)})


_session_service_singleton: SessionService | None = None


def get_session_service() -> SessionService:
    global _session_service_singleton
    if _session_service_singleton is None:
        _session_service_singleton = SessionService()
    return _session_service_singleton
