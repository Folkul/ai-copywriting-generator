"""Unit tests for agent_memory.py — history read/write, summary, edge cases."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_memory
from agent_memory import (
    build_memory_context,
    get_memory_display_hint,
    load_history,
    record_feedback,
    save_history,
)


class TestAgentMemory:
    """Test suite using a temporary history file."""

    @classmethod
    def setup_class(cls):
        cls._orig_file = agent_memory.HISTORY_FILE
        cls._orig_enabled = agent_memory.AGENT_MEMORY_ENABLED
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="test_memory_")
        tmp = Path(cls._tmpdir.name)
        agent_memory.HISTORY_FILE = tmp / "preference_history.json"
        agent_memory.AGENT_MEMORY_ENABLED = True

    @classmethod
    def teardown_class(cls):
        agent_memory.HISTORY_FILE = cls._orig_file
        agent_memory.AGENT_MEMORY_ENABLED = cls._orig_enabled
        cls._tmpdir.cleanup()

    def setup_method(self):
        """Clean history before each test."""
        hf = agent_memory.HISTORY_FILE
        if hf.is_file():
            hf.unlink()
        # Ensure data dir exists
        hf.parent.mkdir(parents=True, exist_ok=True)

    # ── Basic write/read ──

    def test_empty_history_returns_empty_list(self):
        assert load_history() == []

    def test_save_and_load_roundtrip(self):
        entries = [
            {"style": "humor", "adopted": True, "timestamp": 1000},
            {"style": "literary", "adopted": False, "timestamp": 2000},
        ]
        assert save_history(entries) is True
        loaded = load_history()
        assert len(loaded) == 2
        assert loaded[0]["style"] == "humor"
        assert loaded[1]["adopted"] is False

    def test_record_feedback_appends_and_trims(self):
        for i in range(15):
            record_feedback("humor", True)
        history = load_history()
        # Default max is 10
        assert len(history) == 10
        assert all(e["style"] == "humor" for e in history)
        assert all(e["adopted"] is True for e in history)

    # ── Memory context (summary) ──

    def test_build_memory_context_no_history(self):
        result = build_memory_context()
        assert result is None

    def test_build_memory_context_with_data(self):
        record_feedback("humor", True)
        record_feedback("humor", True)
        record_feedback("literary", False)
        result = build_memory_context(max_entries=5)
        assert result is not None
        assert "幽默风趣" in result
        assert "2 次采纳" in result
        assert "文艺清新" in result
        assert "换三条" in result
        # Must contain soft reference language
        assert "仅供参考" in result
        assert "非硬性要求" in result

    def test_build_memory_context_respects_max_entries(self):
        for i in range(10):
            record_feedback("humor" if i % 2 == 0 else "literary", i % 3 == 0)
        result = build_memory_context(max_entries=3)
        assert result is not None
        # Should only reference last 3
        assert "最近 3 次" in result

    # ── Display hint ──

    def test_get_memory_display_hint_no_history(self):
        result = get_memory_display_hint()
        assert result is None

    def test_get_memory_display_hint_with_data(self):
        record_feedback("humor", True)
        record_feedback("humor", True)
        record_feedback("literary", False)
        result = get_memory_display_hint()
        assert result is not None
        assert result["adopted_ratio"] == "2/3"
        assert result["dominant_style"] == "humor"
        assert "偏好幽默风趣" in result["summary"]

    # ── Disabled memory ──

    def test_disabled_memory_returns_empty(self):
        agent_memory.AGENT_MEMORY_ENABLED = False
        try:
            record_feedback("humor", True)
            assert load_history() == []
            assert build_memory_context() is None
            assert get_memory_display_hint() is None
            assert save_history([{"style": "x", "adopted": True, "timestamp": 1}]) is False
        finally:
            agent_memory.AGENT_MEMORY_ENABLED = True

    # ── Corrupted file ──

    def test_corrupted_file_returns_empty(self):
        hf = agent_memory.HISTORY_FILE
        hf.write_text("not valid json {{{", encoding="utf-8")
        assert load_history() == []

    def test_partially_corrupted_file_filters_bad_entries(self):
        hf = agent_memory.HISTORY_FILE
        data = [
            {"style": "humor", "adopted": True, "timestamp": 1},
            {"bad": "entry"},  # missing required fields
            {"style": "literary", "adopted": False, "timestamp": 2},
            "not a dict",  # wrong type
        ]
        hf.write_text(json.dumps(data), encoding="utf-8")
        loaded = load_history()
        assert len(loaded) == 2
        assert loaded[0]["style"] == "humor"
        assert loaded[1]["style"] == "literary"

    def test_missing_file_returns_empty(self):
        assert not agent_memory.HISTORY_FILE.is_file()
        assert load_history() == []

    # ── Unknown style slug ──

    def test_unknown_style_slug_falls_back_to_raw(self):
        record_feedback("unknown_style_xyz", True)
        result = build_memory_context(max_entries=5)
        assert result is not None
        assert "unknown_style_xyz" in result  # fallback to raw slug

    # ── Memory context respects user choice language ──

    def test_memory_context_soft_reference_language(self):
        record_feedback("humor", True)
        record_feedback("humor", True)
        result = build_memory_context()
        assert result is not None
        # Critical: must tell model to prioritize current user choice
        assert "以用户本次" in result
        assert "明确指定" in result or "明确" in result


def run_tests():
    """Simple test runner."""
    tests = TestAgentMemory()
    tests.setup_class()
    passed = 0
    failed = 0
    for name in dir(tests):
        if name.startswith("test_"):
            tests.setup_method()
            try:
                getattr(tests, name)()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                failed += 1
    tests.teardown_class()
    print()
    print(f"{passed} passed, {failed} failed, {passed + failed} total")
    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    raise SystemExit(0 if ok else 1)
