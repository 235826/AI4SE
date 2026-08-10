import json
from pathlib import Path

from patchpilot.memory import MemoryStore
from patchpilot.models import MemoryEntry


def test_append_and_read_recent_entries(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.jsonl")
    store.append(kind="decision", content="use mock provider", source="user", run_id="r1")
    store.append(kind="failure", content="test_x failed", source="pytest", run_id="r1")
    entries = store.recent(limit=1)
    assert len(entries) == 1
    assert entries[0].content == "test_x failed"


def test_recent_returns_empty_for_missing_file(tmp_path: Path):
    store = MemoryStore(tmp_path / "missing.jsonl")
    assert store.recent() == []


def test_append_creates_parent_and_writes_parseable_entry(tmp_path: Path):
    path = tmp_path / ".patchpilot" / "memory.jsonl"
    store = MemoryStore(path)
    entry = store.append(kind="decision", content="keep it local", source="user", run_id="r2")

    assert isinstance(entry, MemoryEntry)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record == {
        "timestamp": entry.timestamp,
        "kind": "decision",
        "content": "keep it local",
        "source": "user",
        "run_id": "r2",
    }


def test_recent_with_zero_limit_returns_empty(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.jsonl")
    store.append(kind="decision", content="one entry", source="user", run_id="r3")

    assert store.recent(limit=0) == []
