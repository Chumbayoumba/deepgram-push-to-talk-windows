from __future__ import annotations

from pathlib import Path

from pynput import keyboard

from deepgram_stt.app import PushToTalkApp, is_stop_hotkey, modifier_name
from deepgram_stt.config import AppConfig
from deepgram_stt.pending_store import PendingDictationStore
from deepgram_stt.text_output import TextInsertError


def test_modifier_name_maps_common_modifiers() -> None:
    assert modifier_name(keyboard.Key.ctrl_l) == "ctrl"
    assert modifier_name(keyboard.Key.alt_r) == "alt"
    assert modifier_name(keyboard.Key.shift_r) == "shift"
    assert modifier_name(keyboard.Key.f8) is None


def test_is_stop_hotkey_requires_ctrl_alt_f12() -> None:
    assert is_stop_hotkey(keyboard.Key.f12, {"ctrl", "alt"}) is True
    assert is_stop_hotkey(keyboard.Key.f12, {"ctrl"}) is False
    assert is_stop_hotkey(keyboard.Key.esc, {"ctrl", "alt"}) is False


def test_replay_saved_transcript_preserves_file_on_failure(tmp_path: Path) -> None:
    app = PushToTalkApp(AppConfig(deepgram_api_key="test-key"))
    app.store = PendingDictationStore(base_dir=tmp_path)
    transcript_path = app.store.save_transcript("Привет")

    class FailingOutput:
        def insert_text(self, text: str) -> str:
            raise TextInsertError("insertion failed")

    app.output = FailingOutput()

    app._replay_saved_transcript(transcript_path)

    assert transcript_path.exists()
    assert transcript_path.read_text(encoding="utf-8") == "Привет"
