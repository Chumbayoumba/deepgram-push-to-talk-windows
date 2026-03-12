"""Deepgram API client."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import requests


class DeepgramResponseError(ValueError):
    """Raised when Deepgram returns an unexpected payload."""


def extract_transcript(payload: dict[str, Any]) -> str:
    """Extract the main transcript from a Deepgram response."""
    try:
        channels = payload["results"]["channels"]
        alternatives = channels[0]["alternatives"]
        transcript = alternatives[0]["transcript"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepgramResponseError("Unexpected Deepgram response format.") from exc

    if not isinstance(transcript, str):
        raise DeepgramResponseError("Transcript is missing or invalid.")

    return transcript.strip()


@dataclass(slots=True, frozen=True)
class DeepgramClient:
    """Minimal Deepgram prerecorded transcription client."""

    api_key: str
    model: str = "nova-3"
    language: str = "ru"
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    base_url: str = "https://api.deepgram.com/v1/listen"

    def transcribe(self, wav_audio: bytes) -> str:
        """Send WAV audio to Deepgram and return the transcript."""
        if not wav_audio:
            raise ValueError("Audio payload cannot be empty.")

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.base_url,
                    params={
                        "model": self.model,
                        "language": self.language,
                        "punctuate": "true",
                        "smart_format": "true",
                    },
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "audio/wav",
                    },
                    data=wav_audio,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return extract_transcript(response.json())
            except requests.RequestException:
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff_seconds * attempt)

        raise RuntimeError("Deepgram transcription exhausted all retries.")
