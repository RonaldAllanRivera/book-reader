import logging
import threading
import re
import os
import time
import hashlib
from collections import deque
import traceback
from tkinter import (
    BOTH,
    Canvas,
    X,
    BOTTOM,
    END,
    LEFT,
    RIGHT,
    Y,
    Button,
    Checkbutton,
    Frame,
    Label,
    Scrollbar,
    Text,
    Tk,
    BooleanVar,
    DoubleVar,
    StringVar,
)
from tkinter import ttk

import numpy as np
from PIL import Image, ImageGrab, ImageTk
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

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
        self.driver_mode_choices: list[tuple[str, str]] = [
            ("Auto", "auto"),
            ("Snap Chromium", "snap"),
            ("Selenium Manager", "selenium-manager"),
            ("WebDriverManager", "webdriver-manager"),
            ("Custom (env paths)", "custom"),
        ]
        self.driver_mode_labels = [label for label, _ in self.driver_mode_choices]
        self.driver_mode_map = {label: mode for label, mode in self.driver_mode_choices}
        self.driver_mode_var = StringVar(value=self.driver_mode_labels[0])
        self.easy_book_screenshot_var = BooleanVar(value=True)
        self.easy_quiz_screenshot_var = BooleanVar(value=False)
        self._easy_book_clipboard_job: str | None = None
        self._easy_book_clipboard_seen: deque[str] = deque(maxlen=200)
        self._easy_book_clipboard_last_sig: str | None = None
        self._easy_quiz_clipboard_job: str | None = None
        self._easy_quiz_clipboard_seen: deque[str] = deque(maxlen=200)
        self._easy_quiz_clipboard_last_sig: str | None = None
        self._quiz_transcribing: bool = False
        self._pending_quiz_image: Image.Image | None = None
        self._pending_quiz_sig: str | None = None
        self.page_images: list[Image.Image] = []
        self.page_texts: list[str] = []
        self.quiz_image: Image.Image | None = None
        self.quiz_text: str | None = None
        self._last_image_tk: ImageTk.PhotoImage | None = None
        self.thumb_images: list[ImageTk.PhotoImage] = []

        self._setup_logging()
        self._build_ui()

        if self.easy_book_screenshot_var.get():
            self.root.after(0, self.on_toggle_easy_book_screenshot)

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
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            activeforeground="white",
        )
        self.launch_button.pack(side=LEFT, padx=4)

        self.fill_login_button = Button(
            button_frame,
            text="Fill Login Form",
            command=self.on_fill_login,
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            activeforeground="white",
        )
        self.fill_login_button.pack(side=LEFT, padx=4)

        self.lexile_button = Button(
            button_frame,
            text="Lexile Levels",
            command=self.on_set_lexile_levels,
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            activeforeground="white",
        )
        self.lexile_button.pack(side=LEFT, padx=4)

        self.paste_button = Button(
            button_frame,
            text="Paste BOOK Screenshot (Ctrl+B)",
            command=self.on_paste_screenshot,
            bg="#2E7D32",
            fg="white",
            activebackground="#1B5E20",
            activeforeground="white",
        )
        self.paste_button.pack(side=LEFT, padx=4)

        self.read_button = Button(
            button_frame,
            text="2. Transcribe Book Screenshots (Ctrl+N)",
            command=self.on_read,
            bg="#2E7D32",
            fg="white",
            activebackground="#1B5E20",
            activeforeground="white",
        )
        self.read_button.pack(side=LEFT, padx=4)

        self.clear_book_button = Button(
            button_frame,
            text="Clear BOOK Screenshots",
            command=self.on_clear_book_screenshots,
            bg="#A5D6A7",
            fg="black",
            activebackground="#81C784",
            activeforeground="black",
        )
        self.clear_book_button.pack(side=LEFT, padx=4)

        self.paste_quiz_button = Button(
            button_frame,
            text="Paste QUIZ Screenshot (Ctrl+Q)",
            command=self.on_paste_quiz_screenshot,
            bg="#6A1B9A",
            fg="white",
            activebackground="#4A148C",
            activeforeground="white",
        )
        self.paste_quiz_button.pack(side=LEFT, padx=4)

        self.transcribe_quiz_button = Button(
            button_frame,
            text="Transcribe Quiz Screenshot (Ctrl+W)",
            command=self.on_transcribe_quiz,
            bg="#6A1B9A",
            fg="white",
            activebackground="#4A148C",
            activeforeground="white",
        )
        self.transcribe_quiz_button.pack(side=LEFT, padx=4)

        self.quiz_button = Button(
            button_frame,
            text="3. Answer Quiz from Book",
            command=self.on_quiz,
            bg="#FF8F00",
            fg="black",
            activebackground="#FF6F00",
            activeforeground="black",
        )
        self.quiz_button.pack(side=LEFT, padx=4)

        self.exit_button = Button(
            button_frame,
            text="Exit",
            command=self.on_exit,
            bg="#C62828",
            fg="white",
            activebackground="#B71C1C",
            activeforeground="white",
        )
        self.exit_button.pack(side=RIGHT, padx=4)

        self.status_label = Label(self.root, text="Ready.", anchor="w")
        self.status_label.pack(fill="x", padx=8)

        driver_frame = Frame(self.root)
        driver_frame.pack(fill="x", padx=8, pady=(0, 4))

        Label(driver_frame, text="Driver:").pack(side=LEFT)
        self.driver_mode_combo = ttk.Combobox(
            driver_frame,
            textvariable=self.driver_mode_var,
            values=self.driver_mode_labels,
            state="readonly",
            width=22,
        )
        self.driver_mode_combo.pack(side=LEFT, padx=(8, 0))

        self.clear_all_button = Button(
            driver_frame,
            text="Clear All",
            command=self.on_clear_all,
            bg="#E0E0E0",
            fg="black",
            activebackground="#BDBDBD",
            activeforeground="black",
        )
        self.clear_all_button.pack(side=RIGHT)

        self.copy_book_transcript_button = Button(
            driver_frame,
            text="Copy Book Transcript",
            command=self.on_copy_book_transcript,
            bg="#E0E0E0",
            fg="black",
            activebackground="#BDBDBD",
            activeforeground="black",
        )
        self.copy_book_transcript_button.pack(side=RIGHT, padx=(0, 8))

        easy_frame = Frame(self.root)
        easy_frame.pack(fill="x", padx=8, pady=(0, 4))

        self.easy_book_screenshot_check = Checkbutton(
            easy_frame,
            text="Enable Easy Screenshot for Book",
            variable=self.easy_book_screenshot_var,
            command=self.on_toggle_easy_book_screenshot,
        )
        self.easy_book_screenshot_check.pack(side=LEFT)

        self.easy_quiz_screenshot_check = Checkbutton(
            easy_frame,
            text="Enable Easy Screenshot for Quiz",
            variable=self.easy_quiz_screenshot_var,
            command=self.on_toggle_easy_quiz_screenshot,
        )
        self.easy_quiz_screenshot_check.pack(side=LEFT, padx=(12, 0))

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

        thumb_container = Frame(self.root)
        thumb_container.pack(fill="x", padx=8, pady=(0, 4))

        self.thumb_canvas = Canvas(thumb_container, height=140, highlightthickness=0)
        self.thumb_canvas.pack(side=LEFT, fill="x", expand=True)

        self.thumb_scrollbar = Scrollbar(
            thumb_container,
            orient="horizontal",
            command=self.thumb_canvas.xview,
        )
        self.thumb_scrollbar.pack(side=BOTTOM, fill=X)
        self.thumb_canvas.configure(xscrollcommand=self.thumb_scrollbar.set)

        self.thumb_frame = Frame(self.thumb_canvas)
        self._thumb_window = self.thumb_canvas.create_window(
            (0, 0),
            window=self.thumb_frame,
            anchor="nw",
        )

        self.thumb_frame.bind("<Configure>", self._on_thumb_frame_configure)
        self.thumb_canvas.bind("<Configure>", self._on_thumb_canvas_configure)
        self.thumb_canvas.bind("<Enter>", self._bind_thumb_scroll)
        self.thumb_canvas.bind("<Leave>", self._unbind_thumb_scroll)

        text_frame = Frame(self.root)
        text_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        self.log_text = Text(text_frame, height=12, state="disabled")
        self.log_text.pack(side=LEFT, fill=BOTH, expand=True)

        scroll = Scrollbar(text_frame, command=self.log_text.yview)
        scroll.pack(side=RIGHT, fill=Y)
        self.log_text.configure(yscrollcommand=scroll.set)

        # Configure log text tags for simple color-coding by category.
        self.log_text.tag_config("log_info", foreground="#000000")
        self.log_text.tag_config("log_status", foreground="#555555")
        self.log_text.tag_config("log_book", foreground="#1B5E20")
        self.log_text.tag_config("log_quiz", foreground="#4A148C")
        self.log_text.tag_config("log_error", foreground="#B71C1C")

        self._bind_shortcuts()

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-b>", lambda event: self.on_paste_screenshot())
        self.root.bind_all("<Control-q>", lambda event: self.on_paste_quiz_screenshot())
        self.root.bind_all("<Control-n>", lambda event: self.on_read())
        self.root.bind_all("<Control-w>", lambda event: self.on_transcribe_quiz())

    def _on_thumb_frame_configure(self, event) -> None:
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))

    def _on_thumb_canvas_configure(self, event) -> None:
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))

    def _bind_thumb_scroll(self, event) -> None:
        self.thumb_canvas.bind("<MouseWheel>", self._on_thumb_mousewheel)
        self.thumb_canvas.bind("<Button-4>", self._on_thumb_mousewheel)
        self.thumb_canvas.bind("<Button-5>", self._on_thumb_mousewheel)

    def _unbind_thumb_scroll(self, event) -> None:
        self.thumb_canvas.unbind("<MouseWheel>")
        self.thumb_canvas.unbind("<Button-4>")
        self.thumb_canvas.unbind("<Button-5>")

    def _on_thumb_mousewheel(self, event) -> None:
        delta = 0
        if hasattr(event, "delta") and event.delta:
            delta = -1 * int(event.delta / 120)
        elif hasattr(event, "num"):
            if event.num == 4:
                delta = -1
            elif event.num == 5:
                delta = 1
        if delta:
            self.thumb_canvas.xview_scroll(delta, "units")

    def _append_log(self, message: str, tag: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(END, message + "\n", (tag,))
        self.log_text.see(END)
        self.log_text.configure(state="disabled")
        self.status_label.configure(text=message)

    def _clear_log_text(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", END)
        self.log_text.configure(state="disabled")

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

    def _rebuild_thumbnails(self) -> None:
        for widget in self.thumb_frame.winfo_children():
            widget.destroy()
        self.thumb_images.clear()

        for index, image in enumerate(self.page_images, start=1):
            thumb = image.copy()
            thumb.thumbnail((96, 96), Image.LANCZOS)
            thumb_tk = ImageTk.PhotoImage(thumb)
            self.thumb_images.append(thumb_tk)

            container = Frame(self.thumb_frame)
            container.pack(side=LEFT, padx=2, pady=2)

            lbl = Label(container, image=thumb_tk)
            lbl.pack(side="top")

            delete_btn = Button(
                container,
                text="X",
                command=lambda idx=index - 1: self._delete_book_screenshots(idx),
                bg="#C62828",
                fg="white",
                activebackground="#B71C1C",
                activeforeground="white",
                padx=2,
                pady=0,
            )
            delete_btn.pack(side="top", fill="x")

        try:
            self.thumb_canvas.update_idletasks()
            self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all"))
        except Exception:  # noqa: BLE001
            pass

    def _delete_book_screenshots(self, index: int) -> None:
        if index < 0 or index >= len(self.page_images):
            return

        self.page_images.pop(index)

        if self.page_texts:
            self.page_texts.clear()
            self.log(
                "Cleared existing book transcripts because a page screenshot was deleted. "
                "Please re-run book transcription.",
            )

        self._rebuild_thumbnails()

        if self.page_images:
            self._show_last_image(self.page_images[-1])
            self.log(
                f"Deleted a BOOK page screenshot. {len(self.page_images)} remaining.",
            )
        else:
            self._last_image_tk = None
            self.image_label.configure(image="", text="No screenshots pasted yet.")
            self._set_progress(0.0)
            self.log("Deleted the last BOOK page screenshot; none remain.")

    def _grab_image_from_clipboard(self, *, silent: bool = False) -> Image.Image | None:
        try:
            data = ImageGrab.grabclipboard()
        except Exception as exc:  # noqa: BLE001
            if not silent:
                self.log(f"Could not read image from clipboard: {exc}")
            return None

        if data is None:
            if not silent:
                self.log("Clipboard does not contain an image.")
            return None

        image: Image.Image | None = None
        if isinstance(data, Image.Image):
            image = data
        elif isinstance(data, list) and data:
            try:
                image = Image.open(data[0])
            except Exception as exc:  # noqa: BLE001
                if not silent:
                    self.log(f"Could not open image from clipboard file: {exc}")
                return None

        if image is None:
            if not silent:
                self.log("Clipboard content is not an image.")
            return None

        return image.convert("RGB")

    def _image_signature(self, image: Image.Image) -> str:
        thumb = image.copy()
        thumb.thumbnail((96, 96), Image.LANCZOS)
        payload = f"{thumb.mode}|{thumb.size[0]}x{thumb.size[1]}".encode("utf-8") + thumb.tobytes()
        return hashlib.sha256(payload).hexdigest()

    def on_toggle_easy_book_screenshot(self) -> None:
        if self.easy_book_screenshot_var.get():
            if self.easy_quiz_screenshot_var.get():
                self.easy_quiz_screenshot_var.set(False)
                self._stop_easy_quiz_clipboard_watcher()
            self._start_easy_book_clipboard_watcher()
            self.log("Easy Book Screenshot enabled (clipboard watcher running).")
        else:
            self._stop_easy_book_clipboard_watcher()
            self.log("Easy Book Screenshot disabled.")

    def on_toggle_easy_quiz_screenshot(self) -> None:
        if self.easy_quiz_screenshot_var.get():
            if self.easy_book_screenshot_var.get():
                self.easy_book_screenshot_var.set(False)
                self._stop_easy_book_clipboard_watcher()
            self._start_easy_quiz_clipboard_watcher()
            self.log("Easy Quiz Screenshot enabled (clipboard watcher running).")
        else:
            self._stop_easy_quiz_clipboard_watcher()
            self.log("Easy Quiz Screenshot disabled.")

    def _start_easy_book_clipboard_watcher(self) -> None:
        if self._easy_book_clipboard_job is not None:
            return
        self._easy_book_clipboard_last_sig = None
        self._poll_easy_book_clipboard()

    def _stop_easy_book_clipboard_watcher(self) -> None:
        job = self._easy_book_clipboard_job
        self._easy_book_clipboard_job = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:  # noqa: BLE001
            pass

    def _start_easy_quiz_clipboard_watcher(self) -> None:
        if self._easy_quiz_clipboard_job is not None:
            return
        self._easy_quiz_clipboard_last_sig = None
        self._pending_quiz_image = None
        self._pending_quiz_sig = None
        self._poll_easy_quiz_clipboard()

    def _stop_easy_quiz_clipboard_watcher(self) -> None:
        job = self._easy_quiz_clipboard_job
        self._easy_quiz_clipboard_job = None
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:  # noqa: BLE001
            pass

    def _maybe_process_pending_quiz(self) -> None:
        if self._quiz_transcribing:
            return
        if not self.easy_quiz_screenshot_var.get():
            self._pending_quiz_image = None
            self._pending_quiz_sig = None
            return
        if self._pending_quiz_image is None:
            return

        image = self._pending_quiz_image
        sig = self._pending_quiz_sig
        self._pending_quiz_image = None
        self._pending_quiz_sig = None

        if image is None:
            return

        self.quiz_image = image
        self._show_last_image(image)
        if sig is not None:
            self._easy_quiz_clipboard_last_sig = sig
            self._easy_quiz_clipboard_seen.append(sig)

        self.log(
            f"Pasted QUIZ screenshot from clipboard (easy mode) ({image.width}x{image.height}).",
        )
        self.on_transcribe_quiz()

    def _poll_easy_quiz_clipboard(self) -> None:
        if not self.easy_quiz_screenshot_var.get():
            self._easy_quiz_clipboard_job = None
            return

        try:
            image = self._grab_image_from_clipboard(silent=True)
            if image is not None:
                sig = self._image_signature(image)
                if sig != self._easy_quiz_clipboard_last_sig and sig not in self._easy_quiz_clipboard_seen:
                    if self._quiz_transcribing:
                        if self._pending_quiz_sig != sig:
                            self._pending_quiz_image = image
                            self._pending_quiz_sig = sig
                            self.log(
                                "Queued QUIZ screenshot from clipboard (easy mode); will process after current OCR completes.",
                            )
                    else:
                        self._easy_quiz_clipboard_last_sig = sig
                        self._easy_quiz_clipboard_seen.append(sig)
                        self.quiz_image = image
                        self._show_last_image(image)
                        self.log(
                            f"Pasted QUIZ screenshot from clipboard (easy mode) ({image.width}x{image.height}).",
                        )
                        self.root.after(0, self.on_transcribe_quiz)
        finally:
            self._easy_quiz_clipboard_job = self.root.after(350, self._poll_easy_quiz_clipboard)

    def _poll_easy_book_clipboard(self) -> None:
        if not self.easy_book_screenshot_var.get():
            self._easy_book_clipboard_job = None
            return

        try:
            image = self._grab_image_from_clipboard(silent=True)
            if image is not None:
                if len(self.page_images) >= self.config.max_book_screenshots:
                    self.easy_book_screenshot_var.set(False)
                    self._stop_easy_book_clipboard_watcher()
                    self.log(
                        f"Reached {self.config.max_book_screenshots} BOOK screenshots; Easy Book Screenshot has been disabled. "
                        "Use Clear BOOK Screenshots / Clear All to reset.",
                    )
                    return

                sig = self._image_signature(image)
                if sig != self._easy_book_clipboard_last_sig and sig not in self._easy_book_clipboard_seen:
                    self._easy_book_clipboard_last_sig = sig
                    self._easy_book_clipboard_seen.append(sig)
                    self.page_images.append(image)
                    index = len(self.page_images)
                    self._show_last_image(image)
                    self.log(
                        f"Added BOOK page screenshot #{index} from clipboard (easy mode) "
                        f"({image.width}x{image.height}).",
                    )
                    self._rebuild_thumbnails()
        finally:
            self._easy_book_clipboard_job = self.root.after(350, self._poll_easy_book_clipboard)

    def on_paste_screenshot(self) -> None:
        if len(self.page_images) >= self.config.max_book_screenshots:
            self.log(
                f"Reached {self.config.max_book_screenshots} BOOK screenshots; cannot paste more. "
                "Use Clear BOOK Screenshots / Clear All to reset, or increase MAX_BOOK_SCREENSHOTS in .env.",
            )
            return

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
        self._rebuild_thumbnails()

    def on_clear_book_screenshots(self) -> None:
        if self._book_transcribing:
            self.log(
                "Cannot clear book screenshots while transcription is running. "
                "Please stop transcription first.",
            )
            return

        count = len(self.page_images)
        if not count:
            self.log("No book screenshots to clear.")
            return

        self.page_images.clear()
        self.page_texts.clear()
        self.thumb_images.clear()

        for widget in self.thumb_frame.winfo_children():
            widget.destroy()

        self._last_image_tk = None
        self.image_label.configure(image="", text="No screenshots pasted yet.")
        self._set_progress(0.0)
        self.log(f"Cleared {count} BOOK screenshots and any associated transcripts.")

    def on_clear_all(self) -> None:
        if self._book_transcribing:
            self.log(
                "Cannot clear transcripts while transcription is running. "
                "Please stop transcription first.",
            )
            return

        had_book = bool(self.page_images) or bool(self.page_texts)
        had_quiz = bool(self.quiz_image) or bool(self.quiz_text)

        self.page_images.clear()
        self.page_texts.clear()
        self.thumb_images.clear()
        for widget in self.thumb_frame.winfo_children():
            widget.destroy()

        self.quiz_image = None
        self.quiz_text = None

        self._last_image_tk = None
        self.image_label.configure(image="", text="No screenshots pasted yet.")
        self._set_progress(0.0)

        self._clear_log_text()

        if not had_book and not had_quiz:
            self.log("Nothing to clear.")
        else:
            self.log("Cleared all BOOK and QUIZ transcripts/screenshots.")

    def on_copy_book_transcript(self) -> None:
        if self._book_transcribing:
            self.log(
                "Cannot copy book transcript while transcription is running. "
                "Please stop transcription first.",
            )
            return

        if not self.page_texts:
            self.log("No book transcript available yet. Transcribe book screenshots first.")
            return

        parts: list[str] = []
        for index, text in enumerate(self.page_texts, start=1):
            display_text = (text or "").strip() or "(no text detected)"
            parts.append(f"Transcript page {index}:\n{display_text}")

        full_text = "\n\n".join(parts)

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(full_text)
            self.root.update()
        except Exception as exc:  # noqa: BLE001
            self.log(f"Failed to copy book transcript to clipboard: {exc}")
            return

        self.log(f"Copied BOOK transcript to clipboard ({len(self.page_texts)} pages).")

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

        lower = message.lower()
        if any(keyword in lower for keyword in ["error:", "failed", "exception", "could not"]):
            tag = "log_error"
        elif "quiz" in lower or "=== quiz" in lower:
            tag = "log_quiz"
        elif "transcript page" in lower or "transcription" in lower or "ocr" in lower:
            tag = "log_book"
        elif any(
            lower.startswith(prefix)
            for prefix in (
                "initializing",
                "opening slz",
                "browser is not running",
                "configuration loaded",
                "chrome webdriver initialized",
            )
        ):
            tag = "log_status"
        else:
            tag = "log_info"

        def _update() -> None:
            self._append_log(message, tag)

        self.root.after(0, _update)

    def _run_in_background(self, func) -> None:
        def _wrapper() -> None:
            try:
                func()
            except Exception as exc:  # noqa: BLE001
                self.log(f"Error: {exc}")
                self.log(traceback.format_exc())

        thread = threading.Thread(target=_wrapper, daemon=True)
        thread.start()

    def on_launch(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Initializing Chrome WebDriver...")
                selected = (self.driver_mode_var.get() or "Auto").strip()
                mode = self.driver_mode_map.get(selected, "auto")
                self.log(f"Driver mode: {selected}")
                self.driver = create_driver(self.config.automation, driver_mode=mode)
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

    def on_set_lexile_levels(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Browser is not running yet. Use 'Launch SLZ / Login' first.")
                return

            lexile_from = os.getenv("LEXILE_FROM", "").strip()
            lexile_to = os.getenv("LEXILE_TO", "").strip()

            if not lexile_from or not lexile_to:
                self.log(
                    "LEXILE_FROM and LEXILE_TO are not configured; cannot fill Lexile Level fields.",
                )
                return

            assert self.driver is not None

            try:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[-1])
            except Exception:  # noqa: BLE001
                pass

            script = """
return (function(fromVal, toVal) {
  function setVal(selector, value) {
    var el = document.querySelector(selector);
    if (!el) { return false; }
    try { el.focus(); } catch (e) {}
    try {
      var desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
      if (desc && desc.set) {
        desc.set.call(el, value);
      } else {
        el.value = value;
      }
    } catch (e) {
      el.value = value;
    }
    try {
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {}
    return true;
  }

  var fromSelectors = "input[name='lexileStart'], input[id='exampleInputEmail1']";
  var toSelectors = "input[name='lexileEnd'], input[id='exampleInputPassword1']";

  var okFrom = setVal(fromSelectors, fromVal);
  var okTo = setVal(toSelectors, toVal);

  return { okFrom: okFrom, okTo: okTo };
})(arguments[0], arguments[1]);
"""

            deadline = time.time() + 10.0
            success = False
            last_error: Exception | None = None

            while time.time() < deadline and not success:
                try:
                    self.driver.switch_to.default_content()

                    try:
                        result = self.driver.execute_script(script, lexile_from, lexile_to)
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        result = None

                    ok_from = bool(result and result.get("okFrom"))
                    ok_to = bool(result and result.get("okTo"))

                    if ok_from and ok_to:
                        success = True
                    else:
                        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                        for frame in frames:
                            try:
                                self.driver.switch_to.default_content()
                                self.driver.switch_to.frame(frame)
                                result = self.driver.execute_script(
                                    script,
                                    lexile_from,
                                    lexile_to,
                                )
                                ok_from = bool(result and result.get("okFrom"))
                                ok_to = bool(result and result.get("okTo"))
                                if ok_from and ok_to:
                                    success = True
                                    break
                            except Exception as exc:  # noqa: BLE001
                                last_error = exc

                    if not success:
                        time.sleep(0.5)
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    time.sleep(0.5)

            try:
                self.driver.switch_to.default_content()
            except Exception:  # noqa: BLE001
                pass

            if success:
                self.log(
                    f"Filled Lexile Level fields with LEXILE_FROM={lexile_from} and LEXILE_TO={lexile_to}.",
                )
            else:
                if last_error is not None:
                    self.log(
                        f"Could not locate Lexile Level inputs on the current page (even after checking iframes): {last_error}",
                    )
                else:
                    self.log(
                        "Could not locate Lexile Level inputs on the current page (selectors did not match any inputs).",
                    )

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
            if self._quiz_transcribing:
                self.log("Quiz transcription is already running.")
                return
            if self.quiz_image is None:
                self.log(
                    "No quiz screenshot has been pasted yet. Use 'Paste QUIZ Screenshot' first.",
                )
                return

            self._quiz_transcribing = True

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

            try:
                self.root.after(0, _set_busy)

                self.log("Starting OCR transcription for QUIZ screenshot.")
                reader = _get_ocr_reader()
                if reader is None:
                    self.log("OCR is not available (easyocr failed to initialize).")
                    return

                try:
                    img_np = np.array(self.quiz_image)
                except Exception as exc:  # noqa: BLE001
                    self.log(f"Failed to prepare quiz image for OCR: {exc}")
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

                # Automatically ask the AI to answer this quiz using the current
                # transcribed book text as context (if available).
                if text.strip():
                    self.log(
                        "Automatically answering quiz from book transcript after OCR.",
                    )
                    # Trigger the normal quiz flow on the main thread; it will run
                    # its work in the background as usual.
                    self.root.after(0, self.on_quiz)
            finally:
                self.root.after(0, _set_idle)
                self._quiz_transcribing = False
                self.root.after(0, self._maybe_process_pending_quiz)

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
            self.root.after(0, self._stop_easy_book_clipboard_watcher)
            self.root.after(0, self._stop_easy_quiz_clipboard_watcher)
            self.root.after(0, self.root.destroy)

        self._run_in_background(task)


def main() -> None:
    root = Tk()
    app = TkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
