import logging
import threading
import re
from tkinter import BOTH, END, LEFT, RIGHT, Y, Button, Frame, Label, Scrollbar, Text, Tk, DoubleVar
from tkinter import ttk

import numpy as np
from PIL import Image, ImageGrab, ImageTk
from selenium.webdriver.remote.webdriver import WebDriver

from automation.browser import create_driver
from automation.workflows import (
    fill_login_form,
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
        self._book_transcribing: bool = False
        self.progress_var = DoubleVar(value=0.0)
        self.page_images: list[Image.Image] = []
        self.page_texts: list[str] = []
        self.quiz_image: Image.Image | None = None
        self.quiz_text: str | None = None
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
            text="Paste BOOK Screenshot",
            command=self.on_paste_screenshot,
        )
        self.paste_button.pack(side=LEFT, padx=4)

        self.read_button = Button(
            button_frame,
            text="2. Transcribe Book Screenshots",
            command=self.on_read,
        )
        self.read_button.pack(side=LEFT, padx=4)

        self.paste_quiz_button = Button(
            button_frame,
            text="Paste QUIZ Screenshot",
            command=self.on_paste_quiz_screenshot,
        )
        self.paste_quiz_button.pack(side=LEFT, padx=4)

        self.transcribe_quiz_button = Button(
            button_frame,
            text="Transcribe Quiz Screenshot",
            command=self.on_transcribe_quiz,
        )
        self.transcribe_quiz_button.pack(side=LEFT, padx=4)

        self.quiz_button = Button(
            button_frame,
            text="3. Answer Quiz from Book",
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

        Label(progress_frame, text="Book transcription progress:").pack(side=LEFT)
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

    def _grab_image_from_clipboard(self) -> Image.Image | None:
        try:
            data = ImageGrab.grabclipboard()
        except Exception as exc:  # noqa: BLE001
            self.log(f"Could not read image from clipboard: {exc}")
            return None

        if data is None:
            self.log("Clipboard does not contain an image.")
            return None

        image: Image.Image | None = None
        if isinstance(data, Image.Image):
            image = data
        elif isinstance(data, list) and data:
            try:
                image = Image.open(data[0])
            except Exception as exc:  # noqa: BLE001
                self.log(f"Could not open image from clipboard file: {exc}")
                return None

        if image is None:
            self.log("Clipboard content is not an image.")
            return None

        return image.convert("RGB")

    def on_paste_screenshot(self) -> None:
        image = self._grab_image_from_clipboard()
        if image is None:
            return

        self.page_images.append(image)
        index = len(self.page_images)
        self._show_last_image(image)
        self.log(
            f"Pasted BOOK page screenshot #{index} ({image.width}x{image.height}).",
        )

        # Also add a small thumbnail to the thumbnail strip so all pasted
        # screenshots are visible in the UI.
        thumb = image.copy()
        thumb.thumbnail((96, 96), Image.LANCZOS)
        thumb_tk = ImageTk.PhotoImage(thumb)
        self.thumb_images.append(thumb_tk)
        lbl = Label(self.thumb_frame, image=thumb_tk)
        lbl.pack(side=LEFT, padx=2, pady=2)

    def on_paste_quiz_screenshot(self) -> None:
        image = self._grab_image_from_clipboard()
        if image is None:
            return

        self.quiz_image = image
        self._show_last_image(image)
        self.log(
            f"Pasted QUIZ screenshot ({image.width}x{image.height}).",
        )

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
        # If a transcription is already running, this acts as a Stop button.
        if self._book_transcribing:
            self._stop_reading = True
            self.log(
                "Stop requested; book transcription will stop after the current page.",
            )
            return

        def task() -> None:
            if not self.page_images:
                self.log(
                    "No page screenshots have been pasted yet. Use 'Paste BOOK Screenshot' first.",
                )
                return

            reader = _get_ocr_reader()
            if reader is None:
                self.log("OCR is not available (easyocr failed to initialize).")
                return

            total = len(self.page_images)
            self.log(f"Starting transcription for {total} pasted screenshots.")

            self._stop_reading = False
            self._book_transcribing = True

            def _set_running() -> None:
                self.read_button.configure(text="Stop Book Transcription")
                self._set_progress(0.0)

            self.root.after(0, _set_running)

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
            self._book_transcribing = False

            def _reset_button() -> None:
                self.read_button.configure(text="2. Transcribe Book Screenshots")
                if texts:
                    self._set_progress(1.0)

            self.root.after(0, _reset_button)
            self.log("Transcription completed for pasted screenshots.")

        self._run_in_background(task)

    def on_transcribe_quiz(self) -> None:
        def task() -> None:
            if self.quiz_image is None:
                self.log(
                    "No quiz screenshot has been pasted yet. Use 'Paste QUIZ Screenshot' first.",
                )
                return

            def _set_busy() -> None:
                self.transcribe_quiz_button.configure(
                    text="Transcribing Quiz...",
                    state="disabled",
                )

            def _set_idle() -> None:
                self.transcribe_quiz_button.configure(
                    text="Transcribe Quiz Screenshot",
                    state="normal",
                )

            self.root.after(0, _set_busy)

            self.log("Starting OCR transcription for QUIZ screenshot.")
            reader = _get_ocr_reader()
            if reader is None:
                self.log("OCR is not available (easyocr failed to initialize).")
                self.root.after(0, _set_idle)
                return

            try:
                img_np = np.array(self.quiz_image)
            except Exception as exc:  # noqa: BLE001
                self.log(f"Failed to prepare quiz image for OCR: {exc}")
                self.root.after(0, _set_idle)
                return

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
                self.log(f"OCR failed for quiz screenshot: {exc}")
                text = ""

            self.quiz_text = text
            display_text = (text or "").strip() or "(no text detected)"
            self.log(f"Quiz OCR text:\n{display_text}")

            self.root.after(0, _set_idle)

        self._run_in_background(task)
    def _parse_quiz_text(self, text: str) -> tuple[str, list[str]]:
        lines = [line.strip() for line in (text or "").splitlines()]
        non_empty = [line for line in lines if line]

        if not non_empty:
            return "", []

        option_pattern = re.compile(r"^([A-Z])[\.\)]\s*(.*)$")

        # First, check if we have any lines that look like "A. ...", "B) ..." etc.
        has_letter_options = any(option_pattern.match(line) for line in non_empty)

        # Fallback mode: no explicit A/B/C labels detected. Treat the first line as
        # the question and each subsequent non-empty line as an option.
        if not has_letter_options:
            # Strip any leading numeric index like "1" or "1." from the question line.
            first = non_empty[0]
            m = re.match(r"^\d+[\).]?\s*(.*)$", first)
            question = (m.group(1) if m and m.group(1) else first).strip()

            candidate_options = non_empty[1:]
            options: list[str] = []
            for line in candidate_options:
                # Skip stray single-letter lines like "A" or "B" from OCR.
                if len(line) == 1 and line.isalpha():
                    continue
                cleaned = line.rstrip(":").strip()
                if cleaned:
                    options.append(cleaned)

            # Limit the number of options to a reasonable maximum.
            if len(options) > 6:
                options = options[:6]

            return question, options

        question_lines: list[str] = []
        options: list[str] = []
        current_option: list[str] = []
        in_options = False

        for line in non_empty:
            match = option_pattern.match(line)
            if match and match.group(1) in ("A", "B", "C", "D", "E", "F"):
                if current_option:
                    options.append(" ".join(current_option).strip())
                    current_option = []
                in_options = True
                rest = match.group(2).strip()
                if rest:
                    current_option.append(rest)
            else:
                if in_options:
                    current_option.append(line)
                else:
                    question_lines.append(line)

        if current_option:
            options.append(" ".join(current_option).strip())

        question = " ".join(question_lines).strip()
        options = [opt for opt in options if opt]

        return question, options

    def on_quiz(self) -> None:
        def task() -> None:
            if not self.quiz_text:
                self.log(
                    "No quiz text has been transcribed yet. Use 'Transcribe Quiz Screenshot' first.",
                )
                return

            question, options = self._parse_quiz_text(self.quiz_text)
            if not question or len(options) < 2:
                self.log(
                    "Could not parse quiz question and options from OCR text. "
                    "Showing raw quiz OCR text instead.",
                )
                display_text = (self.quiz_text or "").strip() or "(no text detected)"
                self.log(f"Raw quiz OCR text:\n{display_text}")
                return

            if self.page_texts:
                context = "\n\n".join(self.page_texts).strip()
                if len(context) > 4000:
                    context = context[-4000:]
                book_context = context
                self.log("Using transcribed book text as context for quiz answer.")
            else:
                book_context = None
                self.log(
                    "No transcribed book text available; quiz answer will use quiz text only.",
                )

            if book_context:
                augmented_question = (
                    "Use the following book transcript to answer the quiz question.\n\n"
                    f"Book transcript:\n{book_context}\n\n"
                    f"Quiz question:\n{question}"
                )
            else:
                augmented_question = question

            llm_client = RemoteLLMClient(self.config.llm)

            try:
                suggestion = llm_client.choose_answer(augmented_question, options)
            except Exception as exc:  # noqa: BLE001
                self.log(f"Error while asking AI to answer quiz: {exc}")
                return

            # Try to detect which option letter the model selected (e.g. "B." or "C)").
            chosen_letter: str | None = None
            match = re.search(r"\b([A-F])[\).]\b", suggestion)
            if not match:
                match = re.search(r"\b([A-F])\b", suggestion)
            if match:
                chosen_letter = match.group(1)

            lines: list[str] = []
            lines.append("=== Quiz (from OCR) ===")
            lines.append(question)
            lines.append("")
            lines.append("Options:")
            for i, opt in enumerate(options):
                letter = chr(ord("A") + i)
                if chosen_letter == letter:
                    lines.append(f"{letter}. {opt}  <<< AI CHOSE THIS")
                else:
                    lines.append(f"{letter}. {opt}")
            lines.append("")
            lines.append(f">>> Suggested answer (raw LLM response): {suggestion}")
            self.log("\n".join(lines))

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
