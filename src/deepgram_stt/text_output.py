"""Insert recognized text into the active window."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from dataclasses import dataclass, field

import pyperclip


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL = 0x11
VK_V = 0x56
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)


class TextInsertError(RuntimeError):
    """Raised when text insertion into the target window fails."""


class PartialTextInsertError(TextInsertError):
    """Raised when direct typing fails after part of the text was already sent."""

    def __init__(self, message: str, remaining_text: str) -> None:
        super().__init__(message)
        self.remaining_text = remaining_text


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", INPUT_UNION),
    ]


USER32 = ctypes.WinDLL("user32", use_last_error=True)
SendInput = USER32.SendInput
SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SendInput.restype = wintypes.UINT
GetForegroundWindow = USER32.GetForegroundWindow
GetForegroundWindow.argtypes = ()
GetForegroundWindow.restype = wintypes.HWND


@dataclass(slots=True)
class ClipboardPaster:
    """Fallback paste mode when direct Unicode typing cannot start."""

    restore_delay_seconds: float = 0.15

    def insert_text(self, text: str) -> None:
        if not text:
            raise ValueError("Text cannot be empty.")

        previous_text: str | None = None
        restore_clipboard = False

        try:
            previous_text = pyperclip.paste()
            restore_clipboard = True
        except pyperclip.PyperclipException:
            previous_text = None

        pyperclip.copy(text)
        time.sleep(0.05)
        self._send_virtual_key(VK_CONTROL, key_up=False)
        self._send_virtual_key(VK_V, key_up=False)
        self._send_virtual_key(VK_V, key_up=True)
        self._send_virtual_key(VK_CONTROL, key_up=True)

        if restore_clipboard and previous_text is not None:
            time.sleep(self.restore_delay_seconds)
            pyperclip.copy(previous_text)

    def _send_virtual_key(self, virtual_key: int, *, key_up: bool) -> None:
        flags = KEYEVENTF_KEYUP if key_up else 0
        keyboard_input = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=virtual_key,
                wScan=0,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            ),
        )
        ctypes.set_last_error(0)
        sent = SendInput(1, ctypes.byref(keyboard_input), ctypes.sizeof(INPUT))
        if sent != 1:
            error_code = ctypes.get_last_error()
            raise TextInsertError(
                f"Clipboard paste shortcut failed for virtual key 0x{virtual_key:02X} (winerror={error_code})."
            )


@dataclass(slots=True)
class UnicodeTyper:
    """Type Unicode text into the current foreground window."""

    clipboard_restore_delay_seconds: float = 0.15
    _fallback_paster: ClipboardPaster = field(init=False, repr=False)
    _clipboard_only_mode: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._fallback_paster = ClipboardPaster(
            restore_delay_seconds=self.clipboard_restore_delay_seconds
        )

    def insert_text(self, text: str) -> str:
        """Insert text and return the delivery mode."""
        if not text:
            raise ValueError("Text cannot be empty.")

        if not GetForegroundWindow():
            raise TextInsertError("No active foreground window.")

        if self._clipboard_only_mode:
            self._fallback_paster.insert_text(text)
            return "pasted"

        for index, character in enumerate(text):
            try:
                for code_unit in self._utf16_code_units(character):
                    self._send_unicode_code_unit(code_unit)
            except TextInsertError as exc:
                self._clipboard_only_mode = True
                if index == 0:
                    try:
                        self._fallback_paster.insert_text(text)
                    except pyperclip.PyperclipException as fallback_exc:
                        raise TextInsertError(
                            "Direct typing could not start and clipboard fallback failed."
                        ) from fallback_exc
                    return "pasted"

                raise PartialTextInsertError(
                    "Direct typing started but failed mid-text; the remaining text was preserved.",
                    text[index:],
                ) from exc

        return "typed"

    def _send_unicode_code_unit(self, code_unit: int) -> None:
        key_down = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=0,
                wScan=code_unit,
                dwFlags=KEYEVENTF_UNICODE,
                time=0,
                dwExtraInfo=0,
            ),
        )
        key_up = INPUT(
            type=INPUT_KEYBOARD,
            ki=KEYBDINPUT(
                wVk=0,
                wScan=code_unit,
                dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                time=0,
                dwExtraInfo=0,
            ),
        )

        inputs = (INPUT * 2)(key_down, key_up)
        ctypes.set_last_error(0)
        sent = SendInput(2, inputs, ctypes.sizeof(INPUT))
        if sent != 2:
            error_code = ctypes.get_last_error()
            raise TextInsertError(
                f"SendInput failed for code unit 0x{code_unit:04X} (winerror={error_code})."
            )

    def _utf16_code_units(self, text: str) -> list[int]:
        encoded = text.encode("utf-16-le")
        return [
            int.from_bytes(encoded[index : index + 2], byteorder="little")
            for index in range(0, len(encoded), 2)
        ]
