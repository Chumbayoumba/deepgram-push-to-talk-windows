from __future__ import annotations

from pathlib import Path

from deepgram_stt.pending_store import PendingDictationStore


def test_pending_store_saves_and_loads_audio(tmp_path: Path) -> None:
    store = PendingDictationStore(base_dir=tmp_path)

    audio_path = store.save_audio(b"wav-data")

    assert store.next_audio_path() == audio_path
    assert store.load_audio(audio_path) == b"wav-data"
    assert store.pending_counts() == (1, 0)

    store.remove_audio(audio_path)

    assert store.next_audio_path() is None
    assert store.pending_counts() == (0, 0)


def test_pending_store_saves_and_loads_transcript(tmp_path: Path) -> None:
    store = PendingDictationStore(base_dir=tmp_path)

    transcript_path = store.save_transcript("Привет!")

    assert store.next_transcript_path() == transcript_path
    assert store.load_transcript(transcript_path) == "Привет!"
    assert store.pending_counts() == (0, 1)

    store.remove_transcript(transcript_path)

    assert store.next_transcript_path() is None
    assert store.pending_counts() == (0, 0)
