from typing import Protocol, runtime_checkable


@runtime_checkable
class AudioStorage(Protocol):
    """Stores audio by opaque key. A local-disk implementation is enough for
    now; an object-storage implementation can replace it without touching
    any calling code."""

    async def save(self, key: str, data: bytes) -> None: ...

    async def load(self, key: str) -> bytes: ...

    async def exists(self, key: str) -> bool: ...
