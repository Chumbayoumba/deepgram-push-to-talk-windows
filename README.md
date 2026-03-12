# Deepgram Push-to-Talk for Windows

[![CI](https://github.com/Chumbayoumba/deepgram-push-to-talk-windows/actions/workflows/ci.yml/badge.svg)](https://github.com/Chumbayoumba/deepgram-push-to-talk-windows/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Chumbayoumba/deepgram-push-to-talk-windows?style=social)](https://github.com/Chumbayoumba/deepgram-push-to-talk-windows/stargazers)
![Windows](https://img.shields.io/badge/platform-Windows-0078D6)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)
![Deepgram](https://img.shields.io/badge/STT-Deepgram-13EF93)
![Language](https://img.shields.io/badge/language-Russian-DA291C)
![Build](https://img.shields.io/badge/distribution-Standalone%20EXE-6f42c1)

Reliable push-to-talk speech-to-text for Windows using Deepgram.

Hold `Right Shift` to record, release to transcribe, and insert the recognized text into the currently focused app.

[Русская версия](README.ru.md)

## Features

- Global push-to-talk hotkey: hold `Right Shift` to record
- Russian speech recognition via Deepgram (`language=ru`, `model=nova-3`)
- Direct Windows Unicode text input
- Reliable clipboard fallback when direct input cannot start
- Pending queue for failed audio/text, so dictation is not lost
- `F8` replay for pending items
- Standalone `.exe` build with PyInstaller

## Hotkeys

| Hotkey | Action |
| --- | --- |
| `Right Shift` | Hold to record |
| `F8` | Replay the oldest pending dictation item |
| `Ctrl+Alt+F12` | Exit the app |

## Why this project exists

Most dictation utilities either depend on a specific keyboard layout, fail silently on Windows input edge cases, or lose speech when the network fails.

This project is designed to be practical:

- it works as a global push-to-talk tool
- it survives temporary Deepgram/DNS failures
- it keeps pending items on disk until you replay them
- it handles Russian text correctly even if the current keyboard layout is different

## Quick start

### 1. Clone the repository

```powershell
git clone https://github.com/Chumbayoumba/deepgram-push-to-talk-windows.git
cd deepgram-push-to-talk-windows
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

### 3. Configure Deepgram

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
DEEPGRAM_API_KEY=your_deepgram_key_here
```

### 4. Run the app

```powershell
.\.venv\Scripts\python.exe -m deepgram_stt
```

Or use helper scripts:

```powershell
.\install.ps1
.\run.ps1
```

## Build a standalone EXE

```powershell
.\build.ps1
```

Build output:

- `dist\deepgram-stt.exe`
- `dist\.env`

The build script copies your local `.env` next to the executable. The packaged app loads `.env` from the EXE directory first.

## How it works

1. Press and hold `Right Shift`
2. The app records microphone audio using `sounddevice`
3. Release `Right Shift`
4. Audio is sent to Deepgram prerecorded transcription
5. The recognized text is delivered to the active app
6. If delivery or network fails, the app stores the pending item on disk
7. Press `F8` later to replay the oldest pending item

## Reliability model

### Direct typing

The app first tries direct Unicode input using Windows `SendInput`.

### Reliable fallback

If direct typing cannot start, the app falls back to clipboard paste using WinAPI virtual keys, not layout-dependent character typing.

This means:

- Russian or English layout does not matter
- `Caps Lock` does not matter
- fallback input is still reliable in many real-world Windows apps

### Pending queue

If Deepgram or insertion fails, the app stores pending items here:

- Source mode: `.runtime\`
- Packaged EXE mode: `dist\state\`

Types:

- `pending_audio\*.wav` — audio that could not be transcribed
- `pending_transcripts\*.txt` — text that could not be inserted

Replay:

- focus the target app
- press `F8`
- the oldest pending item is retried first

## Troubleshooting

### DNS / Deepgram request failed

If you see a network or name resolution error:

- verify that the PC has Internet access
- verify that `api.deepgram.com` resolves correctly
- try again later
- use `F8` after connectivity is restored

Your dictation is preserved in the pending queue.

### The target app does not receive text

Try this:

- run this app with the same privilege level as the target app
- if the target app is elevated, run this app as Administrator too
- click into the target app before replaying with `F8`

### The app exits unexpectedly

The app no longer exits on plain `Esc`.

Exit is only bound to:

```text
Ctrl + Alt + F12
```

### Keyboard layout or Caps Lock issues

The fallback path is layout-independent and does not depend on the current Russian/English layout or `Caps Lock`.

## Security notes

- No API key is stored in source files
- `.env`, `dist`, `.runtime`, and build artifacts are ignored
- Pending dictation is stored locally on your machine
- Review `dist\state\` before sharing builds or logs publicly

## Development

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Project structure

```text
src\deepgram_stt\        application code
tests\                   pytest coverage
install.ps1              dependency install helper
run.ps1                  local runner
build.ps1                PyInstaller build helper
app_bootstrap.py         EXE entry point
```

## Disclaimer

This project is not affiliated with Deepgram.
