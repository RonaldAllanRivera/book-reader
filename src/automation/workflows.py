import io
import logging
import os
import time
from typing import List, Tuple

import easyocr
import numpy as np
from PIL import Image
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ai.base import LLMClient
from config.settings import AppConfig


def login(driver: WebDriver, app_config: AppConfig) -> None:
    """Open SLZ and let the user perform login manually in the browser window."""
    logging.info("Opening Scholastic Learning Zone at %s", app_config.slz.base_url)
    driver.get(app_config.slz.base_url)

    logging.info(
        "Please log in manually in the opened browser window. "
        "After you are fully logged in and can see your books, "
        "return to this console and press Enter to continue."
    )
    input("When you are logged in, press Enter here to continue...")


def fill_login_form(driver: WebDriver, app_config: AppConfig) -> None:
    """Fill the SLZ login form using configured credentials, without clicking Login."""
    if not app_config.username or not app_config.password:
        logging.warning(
            "SLZ_USERNAME and/or SLZ_PASSWORD are not configured; cannot fill login form.",
        )
        return

    logging.info(
        "Filling SLZ login form using credentials from environment for user '%s'.",
        app_config.username,
    )
    wait = WebDriverWait(driver, 20)

    try:
        username_input = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[name='username'], input[formcontrolname='username']",
                )
            )
        )
        password_input = wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "input[type='password'], input[name='password'], input[formcontrolname='password']",
                )
            )
        )

        username_input.clear()
        username_input.send_keys(app_config.username)
        password_input.clear()
        password_input.send_keys(app_config.password)

        logging.info(
            "Login form fields filled. Please review in Chrome and click the Login button manually.",
        )
    except (TimeoutException, NoSuchElementException) as exc:
        logging.warning("Unable to locate login inputs to fill form: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Unexpected error while filling login form: %s", exc)


def auto_read_with_progress(
    driver: WebDriver,
    app_config: AppConfig,
    stop_requested=None,
    on_page_excerpt=None,
    on_progress=None,
) -> None:
    """Auto-scroll and move across multiple pages, with a console progress bar.

    If stop_requested is provided, it should be a callable returning a bool; when it
    returns True, the reading loop will stop early.

    If on_page_excerpt is provided, it should be a callable accepting (page_number, excerpt)
    and will be invoked when the transcript is (re)calculated for a page.
    """
    total_seconds = app_config.automation.read_total_seconds
    step_seconds = app_config.automation.read_scroll_step_seconds
    if total_seconds <= 0 or step_seconds <= 0:
        logging.warning("Auto-read skipped: total_seconds or step_seconds not positive.")
        return

    steps = max(1, int(total_seconds / step_seconds))
    logging.info(
        "Starting auto-reading for ~%s seconds (step %s seconds).",
        total_seconds,
        step_seconds,
    )

    start_time = time.time()
    bar_width = 30
    current_page = _get_current_page(driver)

    if callable(on_progress):
        try:
            on_progress(0.0, 0.0, total_seconds)
        except Exception:
            pass

    _ensure_reading_overlay(driver)
    try:
        page_text = _extract_page_text(driver)
    except Exception:
        page_text = ""
    _update_reading_overlay(driver, current_page, page_text)
    if callable(on_page_excerpt):
        try:
            on_page_excerpt(current_page, page_text)
        except Exception:
            pass

    last_page = current_page

    for _ in range(steps):
        if callable(stop_requested) and stop_requested():
            logging.info("Stop requested for auto-reading; exiting early.")
            break

        # Wait for the next step interval while the user may manually change pages.
        time.sleep(step_seconds)

        elapsed = time.time() - start_time
        progress = min(1.0, elapsed / total_seconds) if total_seconds > 0 else 1.0
        filled = int(bar_width * progress)
        bar = "#" * filled + "-" * (bar_width - filled)
        print(
            f"\rReading progress: [{bar}] {int(elapsed)}/{total_seconds} sec",
            end="",
            flush=True,
        )

        if callable(on_progress):
            try:
                on_progress(progress, elapsed, total_seconds)
            except Exception:
                pass

        # If the user manually changed pages, refresh OCR for the new page.
        try:
            page_now = _get_current_page(driver)
        except Exception:
            page_now = last_page

        if page_now != last_page:
            last_page = page_now
            try:
                page_text = _extract_page_text(driver)
            except Exception:
                page_text = ""
            _update_reading_overlay(driver, page_now, page_text)
            if callable(on_page_excerpt):
                try:
                    on_page_excerpt(page_now, page_text)
                except Exception:
                    pass

        remaining = total_seconds - elapsed
        if remaining <= 0:
            break

    print()
    logging.info("Auto-reading completed.")


def _get_current_page(driver: WebDriver) -> int:
    """Return the current page number from the SLZ reader controls, defaulting to 1."""
    script = """
    var input = document.querySelector('app-page-navigation-controls input#pageInput');
    if (input && input.value) {
        var n = parseInt(input.value, 10);
        if (!isNaN(n)) { return n; }
    }
    return 1;
    """
    try:
        value = driver.execute_script(script)
        return int(value) if value else 1
    except Exception:
        return 1


def _ensure_reading_overlay(driver: WebDriver) -> None:
    script = """
    (function() {
        var el = document.getElementById('slz-reading-overlay');
        if (!el) {
            el = document.createElement('div');
            el.id = 'slz-reading-overlay';
            el.style.position = 'fixed';
            el.style.left = '16px';
            el.style.bottom = '16px';
            el.style.zIndex = '999998';
            el.style.background = 'rgba(0, 0, 0, 0.8)';
            el.style.color = '#ffffff';
            el.style.padding = '8px 12px';
            el.style.borderRadius = '4px';
            el.style.fontSize = '11px';
            el.style.maxWidth = '360px';
            el.style.maxHeight = '40%';
            el.style.overflowY = 'auto';
            el.style.fontFamily = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
            el.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.4)';
            document.body.appendChild(el);
        }
    })();
    """
    driver.execute_script(script)


def _update_reading_overlay(driver: WebDriver, page_number: int, excerpt: str) -> None:
    message = f"Page {page_number} excerpt:\n" + (excerpt or "(no text detected)")
    script = """
    (function(msg) {
        var el = document.getElementById('slz-reading-overlay');
        if (!el) { return; }
        el.textContent = msg;
    })(arguments[0]);
    """
    driver.execute_script(script, message)


_EASYOCR_READER = None


def _get_ocr_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=False)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to initialize easyocr Reader: %s", exc)
            _EASYOCR_READER = None
    return _EASYOCR_READER


def _extract_page_text(driver: WebDriver, max_chars: int = 600) -> str:
    """Extract page text using local OCR (easyocr) on a screenshot.

    This works even when the book content is rendered as an image in the reader.
    """

    reader = _get_ocr_reader()
    if reader is None:
        return ""

    try:
        png_bytes = driver.get_screenshot_as_png()
    except Exception as exc:  # noqa: BLE001
        logging.warning("Failed to capture screenshot for OCR: %s", exc)
        return ""

    try:
        image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        logging.warning("Failed to open screenshot image for OCR: %s", exc)
        return ""

    try:
        img_np = np.array(image)
    except Exception as exc:  # noqa: BLE001
        logging.warning("Failed to convert screenshot image to numpy array: %s", exc)
        return ""

    try:
        lines = reader.readtext(img_np, detail=0, paragraph=True) or []
    except Exception as exc:  # noqa: BLE001
        logging.warning("easyocr OCR failed: %s", exc)
        return ""

    text = "\n".join(line.strip() for line in lines if isinstance(line, str)).strip()
    if not text:
        return ""

    if len(text) > max_chars:
        text = text[:max_chars] + "\n…"
    return text


def _click_next_page(driver: WebDriver) -> bool:
    """Click the next-page button in the SLZ reader, if available and enabled."""
    try:
        next_button = driver.find_element(
            By.CSS_SELECTOR,
            "app-page-navigation-controls .next-button button",
        )
    except NoSuchElementException:
        logging.warning("Next page button not found in the reader controls.")
        return False

    classes = next_button.get_attribute("class") or ""
    if "disabled" in classes or not next_button.is_enabled():
        logging.info("Next page button appears disabled; likely last page.")
        return False

    try:
        next_button.click()
        logging.info("Moved to next page in reader.")
        return True
    except Exception as exc:
        logging.warning("Failed to click next page button: %s", exc)
        return False


def refresh_reading_transcript(
    driver: WebDriver,
    app_config: AppConfig,
    max_chars: int = 600,
) -> tuple[int, str]:
    """Ensure the reading overlay exists and refresh its content for the current page.

    Returns a tuple of (page_number, excerpt_text).
    """
    _ensure_reading_overlay(driver)
    current_page = _get_current_page(driver)
    try:
        page_text = _extract_page_text(driver, max_chars=max_chars)
    except Exception:
        page_text = ""
    _update_reading_overlay(driver, current_page, page_text)
    logging.info("Reading transcript updated for page %s.", current_page)
    return current_page, page_text


def _ensure_overlay(driver: WebDriver) -> None:
    script = """
    (function() {
        var el = document.getElementById('slz-helper-overlay');
        if (!el) {
            el = document.createElement('div');
            el.id = 'slz-helper-overlay';
            el.style.position = 'fixed';
            el.style.right = '16px';
            el.style.bottom = '16px';
            el.style.zIndex = '999999';
            el.style.background = 'rgba(0, 0, 0, 0.85)';
            el.style.color = '#ffffff';
            el.style.padding = '8px 12px';
            el.style.borderRadius = '4px';
            el.style.fontSize = '12px';
            el.style.maxWidth = '320px';
            el.style.fontFamily = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
            el.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.4)';
            document.body.appendChild(el);
        }
    })();
    """
    driver.execute_script(script)


def _update_overlay(driver: WebDriver, message: str) -> None:
    script = """
    (function(msg) {
        var el = document.getElementById('slz-helper-overlay');
        if (!el) { return; }
        el.textContent = msg;
    })(arguments[0]);
    """
    driver.execute_script(script, message)


def _extract_quiz_question_and_options(driver: WebDriver) -> Tuple[str, List[str]]:
    script = """
    return (function() {
        function getText(el) {
            return el && el.innerText ? el.innerText.trim() : '';
        }

        var questionEl =
            document.querySelector('.question-text, .quiz-question, .question') ||
            document.querySelector('h1, h2, h3, .prompt');

        var question = getText(questionEl);

        var optionNodes = Array.from(
            document.querySelectorAll(
                '.answer-option, .option, li.choice, li.answer, button.choice, button.answer'
            )
        );

        var options = optionNodes
            .map(function(n) { return getText(n); })
            .filter(function(t) { return t.length > 0; });

        return { question: question, options: options };
    })();
    """

    data = driver.execute_script(script) or {}
    question = data.get("question") or ""
    options = data.get("options") or []
    return question, options


def run_quiz_assistant(
    driver: WebDriver,
    app_config: AppConfig,
    llm_client: LLMClient,
    book_context: str | None = None,
    on_question_result=None,
) -> None:
    """Loop over quiz questions, show LLM suggestions in an in-page overlay.

    If book_context is provided, it will be included in the prompt sent to the LLM so
    that answers can be grounded in the transcribed book text.
    """

    max_questions = app_config.automation.max_quiz_questions
    logging.info("Starting quiz assistant for up to %s questions.", max_questions)

    _ensure_overlay(driver)

    # To avoid prompts that are too large, cap the context length.
    if book_context:
        trimmed_context = book_context.strip()
        max_context_chars = 4000
        if len(trimmed_context) > max_context_chars:
            trimmed_context = trimmed_context[-max_context_chars:]
    else:
        trimmed_context = None

    for index in range(1, max_questions + 1):
        logging.info("Analyzing quiz question %s", index)

        question, options = _extract_quiz_question_and_options(driver)
        if not question or len(options) < 2:
            logging.warning(
                "Could not extract question/options from the page. "
                "Ensure you are on a quiz question screen.",
            )
            break

        logging.info("Question %s text: %.80s", index, question.replace("\n", " "))

        if trimmed_context:
            augmented_question = (
                "Use the following book transcript to answer the quiz question.\n\n"
                f"Book transcript:\n{trimmed_context}\n\n"
                f"Quiz question:\n{question}"
            )
        else:
            augmented_question = question

        try:
            suggestion = llm_client.choose_answer(augmented_question, options)
        except Exception as exc:
            logging.error("LLM call failed for question %s: %s", index, exc)
            break

        overlay_message = f"Q{index}: Suggestion -> {suggestion}"
        _update_overlay(driver, overlay_message)
        logging.info("Suggestion for Q%s: %s", index, suggestion)

        if callable(on_question_result):
            try:
                on_question_result(index, question, options, suggestion)
            except Exception:
                pass

        user_input = input(
            "Press Enter to proceed to the next quiz question, or type 'q' to stop: "
        ).strip().lower()
        if user_input == "q":
            logging.info("Quiz assistant stopped by user after question %s.", index)
            break

    logging.info("Quiz assistant finished.")
