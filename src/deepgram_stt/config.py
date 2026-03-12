"""Application configuration."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when configuration is invalid."""


def _candidate_env_files() -> list[Path]:
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")

    candidates.append(Path.cwd() / ".env")
    candidates.append(Path(__file__).resolve().parents[2] / ".env")

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)

    return unique_candidates


def load_app_env() -> None:
    """Load .env from the executable folder, current directory, or project root."""
    for env_file in _candidate_env_files():
        if env_file.exists():
            load_dotenv(env_file, override=False)


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ConfigError(f"Invalid boolean value for {name}: {raw_value!r}")


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"Invalid integer value for {name}: {raw_value!r}") from exc

    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero.")

    return value


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ConfigError(f"Invalid float value for {name}: {raw_value!r}") from exc

    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero.")

    return value


@dataclass(slots=True, frozen=True)
class AppConfig:
    """Runtime configuration for the STT app."""

    deepgram_api_key: str
    sample_rate: int = 16_000
    channels: int = 1
    model: str = "nova-3"
    language: str = "ru"
    append_trailing_space: bool = True
    transcription_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load config from environment and .env file."""
        load_app_env()

        api_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "DEEPGRAM_API_KEY is missing. Copy .env.example to .env and set your key."
            )

        return cls(
            deepgram_api_key=api_key,
            sample_rate=_read_int("STT_SAMPLE_RATE", 16_000),
            channels=_read_int("STT_CHANNELS", 1),
            model=os.getenv("DEEPGRAM_MODEL", "nova-3").strip() or "nova-3",
            language=os.getenv("DEEPGRAM_LANGUAGE", "ru").strip() or "ru",
            append_trailing_space=_read_bool("STT_APPEND_TRAILING_SPACE", True),
            transcription_timeout_seconds=_read_float("STT_TIMEOUT_SECONDS", 60.0),
        )
