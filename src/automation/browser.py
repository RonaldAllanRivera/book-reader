import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import AutomationConfig


def _is_snap_chromedriver_wrapper(path: str) -> bool:
    try:
        wrapper = Path(path)
        if not wrapper.is_file():
            return False
        if wrapper.stat().st_size > 4096:
            return False
        content = wrapper.read_text(encoding="utf-8", errors="ignore")
        return "/snap/bin/chromium.chromedriver" in content
    except Exception:  # noqa: BLE001
        return False


def _find_snap_chromium_binary() -> str:
    candidates = [
        Path("/snap/chromium/current/usr/lib/chromium-browser/chrome"),
        Path("/snap/chromium/current/usr/lib/chromium-browser/chromium"),
        Path("/snap/chromium/current/usr/lib/chromium-browser/chromium-browser"),
        Path("/snap/bin/chromium"),
    ]
    for candidate in candidates:
        try:
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)
        except Exception:  # noqa: BLE001
            continue
    return "/snap/bin/chromium"


def _create_snap_chromium_driver(options: ChromeOptions) -> webdriver.Chrome:
    snap_driver = Path("/snap/bin/chromium.chromedriver")
    snap_browser = Path(_find_snap_chromium_binary())
    if not snap_driver.exists() or not snap_browser.exists():
        raise RuntimeError(
            "Snap Chromium is not available at /snap/bin/chromium and /snap/bin/chromium.chromedriver.",
        )

    profiles_root = Path.home() / "snap" / "chromium" / "common" / "slz-selenium-profiles"
    profiles_root.mkdir(parents=True, exist_ok=True)
    user_data_dir = tempfile.mkdtemp(prefix="profile-", dir=str(profiles_root))
    log_path = str(Path(user_data_dir) / "chromedriver-verbose.log")
    chrome_log_path = str(Path(user_data_dir) / "chromium.log")
    try:
        Path(log_path).touch(exist_ok=True)
        Path(chrome_log_path).touch(exist_ok=True)
    except Exception:  # noqa: BLE001
        pass

    logging.info("Using snap chromedriver=%s", snap_driver)
    logging.info("Using snap chromium=%s", snap_browser)
    logging.info("ChromeDriver verbose log at %s", log_path)
    logging.info("Chromium log at %s", chrome_log_path)

    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--remote-debugging-pipe")
    options.add_argument("--enable-logging")
    options.add_argument("--v=1")
    options.add_argument(f"--log-file={chrome_log_path}")

    service_args = ["--verbose", f"--log-path={log_path}"]
    try:
        service = ChromeService(str(snap_driver), service_args=service_args, log_output=log_path)
    except TypeError:
        service = ChromeService(str(snap_driver))
        try:
            service.service_args = service_args
        except Exception:  # noqa: BLE001
            pass

    options.binary_location = str(snap_browser)
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    return driver


def create_driver(config: AutomationConfig, driver_mode: str = "auto") -> webdriver.Chrome:
    options = ChromeOptions()
    if config.headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    if sys.platform.startswith("linux"):
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    mode = (driver_mode or "auto").strip().lower()
    driver_path = os.getenv("CHROMEDRIVER_PATH", "").strip()
    chrome_binary = os.getenv("CHROME_BINARY", "").strip()

    if mode in ("custom", "custom-path"):
        if not driver_path:
            raise RuntimeError(
                "Custom driver mode requires CHROMEDRIVER_PATH to be set. Optionally set CHROME_BINARY.",
            )
        logging.info("Using CHROMEDRIVER_PATH=%s", driver_path)
        service = ChromeService(driver_path)
        if chrome_binary:
            logging.info("Using CHROME_BINARY=%s", chrome_binary)
            options.binary_location = chrome_binary
        driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        return driver

    chromedriver_on_path = shutil.which("chromedriver")
    chromedriver_candidate = chromedriver_on_path or "/usr/bin/chromedriver"
    chromedriver_is_snap_wrapper = bool(
        chromedriver_candidate and _is_snap_chromedriver_wrapper(chromedriver_candidate)
    )

    if mode in ("snap", "snap-chromium"):
        return _create_snap_chromium_driver(options)

    if mode in ("selenium-manager", "selenium"):
        if chromedriver_is_snap_wrapper:
            raise RuntimeError(
                "Selenium Manager mode is not usable because chromedriver on PATH is a snap wrapper (/usr/bin/chromedriver). "
                "Choose 'Snap Chromium' or 'Custom'.",
            )
        if chrome_binary:
            logging.info("Using CHROME_BINARY=%s", chrome_binary)
            options.binary_location = chrome_binary
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        return driver

    if mode in ("webdriver-manager", "wdm"):
        logging.info("Using webdriver-manager ChromeDriver download")
        service = ChromeService(ChromeDriverManager().install())
        if chrome_binary:
            logging.info("Using CHROME_BINARY=%s", chrome_binary)
            options.binary_location = chrome_binary
        driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        return driver

    if driver_path:
        logging.info("Auto mode: using CHROMEDRIVER_PATH=%s", driver_path)
        service = ChromeService(driver_path)
        if chrome_binary:
            logging.info("Using CHROME_BINARY=%s", chrome_binary)
            options.binary_location = chrome_binary
        driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        return driver

    if chromedriver_is_snap_wrapper:
        logging.info("Auto mode: detected snap-wrapper chromedriver; using snap Chromium backend")
        return _create_snap_chromium_driver(options)

    if chrome_binary:
        logging.info("Auto mode: using CHROME_BINARY=%s", chrome_binary)
        options.binary_location = chrome_binary

    if not chromedriver_on_path:
        logging.info("Auto mode: no chromedriver on PATH; using Selenium Manager")
        driver = webdriver.Chrome(options=options)
        driver.maximize_window()
        return driver

    logging.info("Auto mode: using chromedriver on PATH: %s", chromedriver_on_path)
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver
