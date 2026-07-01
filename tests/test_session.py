"""Tests for the persistent multi-turn Session (Zero-Mock, real SQLite files)."""

from src.session import Session


class TestEphemeralSession:
    def test_ask_records_turn(self):
        s = Session()
        s.ask("My wifi password is bluefish42")
        assert s.turn_count == 1

    def test_memory_across_turns(self):
        s = Session()
        s.ask("My wifi password is bluefish42")
        out = s.ask("What is the wifi password?")
        # The Inspector retrieves the earlier turn from the running transcript.
        assert "bluefish42" in out.answer

    def test_turn_count_increments(self):
        s = Session()
        s.ask("first message about alpha")
        s.ask("second message about beta")
        assert s.turn_count == 2


class TestFilePersistence:
    def test_persists_and_reopens(self, tmp_path):
        db = str(tmp_path / "episodes.db")
        mem = str(tmp_path / "MEMORY.md")

        s = Session(db_path=db, memory_path=mem)
        s.ask("please remember the door code is 4321", session_ending=True)
        assert s.turn_count == 1
        s.close()

        # Memory file written by consolidation.
        assert (tmp_path / "MEMORY.md").exists()
        assert "4321" in (tmp_path / "MEMORY.md").read_text()

        # Reopen: prior episode + memory are restored; no duplicate-turn error.
        s2 = Session(db_path=db, memory_path=mem)
        assert s2.turn_count == 1
        assert "4321" in s2.harness.memory_gate.memory_md
        out = s2.ask("what is the door code")
        assert s2.turn_count == 2
        assert out.memory_written.turn_id == 1  # resumed turn id, no collision

    def test_transcript_reconstructed_on_reopen(self, tmp_path):
        db = str(tmp_path / "episodes.db")
        s = Session(db_path=db)
        s.ask("The secret token is zephyr99")
        s.close()

        s2 = Session(db_path=db)
        # The reconstructed transcript lets a fresh process retrieve the fact.
        out = s2.ask("What is the secret token?")
        assert "zephyr99" in out.answer

    def test_no_memory_path_does_not_write(self, tmp_path):
        # memory_path=None: consolidation updates in-process memory only.
        s = Session(db_path=str(tmp_path / "e.db"))
        s.ask("please remember the gate code is 1111", session_ending=True)
        assert not list(tmp_path.glob("MEMORY.md"))
        s.close()


class TestSessionLifecycle:
    def test_reset_clears_transcript(self, tmp_path):
        """Reset discards in-memory transcript and creates a fresh store."""
        db = str(tmp_path / "episodes_reset.db")
        s = Session(db_path=db)
        s.ask("my wifi password is bluefish42")
        assert s.turn_count == 1
        # Reset closes the old store and opens a new one at the same path.
        # Since the old episodes were in the same file, the new store sees them.
        s.reset()
        assert s.turn_count == 1  # same db_path, same episodes
        # Verify the transcript was re-read from the store.
        out = s.ask("what is the wifi password")
        assert "bluefish42" in out.answer
        assert s.turn_count == 2

    def test_reset_preserves_persisted_memory(self, tmp_path):
        """Reset re-reads MEMORY.md from disk, surviving the reset."""
        db = str(tmp_path / "episodes_mem.db")
        mem = str(tmp_path / "MEMORY.md")
        s = Session(db_path=db, memory_path=mem)
        s.ask("please remember the combo is 1234", session_ending=True)
        assert s.turn_count == 1
        s.close()
        # Re-open, then reset.
        s2 = Session(db_path=db, memory_path=mem)
        assert s2.turn_count == 1
        assert "1234" in s2.harness.memory_gate.memory_md
        s2.reset()
        # After reset: fresh store at same path (episodes still there), memory from disk reloaded.
        assert "1234" in s2.harness.memory_gate.memory_md
        assert s2.turn_count == 1  # episodes persist on disk
