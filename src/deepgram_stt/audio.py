"""Microphone recording helpers."""

from __future__ import annotations

import io
import logging
import threading
import wave
from dataclasses import dataclass, field

import sounddevice as sd

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AudioRecorder:
    """Capture audio from the default microphone while the hotkey is held."""

    sample_rate: int = 16_000
    channels: int = 1
    _chunks: list[bytes] = field(default_factory=list, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _stream: sd.RawInputStream | None = field(default=None, init=False, repr=False)
    _recording: bool = field(default=False, init=False, repr=False)

    def start(self) -> None:
        """Start recording from the default microphone."""
        with self._lock:
            if self._recording:
                raise RuntimeError("Recorder is already running.")

            self._chunks.clear()
            stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=self._on_audio,
            )
            stream.start()
            self._stream = stream
            self._recording = True

    def stop(self) -> bytes | None:
        """Stop recording and return the captured WAV bytes."""
        with self._lock:
            if not self._recording or self._stream is None:
                raise RuntimeError("Recorder is not running.")

            stream = self._stream
            self._stream = None
            self._recording = False

        stream.stop()
        stream.close()

        with self._lock:
            raw_audio = b"".join(self._chunks)
            self._chunks.clear()

        if not raw_audio:
            return None

        return self._encode_wav(raw_audio)

    def _on_audio(self, indata, frames: int, time_info, status: sd.CallbackFlags) -> None:
        if status:
            LOGGER.warning("Audio callback status: %s", status)

        with self._lock:
            if self._recording:
                self._chunks.append(bytes(indata))

    def _encode_wav(self, raw_audio: bytes) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(raw_audio)
        return buffer.getvalue()
