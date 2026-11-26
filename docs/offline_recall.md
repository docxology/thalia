# Trace a stored episode offline

This example uses the synthetic Lisbon fixture from
[the recall tests](../tests/test_recall.py). It exercises a real SQLite
database and the retrieval layer directly. Run it from the repository
root after the [locked installation](quickstart.md#install--verify).

```bash
uv run --no-sync python - <<'PYTHON'
from pathlib import Path
from tempfile import TemporaryDirectory

from src.memory.episodic_store import EpisodicStore
from src.recall import recall_evidence
from src.signatures import EpisodicEntry

query = "Where do I live?"
with TemporaryDirectory() as temporary:
    database = str(Path(temporary) / "episodes.db")
    with EpisodicStore(database) as store:
        assert recall_evidence(store, "", query) == []
        store.append(EpisodicEntry(0, "where do I live", "I live in Lisbon"))
        store.append(EpisodicEntry(1, "what is for lunch", "tacos"))

    with EpisodicStore(database) as reopened:
        windows = recall_evidence(reopened, "", query)
        assert any("Lisbon" in item.text for item in windows)
        assert all(item.source_index < 0 for item in windows)
        for item in windows:
            print(item.source_index, item.text)
PYTHON
```

The empty string stands for empty derived memory. A negative source index
marks recalled evidence, separate from positions in the active transcript.
The temporary directory owns the raw episodes and disappears after the
example. A real [session](../src/session.py) can combine these stored
episodes with current context.

The fixture checks persistence and source separation. The
[manuscript validation section](manuscript/11_validation.md#isolated-memory-recall-validation-secval-memory)
shows the larger validation context, including the separate no-store
ablation.
