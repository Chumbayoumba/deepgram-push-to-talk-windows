from __future__ import annotations

import ctypes

import pytest

from deepgram_stt.text_output import (
    HARDWAREINPUT,
    INPUT,
    INPUT_UNION,
    KEYBDINPUT,
    MOUSEINPUT,
    PartialTextInsertError,
    UnicodeTyper,
)


def test_unicode_typer_sends_all_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_calls: list[tuple[int, object, int]] = []

    def fake_send_input(count: int, inputs, size: int) -> int:
        sent_calls.append((count, inputs, size))
        return count

    monkeypatch.setattr("deepgram_stt.text_output.GetForegroundWindow", lambda: 1)
    monkeypatch.setattr("deepgram_stt.text_output.SendInput", fake_send_input)

    typer = UnicodeTyper()
    delivery_mode = typer.insert_text("Пр!")

    assert delivery_mode == "typed"
    assert len(sent_calls) == 3
    first_inputs = sent_calls[0][1]
    assert first_inputs[0].ki.wScan == ord("П")
    assert first_inputs[0].ki.dwFlags & 0x0004
    assert first_inputs[1].ki.dwFlags & 0x0002


def test_input_union_size_matches_largest_winapi_member() -> None:
    assert ctypes.sizeof(INPUT_UNION) == max(
        ctypes.sizeof(MOUSEINPUT),
        ctypes.sizeof(KEYBDINPUT),
        ctypes.sizeof(HARDWAREINPUT),
    )
    assert ctypes.sizeof(INPUT) >= ctypes.sizeof(INPUT_UNION)


def test_unicode_typer_rejects_empty_text() -> None:
    typer = UnicodeTyper()

    with pytest.raises(ValueError):
        typer.insert_text("")


def test_unicode_typer_uses_clipboard_fallback_if_first_key_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_calls: list[str] = []

    monkeypatch.setattr("deepgram_stt.text_output.GetForegroundWindow", lambda: 1)
    monkeypatch.setattr("deepgram_stt.text_output.SendInput", lambda count, inputs, size: 0)
    monkeypatch.setattr(
        "deepgram_stt.text_output.ClipboardPaster.insert_text",
        lambda self, text: fallback_calls.append(text),
    )

    typer = UnicodeTyper()
    delivery_mode = typer.insert_text("A")

    assert delivery_mode == "pasted"
    assert fallback_calls == ["A"]


def test_unicode_typer_stays_in_clipboard_mode_after_first_direct_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_calls: list[str] = []

    monkeypatch.setattr("deepgram_stt.text_output.GetForegroundWindow", lambda: 1)
    monkeypatch.setattr("deepgram_stt.text_output.SendInput", lambda count, inputs, size: 0)
    monkeypatch.setattr(
        "deepgram_stt.text_output.ClipboardPaster.insert_text",
        lambda self, text: fallback_calls.append(text),
    )

    typer = UnicodeTyper()
    assert typer.insert_text("A") == "pasted"
    assert typer.insert_text("B") == "pasted"

    assert fallback_calls == ["A", "B"]


def test_unicode_typer_raises_if_sendinput_fails_after_partial_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    def fake_send_input(count: int, inputs, size: int) -> int:
        calls["count"] += 1
        if calls["count"] == 1:
            return count
        return 0

    monkeypatch.setattr("deepgram_stt.text_output.GetForegroundWindow", lambda: 1)
    monkeypatch.setattr("deepgram_stt.text_output.SendInput", fake_send_input)

    typer = UnicodeTyper()

    with pytest.raises(PartialTextInsertError) as exc_info:
        typer.insert_text("AB")

    assert exc_info.value.remaining_text == "B"
