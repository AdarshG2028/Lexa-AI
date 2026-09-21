import asyncio

from app.models import Session


class InMemorySessionRepository:
    """Process-local session store. Sessions are lost on restart, which is
    acceptable until persistence lands in Phase 3."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create(self, session: Session) -> Session:
        async with self._lock:
            self._sessions[session.id] = session
        return session

    async def get(self, session_id: str) -> Session | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def save(self, session: Session) -> Session:
        async with self._lock:
            self._sessions[session.id] = session
        return session
