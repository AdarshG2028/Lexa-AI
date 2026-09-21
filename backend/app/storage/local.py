from pathlib import Path

from app.core.errors import StorageError


class LocalAudioStorage:
    """Writes audio under a root directory, one file per key."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        if ".." in key or Path(key).is_absolute():
            raise StorageError("Invalid audio key.")
        return self._root / key

    async def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise StorageError("The audio file could not be written.") from exc

    async def load(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError("The audio file could not be read.") from exc

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()
