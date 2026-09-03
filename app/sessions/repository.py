from typing import Protocol, runtime_checkable

from app.models import Session


@runtime_checkable
class SessionRepository(Protocol):
    """Session persistence. In-memory for now; a database-backed
    implementation arrives in Phase 3 without changing the service layer."""

    async def create(self, session: Session) -> Session: ...

    async def get(self, session_id: str) -> Session | None: ...

    async def save(self, session: Session) -> Session: ...
