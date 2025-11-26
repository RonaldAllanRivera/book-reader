import logging
import threading
from tkinter import BOTH, END, LEFT, RIGHT, Y, Button, Frame, Label, Scrollbar, Text, Tk

from selenium.webdriver.remote.webdriver import WebDriver

from automation.browser import create_driver
from automation.workflows import auto_read_with_progress, run_quiz_assistant
from ai.remote_client import RemoteLLMClient
from config.settings import AppConfig, load_config


class TkApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("SLZ Book Reader Controller")

        self.config: AppConfig = load_config()
        self.driver: WebDriver | None = None

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

        self.read_button = Button(
            button_frame,
            text="2. Start Auto-Reading",
            command=self.on_read,
        )
        self.read_button.pack(side=LEFT, padx=4)

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

    def on_read(self) -> None:
        def task() -> None:
            if self.driver is None:
                self.log("Browser is not running yet. Use 'Launch SLZ / Login' first.")
                return

            self.log(
                "Starting auto-reading. In Chrome, ensure the book reading view is open."
            )
            assert self.driver is not None
            auto_read_with_progress(self.driver, self.config)
            self.log("Auto-reading completed.")

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
