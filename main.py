"""BOSS BABY - entry point: opens the HUD window and starts the assistant."""

import faulthandler
import os

import webview

from assistant import Assistant

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# dump all thread stacks to the log periodically so hangs are diagnosable
_fh = open(os.path.join(BASE_DIR, "bossbaby.log"), "a", encoding="utf-8")
faulthandler.enable(file=_fh)
faulthandler.dump_traceback_later(15, repeat=True, file=_fh)


class Api:
    """Functions the HUD buttons can call.

    The window reference MUST stay underscore-private: pywebview converts
    every public attribute of this object into a JS proxy, and walking the
    Window object deadlocks window creation with a COM threading error.
    """

    def __init__(self):
        self._window = None

    def close(self):
        self._window.destroy()
        os._exit(0)

    def minimize(self):
        self._window.minimize()


def main():
    api = Api()
    window = webview.create_window(
        "BOSS BABY",
        os.path.join(BASE_DIR, "ui", "index.html"),
        js_api=api,
        width=460,
        height=700,
        frameless=True,
        on_top=True,
        background_color="#03060c",
    )
    api.window = window
    assistant = Assistant(window)
    webview.start(assistant.run)


if __name__ == "__main__":
    main()
