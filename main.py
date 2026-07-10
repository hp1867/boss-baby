"""BOSS BABY - entry point: opens the HUD window and starts the assistant."""

import os

import webview

from assistant import Assistant

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Api:
    """Functions the HUD buttons can call."""

    def __init__(self):
        self.window = None

    def close(self):
        self.window.destroy()
        os._exit(0)

    def minimize(self):
        self.window.minimize()


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
