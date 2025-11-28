import logging
import threading
from tkinter import BOTH, END, LEFT, RIGHT, Y, Button, Frame, Label, Scrollbar, Text, Tk, DoubleVar
from tkinter import ttk

import numpy as np
from PIL import Image, ImageGrab, ImageTk
from selenium.webdriver.remote.webdriver import WebDriver

from automation.browser import create_driver
from automation.workflows import (
    fill_login_form,
    refresh_reading_transcript,
    run_quiz_assistant,
    _get_ocr_reader,
)
from ai.remote_client import RemoteLLMClient
from config.settings import AppConfig, load_config


class TkApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("SLZ Book Reader Controller")

        self.config: AppConfig = load_config()
        self.driver: WebDriver | None = None
        self._stop_reading: bool = False
        self.progress_var = DoubleVar(value=0.0)
        self.page_images: list[Image.Image] = []
        self.page_texts: list[str] = []
        self._last_image_tk: ImageTk.PhotoImage | None = None
        self.thumb_images: list[ImageTk.PhotoImage] = []

        self._setup_logging()
        self._build_ui()

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )

    def _build_ui(self) -> None:
        button_frame = Frame(self.root)
        button_frame.pack(fill="x", padx=8, pady=8)

        self.launch_button = Button(
            button_frame,
            text="1. Launch SLZ / Login",
            command=self.on_launch,
        )
        self.launch_button.pack(side=LEFT, padx=4)

        self.fill_login_button = Button(
            button_frame,
            text="Fill Login Form",
            command=self.on_fill_login,
        )
        self.fill_login_button.pack(side=LEFT, padx=4)

        self.paste_button = Button(
            button_frame,
            text="Paste Screenshot",
            command=self.on_paste_screenshot,
        )
        self.paste_button.pack(side=LEFT, padx=4)

        self.read_button = Button(
            button_frame,
            text="2. Transcribe Screenshots",
            command=self.on_read,
        )
        self.read_button.pack(side=LEFT, padx=4)

        self.stop_read_button = Button(
            button_frame,
            text="Stop Auto-Reading",
            command=self.on_stop_read,
        )
        self.stop_read_button.pack(side=LEFT, padx=4)

        self.transcript_button = Button(
            button_frame,
            text="Update Transcript",
            command=self.on_update_transcript,
        )
        self.transcript_button.pack(side=LEFT, padx=4)

        self.quiz_button = Button(
            button_frame,
            text="3. Start Quiz Assistant",
            command=self.on_quiz,
        )
        self.quiz_button.pack(side=LEFT, padx=4)

        self.exit_button = Button(
            button_frame,
            text="Exit",
            command=self.on_exit,
        )
        self.exit_button.pack(side=RIGHT, padx=4)

        self.status_label = Label(self.root, text="Ready.", anchor="w")
        self.status_label.pack(fill="x", padx=8)

        progress_frame = Frame(self.root)
        progress_frame.pack(fill="x", padx=8, pady=(0, 4))

        Label(progress_frame, text="Reading progress:").pack(side=LEFT)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            length=200,
            maximum=100,
            variable=self.progress_var,
        )
        self.progress_bar.pack(side=LEFT, padx=(8, 0), fill="x", expand=True)

        self.image_label = Label(self.root, text="No screenshots pasted yet.", anchor="w")
        self.image_label.pack(fill="x", padx=8, pady=(0, 4))

        self.thumb_frame = Frame(self.root)
        self.thumb_frame.pack(fill="x", padx=8, pady=(0, 4))

        text_frame = Frame(self.root)
        text_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        self.log_text = Text(text_frame, height=12, state="disabled")
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)

        scroll = Scrollbar(text_frame, command=self.log_text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=scroll.set)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(END, message + "\n")
        self.log_text.see(END)
        self.log_text.configure(state="disabled")
        self.status_label.configure(text=message)

    def _set_progress(self, fraction: float) -> None:
        value = max(0.0, min(1.0, fraction)) * 100.0

        def _update() -> None:
            self.progress_var.set(value)

        self.root.after(0, _update)

    def _show_last_image(self, image: Image.Image) -> None:
        max_w, max_h = 320, 240
        w, h = image.size
        scale = min(max_w / float(w), max_h / float(h), 1.0)
        if scale < 1.0:
            display = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        else:
            display = image
        self._last_image_tk = ImageTk.PhotoImage(display)
        self.image_label.configure(image=self._last_image_tk, text="")

    def on_paste_screenshot(self) -> None:
        try:
            data = ImageGrab.grabclipboard()
        except Exception as exc:  # noqa: BLE001
            self.log(f"Could not read image from clipboard: {exc}")
            return

        if data is None:
            self.log("Clipboard does not contain an image.")
            return

        image: Image.Image | None = None
        if isinstance(data, Image.Image):
            image = data
        elif isinstance(data, list) and data:
            try:
                image = Image.open(data[0])
            except Exception as exc:  # noqa: BLE001
                self.log(f"Could not open image from clipboard file: {exc}")
                return

        if image is None:
            self.log("Clipboard content is not an image.")
            return

        image = image.convert("RGB")
        self.page_images.append(image)
        index = len(self.page_images)
        self._show_last_image(image)
        self.log(f"Pasted page screenshot #{index} ({image.width}x{image.height}).")

        # Also add a small thumbnail to the thumbnail strip so all pasted
        # screenshots are visible in the UI.
        thumb = image.copy()
        thumb.thumbnail((96, 96), Image.LANCZOS)
        thumb_tk = ImageTk.PhotoImage(thumb)
        self.thumb_images.append(thumb_tk)
        lbl = Label(self.thumb_frame, image=thumb_tk)
        lbl.pack(side=LEFT, padx=2, pady=2)

    def log(self, message: str) -> None:
        logging.info(message)

        def _update() -> None:
            self._append_log(message)

        self.root.after(0, _update)

    def _run_in_background(self, func) -> None:
        def _wrapper() -> None:
            try:
                func()
            except Exception as exc:  # noqa: BLE001
                self.log(f"Error: {exc}")

        thread = threading.Thread(target=_wrapper, daemon=True)
        thread.start()

    def on_launch(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Initializing Chrome WebDriver...")
                self.driver = create_driver(self.config.automation)
                self.log("Chrome WebDriver initialized.")

            self.log(f"Opening SLZ at {self.config.slz.base_url}")
            assert self.driver is not None
            self.driver.get(self.config.slz.base_url)
            self.log(
                "Please log in manually in the Chrome window. "
                "Once you can see your books, open the book reader and then use the other buttons."
            )

        self._run_in_background(task)

    def on_fill_login(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Browser is not running yet. Use 'Launch SLZ / Login' first.")
                return

            self.log(
                "Filling SLZ login form in Chrome using SLZ_USERNAME/SLZ_PASSWORD from environment.",
            )
            assert self.driver is not None
            fill_login_form(self.driver, self.config)

        self._run_in_background(task)

    def on_read(self) -> None:
        def task() -> None:
            if not self.page_images:
                self.log(
                    "No page screenshots have been pasted yet. Use 'Paste Screenshot' first.",
                )
                return

            total = len(self.page_images)
            self.log(f"Starting transcription for {total} pasted screenshots.")
            self._stop_reading = False
            self._set_progress(0.0)

            reader = _get_ocr_reader()
            if reader is None:
                self.log("OCR is not available (easyocr failed to initialize).")
                return

            texts: list[str] = []

            for index, image in enumerate(self.page_images, start=1):
                if self._stop_reading:
                    self.log(
                        "Stop requested; transcription will stop after current page.",
                    )
                    break

                try:
                    img_np = np.array(image)
                except Exception as exc:  # noqa: BLE001
                    self.log(f"Failed to prepare image {index} for OCR: {exc}")
                    text = ""
                else:
                    try:
                        lines = reader.readtext(
                            img_np,
                            detail=0,
                            paragraph=True,
                        ) or []
                        text = "\n".join(
                            line.strip() for line in lines if isinstance(line, str)
                        ).strip()
                    except Exception as exc:  # noqa: BLE001
                        self.log(f"OCR failed for screenshot {index}: {exc}")
                        text = ""

                texts.append(text)

                display_text = (text or "").strip() or "(no text detected)"
                # Log the full transcription for this page (multi-line).
                self.log(f"Transcript page {index}:\n{display_text}")

                self._set_progress(index / float(total))

            self.page_texts = texts
            self.log("Transcription completed for pasted screenshots.")

        self._run_in_background(task)

    def on_stop_read(self) -> None:
        self._stop_reading = True
        self.log("Stop requested for auto-reading; it will stop shortly.")

    def on_update_transcript(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Browser is not running yet. Use 'Launch SLZ / Login' first.")
                return

            self.log(
                "Updating reading transcript overlay for the current page in Chrome.",
            )
            assert self.driver is not None
            page, excerpt = refresh_reading_transcript(self.driver, self.config)
            one_line = (excerpt or "").replace("\n", " ").strip()
            if not one_line:
                one_line_display = "(no text detected)"
            elif len(one_line) > 140:
                one_line_display = one_line[:137] + "..."
            else:
                one_line_display = one_line
            self.log(f"Transcript page {page}: {one_line_display}")

        self._run_in_background(task)

    def on_quiz(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Browser is not running yet. Use 'Launch SLZ / Login' first.")
                return

            self.log(
                "Starting quiz assistant. In Chrome, navigate to the first quiz question."
            )
            llm_client = RemoteLLMClient(self.config.llm)
            assert self.driver is not None
            run_quiz_assistant(self.driver, self.config, llm_client)
            self.log("Quiz assistant finished.")

        self._run_in_background(task)

    def on_exit(self) -> None:
        def task() -> None:
            if self.driver is not None:
                self.log("Closing browser...")
                try:
                    self.driver.quit()
                except Exception:  # noqa: BLE001
                    pass
                self.driver = None
            self.root.after(0, self.root.destroy)

        self._run_in_background(task)


def main() -> None:
    root = Tk()
    app = TkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
