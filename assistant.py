"""BOSS BABY - the brain: wake word, speech-to-text, Gemini, actions, text-to-speech."""

import asyncio
import ctypes
import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import webbrowser

import requests

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_ALIASES = {
    "file explorer": "explorer",
    "explorer": "explorer",
    "files": "explorer",
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "settings": "ms-settings:",
    "camera": "microsoft.windows.camera:",
    "paint": "mspaint",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "wt",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "code": "code",
    "spotify": "spotify:",
    "whatsapp": "whatsapp:",
    "task manager": "taskmgr",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "snipping tool": "snippingtool",
}

SYSTEM_PROMPT = """You are BOSS BABY, a voice assistant running on the user's Windows 11 PC, \
styled after Jarvis from Iron Man. Personality: confident, witty, loyal, and brief. \
Address the user as "Boss".

You MUST reply with ONLY a JSON object in this exact shape:
{"say": "<short spoken reply>", "actions": [{"type": "<action>", "target": "<target>"}]}

Available action types:
- "open_app"     target = app name, e.g. "notepad", "calc", "chrome", "explorer", "code", "spotify", "word"
- "open_url"     target = a full URL starting with https://
- "search_web"   target = search query (opens Google results)
- "play_youtube" target = search query (opens YouTube results)
- "open_path"    target = a Windows file or folder path, e.g. "C:\\Users\\Admin\\Desktop"
- "lock_pc"      locks the computer, target = ""

If no action is needed (a question, chit-chat), use "actions": [].
You may return multiple actions when the request needs them.

Rules for "say":
- 1-2 short sentences of natural speech. It will be read aloud by text-to-speech.
- No markdown, no emojis, no lists, no code.
- When you perform an action, confirm it briefly, e.g. "Opening Chrome for you, Boss."
"""

WAKE_HINT = 'Say "Boss Baby" to wake me'
CONVERSE_HINT = "Listening... say 'go to sleep' when done"

STOP_PHRASES = (
    "go to sleep",
    "go back to sleep",
    "that's all",
    "that is all",
    "stop listening",
    "goodbye",
    "good bye",
    "thank you boss baby",
    "thanks boss baby",
)


class RateLimited(Exception):
    pass


def load_config():
    with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
        return json.load(f)


class Assistant:
    def __init__(self, window):
        self.window = window
        cfg = load_config()
        self.provider = cfg.get("provider", "nvidia")
        self.nvidia = cfg.get("nvidia", {})
        self.gemini = cfg.get("gemini", {})
        self.voice = cfg.get("voice", "en-GB-RyanNeural")
        self.wake_words = [w.lower() for w in cfg.get("wake_words", ["boss baby"])]
        self.history = []  # list of {"role": "user"|"assistant", "text": str}

    # ---------- UI bridge ----------

    def set_state(self, state, status="", user=None, reply=None):
        js = "window.bb && bb.setState({}, {}, {}, {})".format(
            json.dumps(state), json.dumps(status), json.dumps(user), json.dumps(reply)
        )
        try:
            self.window.evaluate_js(js)
        except Exception:
            pass

    # ---------- LLM brain ----------

    def ask_llm(self, user_text):
        self.history.append({"role": "user", "text": user_text})
        self.history = self.history[-20:]
        try:
            if self.provider == "gemini":
                raw = self._call_gemini()
            else:
                raw = self._call_nvidia()
        except RateLimited:
            self.history.pop()
            return {"say": "I'm being rate limited, Boss. Give me a minute and try again.", "actions": []}
        except Exception:
            self.history.pop()
            return {"say": "I couldn't reach my brain, Boss. Check the internet connection.", "actions": []}

        self.history.append({"role": "assistant", "text": raw})
        return self._parse_reply(raw)

    def _call_nvidia(self):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in self.history:
            role = "assistant" if turn["role"] == "assistant" else "user"
            messages.append({"role": role, "content": turn["text"]})
        resp = requests.post(
            self.nvidia.get("base_url", "https://integrate.api.nvidia.com/v1") + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.nvidia['api_key']}",
                "Accept": "text/event-stream",
            },
            json={
                "model": self.nvidia.get("model", "z-ai/glm-5.2"),
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096,
                "stream": True,
            },
            timeout=(10, 300),
            stream=True,
        )
        if resp.status_code == 429:
            raise RateLimited()
        resp.raise_for_status()
        parts = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                choices = json.loads(data).get("choices") or []
                chunk = choices[0].get("delta", {}).get("content") if choices else None
            except (json.JSONDecodeError, KeyError):
                continue
            if chunk:
                parts.append(chunk)
        return "".join(parts)

    def _call_gemini(self):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini.get('model', 'gemini-2.5-flash')}:generateContent"
            f"?key={self.gemini['api_key']}"
        )
        contents = [
            {"role": "model" if t["role"] == "assistant" else "user", "parts": [{"text": t["text"]}]}
            for t in self.history
        ]
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.7,
                "maxOutputTokens": 400,
                # no thinking: replies must be instant, not deliberate
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        resp = requests.post(url, json=body, timeout=30)
        if resp.status_code == 429:
            raise RateLimited()
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    @staticmethod
    def _parse_reply(raw):
        text = raw.strip()
        # reasoning models may prepend <think>...</think>
        if "</think>" in text:
            text = text.split("</think>", 1)[1].strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        # tolerate chatter around the JSON object
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                if isinstance(data, dict) and "say" in data:
                    data.setdefault("actions", [])
                    return data
            except json.JSONDecodeError:
                pass
        return {"say": text[:300], "actions": []}

    # ---------- Actions ----------

    def run_actions(self, actions):
        for action in actions or []:
            try:
                self._run_action(action.get("type", ""), str(action.get("target", "")))
            except Exception:
                pass

    def _run_action(self, kind, target):
        if kind == "open_app":
            alias = APP_ALIASES.get(target.lower().strip(), target)
            subprocess.Popen(f'start "" "{alias}"', shell=True)
        elif kind == "open_url":
            webbrowser.open(target)
        elif kind == "search_web":
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(target))
        elif kind == "play_youtube":
            webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote(target))
        elif kind == "open_path":
            os.startfile(target)
        elif kind == "lock_pc":
            ctypes.windll.user32.LockWorkStation()

    # ---------- Voice output ----------

    def speak(self, text):
        if not text:
            return
        try:
            import hashlib

            import edge_tts
            import pygame

            # cache generated audio so repeated phrases play instantly
            cache_dir = os.path.join(tempfile.gettempdir(), "bossbaby_tts")
            os.makedirs(cache_dir, exist_ok=True)
            key = hashlib.md5(f"{self.voice}|{text}".encode("utf-8")).hexdigest()
            path = os.path.join(cache_dir, key + ".mp3")
            if not os.path.exists(path):
                asyncio.run(edge_tts.Communicate(text, self.voice).save(path))
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
        except Exception:
            pass

    # ---------- Voice input ----------

    def listen(self, source, timeout=6, phrase_limit=8):
        sr = self.sr
        try:
            audio = self.rec.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            return self.rec.recognize_google(audio)
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            return None
        except sr.RequestError:
            self.set_state("error", "Speech service unreachable, retrying...")
            time.sleep(2)
            return None

    # ---------- Main loop ----------

    def run(self):
        time.sleep(2)  # let the UI finish loading
        try:
            import pygame
            import speech_recognition as sr

            pygame.mixer.init()
            self.sr = sr
            self.rec = sr.Recognizer()
            mic = sr.Microphone()
        except Exception as exc:
            self.set_state("error", f"Startup failed: {exc}")
            return

        with mic as source:
            self.set_state("idle", "Calibrating microphone...")
            self.rec.adjust_for_ambient_noise(source, duration=1)
            # lock the threshold: dynamic mode drifts up when the assistant's
            # own voice plays through the speakers, making it go deaf
            self.rec.dynamic_energy_threshold = False
            self.rec.energy_threshold = max(self.rec.energy_threshold, 250)
            # snappier end-of-phrase detection (defaults: 0.8 / 0.5)
            self.rec.pause_threshold = 0.6
            self.rec.non_speaking_duration = 0.4
            self.set_state("idle", WAKE_HINT)

            while True:
                heard = self.listen(source, timeout=None, phrase_limit=7)
                if not heard:
                    continue
                low = heard.lower()
                wake = next((w for w in self.wake_words if w in low), None)
                if not wake:
                    self.set_state("idle", f'Heard "{heard}" - {WAKE_HINT}')
                    continue

                command = low.split(wake, 1)[1].strip(" ,.!?")
                if not command:
                    self.set_state("listening", "Yes, Boss?")
                    self.speak("Yes, Boss?")
                    command = self.listen(source, timeout=7, phrase_limit=10)
                    if not command:
                        self.set_state("idle", WAKE_HINT)
                        continue

                self.handle(command, source)
                self.converse(source)

    def converse(self, source):
        """Conversation mode: keep listening for follow-ups after the first
        command, no wake word needed. Ends after silence or a stop phrase."""
        misses = 0
        while True:
            self.set_state("listening", CONVERSE_HINT)
            heard = self.listen(source, timeout=8, phrase_limit=12)
            if not heard:
                misses += 1
                if misses >= 2:
                    self.set_state("idle", WAKE_HINT)
                    return
                continue
            misses = 0
            low = heard.lower()
            if any(p in low for p in STOP_PHRASES):
                self.set_state("speaking", "Speaking...")
                self.speak("Going back to sleep, Boss. Just call my name.")
                self.set_state("idle", WAKE_HINT)
                return
            # tolerate the wake word being repeated mid-conversation
            wake = next((w for w in self.wake_words if w in low), None)
            if wake:
                rest = low.split(wake, 1)[1].strip(" ,.!?")
                if rest:
                    low = rest
            self.handle(low, source)

    def handle(self, command, source):
        self.set_state("thinking", "Processing...", user=command)
        result = self.ask_llm(command)
        say = result.get("say", "")
        self.run_actions(result.get("actions"))
        self.set_state("speaking", "Speaking...", reply=say)
        self.speak(say)
