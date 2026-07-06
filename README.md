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

Say the wake word, then your command — or say it all in one breath:

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
