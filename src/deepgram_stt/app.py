"""Push-to-talk app controller."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

import requests
import sounddevice as sd
from pynput import keyboard

from .audio import AudioRecorder
from .config import AppConfig
from .deepgram_client import DeepgramClient, DeepgramResponseError
from .pending_store import PendingDictationStore
from .text_output import PartialTextInsertError, TextInsertError, UnicodeTyper

LOGGER = logging.getLogger(__name__)


def modifier_name(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
    if key in {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}:
        return "ctrl"
    if key in {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr}:
        return "alt"
    if key in {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}:
        return "shift"
    return None


def is_stop_hotkey(
    key: keyboard.Key | keyboard.KeyCode | None, pressed_modifiers: set[str]
) -> bool:
    return key == keyboard.Key.f12 and {"ctrl", "alt"}.issubset(pressed_modifiers)


@dataclass(slots=True)
class PushToTalkApp:
    """Global Right Shift hotkey controller for dictation."""

    config: AppConfig
    recorder: AudioRecorder = field(init=False)
    deepgram: DeepgramClient = field(init=False)
    output: UnicodeTyper = field(init=False)
    store: PendingDictationStore = field(init=False)
    _state_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _pressed_modifiers: set[str] = field(default_factory=set, init=False, repr=False)
    _recording: bool = field(default=False, init=False, repr=False)
    _busy: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
        )
        self.deepgram = DeepgramClient(
            api_key=self.config.deepgram_api_key,
            model=self.config.model,
            language=self.config.language,
            timeout_seconds=self.config.transcription_timeout_seconds,
        )
        self.output = UnicodeTyper()
        self.store = PendingDictationStore()

    def run(self) -> None:
        """Run the listener until the user presses Esc."""
        pending_audio, pending_transcripts = self.store.pending_counts()
        LOGGER.info(
            "Ready. Hold Right Shift to talk. Press F8 to replay pending dictation. Press Ctrl+Alt+F12 to exit."
        )
        if pending_audio or pending_transcripts:
            LOGGER.warning(
                "Pending items found: %s audio, %s transcripts. Press F8 to replay.",
                pending_audio,
                pending_transcripts,
            )
        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> bool | None:
        self._update_modifier_state(key, pressed=True)

        if is_stop_hotkey(key, self._pressed_modifiers):
            LOGGER.info("Stopping.")
            return False

        if key == keyboard.Key.f8:
            self._start_replay_pending_item()
            return None

        if key != keyboard.Key.shift_r:
            return None

        with self._state_lock:
            if self._busy:
                LOGGER.info("Still processing previous recording.")
                return None
            if self._recording:
                return None
            self._recording = True

        try:
            self.recorder.start()
        except (RuntimeError, sd.PortAudioError) as exc:
            with self._state_lock:
                self._recording = False
            LOGGER.error("Failed to start microphone recording: %s", exc)
            return None

        LOGGER.info("Recording...")
        return None

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        self._update_modifier_state(key, pressed=False)

        if key != keyboard.Key.shift_r:
            return

        with self._state_lock:
            if not self._recording:
                return
            self._recording = False
            self._busy = True

        try:
            wav_audio = self.recorder.stop()
        except (RuntimeError, sd.PortAudioError) as exc:
            LOGGER.error("Failed to stop microphone recording: %s", exc)
            with self._state_lock:
                self._busy = False
            return

        worker = threading.Thread(
            target=self._process_audio,
            args=(wav_audio,),
            daemon=True,
        )
        worker.start()

    def _process_audio(self, wav_audio: bytes | None) -> None:
        final_text: str | None = None
        try:
            if not wav_audio:
                LOGGER.info("No audio captured.")
                return

            LOGGER.info("Transcribing...")
            transcript = self.deepgram.transcribe(wav_audio)

            if not transcript:
                LOGGER.info("No speech detected.")
                return

            final_text = self._prepare_text(transcript)
            delivery_mode = self.output.insert_text(final_text)
            self._log_delivery(final_text, delivery_mode, replayed=False)
        except requests.RequestException as exc:
            self._persist_pending_audio(wav_audio, f"Deepgram request failed: {exc}")
        except DeepgramResponseError as exc:
            self._persist_pending_audio(
                wav_audio, f"Deepgram returned invalid data: {exc}"
            )
        except PartialTextInsertError as exc:
            self._persist_pending_transcript(
                exc.remaining_text, f"Direct text input failed after partial delivery: {exc}"
            )
        except TextInsertError as exc:
            if final_text is None:
                LOGGER.error("Direct text input failed before transcript creation: %s", exc)
            else:
                self._persist_pending_transcript(
                    final_text, f"Direct text input failed: {exc}"
                )
        except ValueError as exc:
            if final_text is None:
                LOGGER.error("Could not insert text: %s", exc)
            else:
                self._persist_pending_transcript(
                    final_text, f"Could not insert text: {exc}"
                )
        finally:
            with self._state_lock:
                self._busy = False

    def _prepare_text(self, transcript: str) -> str:
        cleaned = transcript.strip()
        if self.config.append_trailing_space and cleaned:
            return f"{cleaned} "
        return cleaned

    def _start_replay_pending_item(self) -> None:
        with self._state_lock:
            if self._recording:
                LOGGER.info("Stop recording before replaying pending dictation.")
                return
            if self._busy:
                LOGGER.info("Still processing previous recording.")
                return
            self._busy = True

        worker = threading.Thread(
            target=self._replay_pending_item,
            daemon=True,
        )
        worker.start()

    def _replay_pending_item(self) -> None:
        try:
            transcript_path = self.store.next_transcript_path()
            if transcript_path is not None:
                self._replay_saved_transcript(transcript_path)
                return

            audio_path = self.store.next_audio_path()
            if audio_path is None:
                LOGGER.info("No pending dictation.")
                return

            LOGGER.info("Retrying pending audio: %s", audio_path.name)
            wav_audio = self.store.load_audio(audio_path)
            transcript = self.deepgram.transcribe(wav_audio)

            if not transcript:
                self.store.remove_audio(audio_path)
                LOGGER.info("Pending audio had no speech and was removed: %s", audio_path.name)
                self._log_pending_counts()
                return

            final_text = self._prepare_text(transcript)

            try:
                delivery_mode = self.output.insert_text(final_text)
            except PartialTextInsertError as exc:
                self.store.remove_audio(audio_path)
                self._persist_pending_transcript(
                    exc.remaining_text,
                    f"Recovered transcript failed after partial delivery: {exc}",
                )
                return
            except (TextInsertError, ValueError) as exc:
                self.store.remove_audio(audio_path)
                self._persist_pending_transcript(
                    final_text, f"Recovered transcript could not be inserted: {exc}"
                )
                return

            self.store.remove_audio(audio_path)
            self._log_delivery(final_text, delivery_mode, replayed=True)
            self._log_pending_counts()
        except requests.RequestException as exc:
            LOGGER.error("Pending audio replay failed due to network: %s", exc)
        except DeepgramResponseError as exc:
            LOGGER.error("Pending audio replay returned invalid data: %s", exc)
        finally:
            with self._state_lock:
                self._busy = False

    def _persist_pending_audio(self, wav_audio: bytes | None, message: str) -> None:
        LOGGER.error("%s", message)
        if not wav_audio:
            return

        audio_path = self.store.save_audio(wav_audio)
        LOGGER.warning(
            "Saved pending audio: %s. Restore network and press F8 to replay.",
            audio_path,
        )
        self._log_pending_counts()

    def _persist_pending_transcript(self, text: str, message: str) -> None:
        LOGGER.error("%s", message)
        if not text:
            return

        transcript_path = self.store.save_transcript(text)
        LOGGER.warning(
            "Saved pending transcript: %s. Focus the target app and press F8 to replay.",
            transcript_path,
        )
        self._log_pending_counts()

    def _log_delivery(self, text: str, delivery_mode: str, *, replayed: bool) -> None:
        if delivery_mode == "pasted":
            LOGGER.info(
                "Used reliable paste mode for this dictation. Layout and Caps Lock do not matter."
            )

        verb = "Replayed" if replayed else "Inserted"
        LOGGER.info("%s: %s", verb, text.rstrip())

    def _log_pending_counts(self) -> None:
        pending_audio, pending_transcripts = self.store.pending_counts()
        if pending_audio or pending_transcripts:
            LOGGER.warning(
                "Pending items remaining: %s audio, %s transcripts.",
                pending_audio,
                pending_transcripts,
            )

    def _replay_saved_transcript(self, transcript_path: Path) -> None:
        transcript = self.store.load_transcript(transcript_path)
        if not transcript.strip():
            self.store.remove_transcript(transcript_path)
            LOGGER.warning("Removed empty pending transcript: %s", transcript_path)
            self._log_pending_counts()
            return

        try:
            delivery_mode = self.output.insert_text(transcript)
        except PartialTextInsertError as exc:
            transcript_path.write_text(exc.remaining_text, encoding="utf-8")
            LOGGER.error("Pending transcript replay partially failed: %s", exc)
            LOGGER.warning(
                "Saved remaining transcript back to %s. Focus the target app and press F8 again.",
                transcript_path,
            )
            self._log_pending_counts()
            return
        except (TextInsertError, ValueError) as exc:
            LOGGER.error("Pending transcript replay failed: %s", exc)
            LOGGER.warning(
                "Pending transcript preserved: %s. Focus the target app and press F8 again.",
                transcript_path,
            )
            self._log_pending_counts()
            return

        self.store.remove_transcript(transcript_path)
        self._log_delivery(transcript, delivery_mode, replayed=True)
        self._log_pending_counts()

    def _update_modifier_state(
        self, key: keyboard.Key | keyboard.KeyCode | None, *, pressed: bool
    ) -> None:
        modifier = modifier_name(key)
        if modifier is None:
            return

        if pressed:
            self._pressed_modifiers.add(modifier)
        else:
            self._pressed_modifiers.discard(modifier)
