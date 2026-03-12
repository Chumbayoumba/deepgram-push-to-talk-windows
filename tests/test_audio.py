from __future__ import annotations

import io
import wave
from typing import Any

from deepgram_stt.audio import AudioRecorder


def test_audio_recorder_uses_raw_stream_and_writes_wav(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeStream:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.started = False
            self.stopped = False
            self.closed = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.stopped = True

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr("deepgram_stt.audio.sd.RawInputStream", FakeStream)

    recorder = AudioRecorder(sample_rate=16_000, channels=1)
    recorder.start()

    assert isinstance(recorder._stream, FakeStream)
    assert recorder._stream.started is True
    assert captured["dtype"] == "int16"
    assert captured["samplerate"] == 16_000
    assert captured["channels"] == 1

    callback = captured["callback"]
    callback(b"\x01\x00\x02\x00", 2, None, None)

    wav_bytes = recorder.stop()

    assert recorder._stream is None
    assert wav_bytes is not None

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16_000
        assert wav_file.readframes(2) == b"\x01\x00\x02\x00"
