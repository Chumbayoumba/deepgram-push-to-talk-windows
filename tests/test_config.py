from __future__ import annotations

from pathlib import Path

import pytest

from deepgram_stt.config import AppConfig, ConfigError, _candidate_env_files


def test_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("deepgram_stt.config._candidate_env_files", lambda: [])
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    with pytest.raises(ConfigError):
        AppConfig.from_env()


def test_from_env_reads_custom_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    monkeypatch.setenv("STT_SAMPLE_RATE", "44100")
    monkeypatch.setenv("STT_CHANNELS", "2")
    monkeypatch.setenv("DEEPGRAM_MODEL", "nova-3")
    monkeypatch.setenv("DEEPGRAM_LANGUAGE", "ru")
    monkeypatch.setenv("STT_APPEND_TRAILING_SPACE", "false")
    monkeypatch.setenv("STT_TIMEOUT_SECONDS", "12.5")

    config = AppConfig.from_env()

    assert config.deepgram_api_key == "test-key"
    assert config.sample_rate == 44_100
    assert config.channels == 2
    assert config.append_trailing_space is False
    assert config.transcription_timeout_seconds == 12.5


def test_candidate_env_files_prioritize_executable_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    exe_dir = tmp_path / "dist"
    exe_dir.mkdir()
    current_dir = tmp_path / "cwd"
    current_dir.mkdir()

    monkeypatch.chdir(current_dir)
    monkeypatch.setattr("deepgram_stt.config.sys.frozen", True, raising=False)
    monkeypatch.setattr("deepgram_stt.config.sys.executable", str(exe_dir / "app.exe"))

    candidates = _candidate_env_files()

    assert candidates[0] == exe_dir / ".env"
    assert current_dir / ".env" in candidates
