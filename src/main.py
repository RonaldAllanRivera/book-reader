import logging

from config.settings import load_config
from automation.browser import create_driver
from automation.workflows import auto_read_with_progress, login, run_quiz_assistant
from ai.remote_client import RemoteLLMClient


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = load_config()
    logging.info("Configuration loaded successfully.")

    driver = create_driver(config.automation, driver_mode=None)
    logging.info("Chrome WebDriver initialized.")

    try:
        login(driver, config)
        logging.info("Login phase completed.")

        logging.info(
            "In the browser, navigate to the book you want to read and open the reading view. "
            "Then return to this console and press Enter to start auto-reading."
        )
        input("When the book reading view is open, press Enter here to start auto-reading...")

        auto_read_with_progress(driver, config)

        logging.info(
            "If a quiz is available for this book, navigate to the first quiz question in the "
            "browser, then return here and press Enter to start the quiz assistant."
        )
        input("When you are on the first quiz question, press Enter here to continue...")

        llm_client = RemoteLLMClient(config.llm)
        run_quiz_assistant(driver, config, llm_client)
    finally:
        driver.quit()
        logging.info("Browser closed.")


if __name__ == "__main__":
    main()
