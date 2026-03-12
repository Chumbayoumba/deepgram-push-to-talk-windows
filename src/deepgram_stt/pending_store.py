"""Persistent storage for pending dictation items."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _default_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "state"

    return Path(__file__).resolve().parents[2] / ".runtime"


@dataclass(slots=True)
class PendingDictationStore:
    """Persist audio and transcript items so dictation is never silently lost."""

    base_dir: Path = field(default_factory=_default_runtime_dir)
    audio_dir: Path = field(init=False)
    transcript_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.audio_dir = self.base_dir / "pending_audio"
        self.transcript_dir = self.base_dir / "pending_transcripts"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_dir.mkdir(parents=True, exist_ok=True)

    def save_audio(self, wav_audio: bytes) -> Path:
        path = self.audio_dir / self._new_name(".wav")
        path.write_bytes(wav_audio)
        return path

    def next_audio_path(self) -> Path | None:
        return self._next_path(self.audio_dir, "*.wav")

    def load_audio(self, path: Path) -> bytes:
        return path.read_bytes()

    def remove_audio(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def save_transcript(self, text: str) -> Path:
        path = self.transcript_dir / self._new_name(".txt")
        path.write_text(text, encoding="utf-8")
        return path

    def next_transcript_path(self) -> Path | None:
        return self._next_path(self.transcript_dir, "*.txt")

    def load_transcript(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def remove_transcript(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def pending_counts(self) -> tuple[int, int]:
        audio_count = sum(1 for _ in self.audio_dir.glob("*.wav"))
        transcript_count = sum(1 for _ in self.transcript_dir.glob("*.txt"))
        return audio_count, transcript_count

    def _new_name(self, suffix: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        return f"{timestamp}_{uuid4().hex[:8]}{suffix}"

    def _next_path(self, directory: Path, pattern: str) -> Path | None:
        candidates = sorted(directory.glob(pattern))
        if not candidates:
            return None
        return candidates[0]
