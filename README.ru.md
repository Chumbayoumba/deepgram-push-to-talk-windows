# Deepgram Push-to-Talk для Windows

Надёжная push-to-talk утилита для speech-to-text на Windows с Deepgram.

Зажал `Right Shift` — запись. Отпустил — распознавание и ввод текста в активное окно.

[English README](README.md)

## Возможности

- глобальный hotkey для записи
- русский язык через Deepgram (`language=ru`, `model=nova-3`)
- прямой Unicode-ввод в активное окно
- надёжный fallback через paste, если прямой ввод не стартует
- очередь pending-элементов, чтобы диктовка не терялась
- повтор pending через `F8`
- сборка standalone `.exe`

## Горячие клавиши

| Клавиша | Действие |
| --- | --- |
| `Right Shift` | Удерживать для записи |
| `F8` | Повторить самый старый pending item |
| `Ctrl+Alt+F12` | Закрыть приложение |

## Быстрый старт

```powershell
git clone https://github.com/Chumbayoumba/deepgram-push-to-talk-windows.git
cd deepgram-push-to-talk-windows
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
Copy-Item .env.example .env
```

В `.env`:

```env
DEEPGRAM_API_KEY=your_deepgram_key_here
```

Запуск:

```powershell
.\run.ps1
```

Или:

```powershell
.\.venv\Scripts\python.exe -m deepgram_stt
```

## Сборка `.exe`

```powershell
.\build.ps1
```

После сборки:

- `dist\deepgram-stt.exe`
- `dist\.env`

## Как это работает

1. Удерживаешь `Right Shift`
2. Идёт запись микрофона
3. Отпускаешь `Right Shift`
4. Аудио уходит в Deepgram
5. Текст вставляется в активное приложение
6. Если сеть или ввод упали, данные сохраняются локально
7. Потом можно нажать `F8` и повторить pending item

## Надёжность

### Прямой ввод

Сначала приложение пытается печатать через Windows `SendInput`.

### Fallback

Если прямой ввод не стартует, включается fallback через clipboard paste с WinAPI virtual keys.

То есть fallback не зависит от:

- русской или английской раскладки
- `Caps Lock`

### Pending queue

Если не сработала сеть или вставка, данные не теряются:

- в source-режиме: `.runtime\`
- в `.exe`-режиме: `dist\state\`

Типы:

- `pending_audio\*.wav`
- `pending_transcripts\*.txt`

## Если что-то пошло не так

### Ошибка сети / DNS

Если Deepgram недоступен:

- запись сохранится локально
- после восстановления сети нажми `F8`

### Текст не входит в нужное окно

Проверь:

- окно действительно в фокусе
- приложение STT запущено с тем же уровнем прав, что и целевое окно
- если цель запущена как Administrator, STT тоже лучше запускать как Administrator

### Приложение само закрывается

Теперь plain `Esc` приложение не закрывает.

Выход только по:

```text
Ctrl + Alt + F12
```

## Безопасность

- ключ Deepgram не хранится в исходниках
- `.env`, `dist`, `.runtime` и build-артефакты не публикуются
- перед публикацией репозитория нужно дополнительно проверять, что ключ не попал в коммиты или release-артефакты
