from __future__ import annotations

from typing import Any

import pytest
import requests

from deepgram_stt.deepgram_client import (
    DeepgramClient,
    DeepgramResponseError,
    extract_transcript,
)


def test_extract_transcript_returns_cleaned_text() -> None:
    payload: dict[str, Any] = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": " привет мир ",
                        }
                    ]
                }
            ]
        }
    }

    assert extract_transcript(payload) == "привет мир"


def test_extract_transcript_rejects_invalid_payload() -> None:
    with pytest.raises(DeepgramResponseError):
        extract_transcript({})


def test_transcribe_posts_audio_to_deepgram(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "привет",
                                }
                            ]
                        }
                    ]
                }
            }

    def fake_post(
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
        data: bytes,
        timeout: float,
    ) -> FakeResponse:
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("deepgram_stt.deepgram_client.requests.post", fake_post)

    client = DeepgramClient(api_key="test-key", timeout_seconds=12.0)
    transcript = client.transcribe(b"wav-data")

    assert transcript == "привет"
    assert captured["url"] == "https://api.deepgram.com/v1/listen"
    assert captured["params"]["language"] == "ru"
    assert captured["params"]["model"] == "nova-3"
    assert captured["headers"]["Authorization"] == "Token test-key"
    assert captured["headers"]["Content-Type"] == "audio/wav"
    assert captured["timeout"] == 12.0
    assert captured["data"] == b"wav-data"


def test_transcribe_rejects_empty_audio() -> None:
    client = DeepgramClient(api_key="test-key")

    with pytest.raises(ValueError):
        client.transcribe(b"")


def test_transcribe_retries_request_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"count": 0}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "results": {
                    "channels": [
                        {
                            "alternatives": [
                                {
                                    "transcript": "привет",
                                }
                            ]
                        }
                    ]
                }
            }

    def fake_post(
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
        data: bytes,
        timeout: float,
    ) -> FakeResponse:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise requests.RequestException("temporary network issue")
        return FakeResponse()

    monkeypatch.setattr("deepgram_stt.deepgram_client.requests.post", fake_post)
    monkeypatch.setattr("deepgram_stt.deepgram_client.time.sleep", lambda seconds: None)

    client = DeepgramClient(api_key="test-key", max_retries=3)

    assert client.transcribe(b"wav-data") == "привет"
    assert attempts["count"] == 3
