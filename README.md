# BOSS BABY 🤖

A Jarvis-style voice assistant for Windows with an Iron Man-inspired HUD.
Say **"Boss Baby"** and it wakes up, listens, answers with a natural voice,
and controls your PC — open apps, search the web, play YouTube, open files.

## Features

- 🎙️ **Wake word** — always listening for "Boss Baby"
- 🧠 **LLM brain** — GLM-5.2 via NVIDIA's free API (Gemini supported as an alternative)
- 🗣️ **Natural voice replies** — Microsoft Edge neural text-to-speech
- ⚡ **PC control** — open apps, websites, files/folders, Google/YouTube search, lock the PC
- 🔵 **Arc-reactor HUD** — glowing interface that pulses while listening, turns amber while thinking, and shows an equalizer while speaking

## Setup

1. Install [Python 3.12](https://www.python.org/downloads/)
2. Copy `config.example.json` to `config.json` and paste your
   [NVIDIA API key](https://build.nvidia.com/) (or a
   [Google Gemini key](https://aistudio.google.com/apikey) with `"provider": "gemini"`)
3. Double-click **`run.bat`** — first run creates a virtual environment and
   installs dependencies automatically

## Usage

Say the wake word once, then just keep talking — after the first command it
stays in **conversation mode** and responds to everything without needing the
wake word again. It goes back to sleep after ~16 seconds of silence, or when
you say "go to sleep" / "that's all" / "goodbye".

Examples:

- "Boss Baby, open Chrome"
- "Boss Baby, search the web for weather in Melbourne"
- "Boss Baby, play some lo-fi beats on YouTube"
- "Boss Baby, open my Desktop folder"
- "Boss Baby, what's the capital of Japan?"
- "Boss Baby, lock my PC"

## Tech stack

| Part | Tool |
|------|------|
| Speech-to-text | Google Web Speech (via `SpeechRecognition`) |
| Brain | GLM-5.2 (NVIDIA API) or Gemini 2.5 Flash |
| Text-to-speech | `edge-tts` neural voices |
| HUD window | `pywebview` (HTML/CSS) |
| Audio playback | `pygame` |

## Notes

- `config.json` holds your API key and is **git-ignored** — never commit it.
- Requires an internet connection (speech recognition, Gemini, and TTS are online services).
- Free-tier Gemini has rate limits; if it says it's rate-limited, wait a minute.

## Automatic GitHub sync

On the configured Windows PC, the **BossBaby GitHub Auto Sync** scheduled task
runs `scripts/auto-sync.ps1` after sign-in and once per minute. When project
files remain unchanged for a 12-second safety window, it creates an
`Auto-commit` snapshot and pushes the current branch to `origin`. If the
network is unavailable, the commit remains local and the next run retries.

The watcher never force-pushes, pauses during merges/rebases, and explicitly
keeps `config.json` out of automatic commits. Its local activity log is stored
at `.git/auto-sync.log`. To reinstall the task after moving the folder, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-auto-sync.ps1
```
