from pathlib import Path

from patchpilot.memory import MemoryStore


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
