import logging
import time
from typing import List, Tuple

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


def auto_read_with_progress(driver: WebDriver, app_config: AppConfig) -> None:
    """Auto-scroll and move across multiple pages, with a console progress bar."""
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

    _ensure_reading_overlay(driver)
    try:
        page_text = _extract_page_text(driver)
    except Exception:
        page_text = ""
    _update_reading_overlay(driver, current_page, page_text)

    for _ in range(steps):
        driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")

        elapsed = time.time() - start_time
        progress = min(1.0, elapsed / total_seconds) if total_seconds > 0 else 1.0
        filled = int(bar_width * progress)
        bar = "#" * filled + "-" * (bar_width - filled)
        print(
            f"\rReading progress: [{bar}] {int(elapsed)}/{total_seconds} sec",
            end="",
            flush=True,
        )

        # If we're near the bottom of the current page, try going to the next page.
        try:
            at_bottom = bool(
                driver.execute_script(
                    "return (window.innerHeight + window.scrollY) >= "
                    "(document.body.scrollHeight - 10);"
                )
            )
        except Exception:
            at_bottom = False

        if at_bottom:
            new_page = _get_current_page(driver)
            if new_page == current_page and _click_next_page(driver):
                # Give the new page a moment to render, then reset scroll and update page.
                time.sleep(1.0)
                driver.execute_script("window.scrollTo(0, 0);")
                current_page = _get_current_page(driver)
                try:
                    page_text = _extract_page_text(driver)
                except Exception:
                    page_text = ""
                _update_reading_overlay(driver, current_page, page_text)

        remaining = total_seconds - elapsed
        if remaining <= 0:
            break
        time.sleep(step_seconds)

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


def _extract_page_text(driver: WebDriver, max_chars: int = 600) -> str:
    script = """
    return (function() {
        function getText(el) {
            return el && el.innerText ? el.innerText.trim() : '';
        }

        var container =
            document.querySelector('app-page, app-reader-page, .page, .page-wrapper, .page-content') ||
            document.querySelector('main, .content, .reader');

        var text = getText(container);
        if (!text) {
            text = getText(document.body);
        }

        if (text.length > arguments[0]) {
            text = text.substring(0, arguments[0]) + '\n…';
        }
        return text;
    })();
    """
    text = driver.execute_script(script, max_chars) or ""
    return str(text)


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


def run_quiz_assistant(driver: WebDriver, app_config: AppConfig, llm_client: LLMClient) -> None:
    """Loop over quiz questions, show LLM suggestions in an in-page overlay."""
    max_questions = app_config.automation.max_quiz_questions
    logging.info("Starting quiz assistant for up to %s questions.", max_questions)

    _ensure_overlay(driver)

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

        try:
            suggestion = llm_client.choose_answer(question, options)
        except Exception as exc:
            logging.error("LLM call failed for question %s: %s", index, exc)
            break

        overlay_message = f"Q{index}: Suggestion -> {suggestion}"
        _update_overlay(driver, overlay_message)
        logging.info("Suggestion for Q%s: %s", index, suggestion)

        user_input = input(
            "Press Enter to proceed to the next quiz question, or type 'q' to stop: "
        ).strip().lower()
        if user_input == "q":
            logging.info("Quiz assistant stopped by user after question %s.", index)
            break

    logging.info("Quiz assistant finished.")
