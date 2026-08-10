from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import MemoryEntry


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, kind: str, content: str, source: str, run_id: str) -> MemoryEntry:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = MemoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            content=content,
            source=source,
            run_id=run_id,
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry.__dict__) + "\n")
        return entry

    def recent(self, limit: int = 5) -> list[MemoryEntry]:
        if limit <= 0 or not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as file:
            entries = [MemoryEntry(**json.loads(line)) for line in file if line.strip()]
        return entries[-limit:]
