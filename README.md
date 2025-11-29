# Book Reader – Scholastic Learning Zone Automation

A small but production-grade Python automation tool that assists with reading and quizzes in **Scholastic Learning Zone (SLZ)**.

The goal is to behave like a focused personal assistant:

- Open the SLZ student login URL in Chrome.
- Let you log in manually, then continue the automation.
- Help you read a chosen book by **transcribing page screenshots** with local OCR (easyocr), showing a progress indicator and full transcripts.
- After reading, help with the associated **quiz** by **transcribing quiz screenshots** and calling a **remote OpenAI‑compatible LLM** to suggest the best answers, using the book transcript as context.
- Surface quiz questions, options, and the AI suggestion **directly in the Tkinter GUI log**, so you can quickly see what to click in SLZ.

This repository is structured, configurable, and testable in a way that reflects modern full‑stack engineering practices.

> **Disclaimer**
> This project is intended for **personal learning assistance only**. Respect Scholastic’s Terms of Service and your school’s policies. Do not use it for cheating, mass-scraping, or abusive traffic.

---

## Features

- **Chrome browser automation (Selenium)**
  - Uses `webdriver-manager` to download and manage the correct ChromeDriver.
  - Supports headless and non-headless modes via config.

- **Manual, explicit login flow**
  - Reads `SLZ_BASE_URL` (deep login URL) from environment or `config.yaml`.
  - Always opens the SLZ login page in Chrome and asks you to log in manually.
  - Only proceeds once you confirm in the console that you are logged in.

- **Config-driven behavior**
  - Central `config.yaml` + `.env` with typed dataclass configuration.
  - Tunable reading duration, scroll speed, and maximum quiz questions.

- **LLM-powered quiz assistance (remote, OpenAI-compatible)**
  - Uses a pluggable `LLMClient` abstraction.
  - Ships with a `RemoteLLMClient` that targets an OpenAI-style `/chat/completions` endpoint.
  - Prompts are specialized for reading comprehension and multiple-choice questions.

-- **Local OCR for image-based books**
  - Uses **easyocr** (pure-Python OCR) together with `Pillow`/`numpy` to read text from screenshots of book pages rendered as images.
  - OCR runs locally on your CPU (no extra API cost); accuracy depends on page quality.

- **Tkinter desktop controller (recommended workflow)**
  - Small GUI window to launch SLZ, manage **book** and **quiz** screenshots, and call the quiz assistant.
  - Supports a **screenshot-based reading workflow**: paste page screenshots from the clipboard, see thumbnails for all pages, and batch-transcribe them with local OCR.
  - Supports a **screenshot-based quiz workflow**: paste quiz screenshots from the clipboard, transcribe them with OCR, and send question + options (plus optional book context) to the LLM.
  - Quiz results (question, options, and which option the AI chose) are logged clearly in the GUI so you can manually click the best choice in SLZ.
  - Chrome remains a normal external window; Tkinter is only the control panel.

- **User experience focus**
  - Reading phase (GUI) shows a **progress bar** for batch OCR of pasted book pages and logs full-page transcripts.
  - Quiz suggestions are shown in a clear text block in the Tkinter GUI log, highlighting the option the AI chose.
  - Optional console/overlay mode can still show suggestions inside the SLZ tab via an in-page overlay.

- **Engineering practices**
  - Clear layering: `config` / `automation` / `ai` / `scripts`.
  - Uses Python `dataclasses` for configuration.
  - Centralized logging with structured messages.
  - Designed for extension (more SLZ programs, different LLM providers, fully automated answers, etc.).

---

## Project Structure

```text
book-reader/
  PLAN.md                   # High-level design document
  README.md                 # This file
  requirements.txt          # Python dependencies
  config.yaml               # Non-secret configuration (URLs, timings, etc.)
  .env.example              # Example environment variables
  .env                      # Your real secrets (ignored by Git)
  src/
    __init__.py
    main.py                 # Main entrypoint (login + orchestration)
    automation/
      __init__.py
      browser.py            # Selenium Chrome setup and options
      workflows.py          # Login flow (auto + manual fallback), later reading/quiz flows
    ai/
      __init__.py
      base.py               # `LLMClient` interface
      remote_client.py      # OpenAI-style remote LLM implementation
      prompts.py            # Prompt builder for quiz questions
    config/
      __init__.py
      settings.py           # Typed configuration loading from .env + config.yaml
    ui/
      __init__.py
      tk_gui.py             # Tkinter desktop controller
  scripts/
    run_slz_automation.py   # CLI entrypoint (ensures src/ on sys.path and calls main)
    run_gui.py              # Tkinter GUI entrypoint
```

The design deliberately keeps **SLZ-specific selectors** and **LLM wiring** in their own modules so they can be adapted without rewriting the entire application.

---

## Prerequisites

- **Operating system**: Windows (tested) – other platforms may work with minor adjustments.
- **Python**: 3.11+ recommended.
- **Browser**: Google Chrome installed and up-to-date.
- **Accounts**:
  - Valid **Scholastic Learning Zone** student account.
  - Valid **OpenAI API key** (or compatible provider with the same API surface).

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/book-reader.git
cd book-reader
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
# On PowerShell, you might use: .venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs Python libraries including `easyocr`, `Pillow`, and `numpy` used for local OCR.

### 3.5 Local OCR for image-based books (easyocr)

The reading assistant can use **easyocr** to extract text from books rendered as images.

- No separate system installer is required (no `tesseract.exe`).
- The first time OCR runs, `easyocr` will download its model weights; this may take a minute.
- The models are cached on disk for future runs.

There is no extra configuration needed; OCR is enabled automatically when you run auto-reading from the console or batch transcription from the Tkinter GUI.

### 4. Configure environment variables

1. Copy the example env file:

```bash
copy .env.example .env
```

2. Edit `.env` and fill in your values:

   ```env
   OPENAI_API_KEY=sk-...your_real_key...
   SLZ_BASE_URL=https://slz02.scholasticlearningzone.com/resources/dp-int/dist/#/login3/student/PHL9tjd
   ```

   Notes:
   - `OPENAI_API_KEY` is required for the LLM quiz assistance.
   - `SLZ_BASE_URL` should be the exact SLZ login URL you normally use.

### 5. Adjust config (optional)

Open `config.yaml` to tune behavior:

```yaml
slz:
  base_url: "https://slz02.scholasticlearningzone.com/resources/dp-int/dist/#/login3/student/PHL9tjd"

automation:
  book_title: ""                 # TODO: used later for book selection
  read_scroll_step_seconds: 2.0   # How often to scroll while "reading"
  read_total_seconds: 120         # Total time to keep scrolling
  max_quiz_questions: 20          # Safety cap on number of quiz questions
  headless: false                 # Set true to run Chrome without UI

llm:
  provider: "openai"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"           # Cost-efficient model for quiz assistance
```

The environment variable `SLZ_BASE_URL` overrides `slz.base_url` in `config.yaml`, which makes it easy to keep secrets out of version control.

---

## How to Run

From the project root with the virtual environment active:

```bash
python scripts\run_slz_automation.py
```

Current flow:

1. **Configuration & driver setup**
   - Loads `.env` and `config.yaml` via `config.settings.load_config()`.
   - Initializes Chrome WebDriver with `automation.browser.create_driver()`.

2. **Login phase** (`automation.workflows.login`)
   - Opens `SLZ_BASE_URL` (or `slz.base_url` if no env override).
   - Asks you to log in manually in the browser window.
   - Continues only after you press Enter in the console to confirm you are logged in.

3. **Post-login: Tkinter GUI workflow (recommended)**

   - After login, the recommended workflow is to use the Tkinter GUI for a **paste-screenshot + transcription + quiz assistant** workflow.

### How to Run – Tkinter GUI (recommended workflow)

For image-based books and quizzes, the Tkinter GUI provides a **paste-screenshot + transcription + quiz assistant** workflow.

1. **Start the GUI**

   ```bash
   python scripts\run_gui.py
   ```

2. **Launch SLZ and log in**

   - In the GUI, click **"1. Launch SLZ / Login"** to open the SLZ login page in Chrome.
   - Optionally click **"Fill Login Form"** to auto-fill username/password from your `.env`, then click the Login button manually in Chrome.

3. **Capture book page screenshots**

   - Navigate to the book reading view in Chrome.
   - For each page you want to "read":
     - Use Windows Snipping Tool (**Win+Shift+S**), `Print Screen`, `Alt+Print Screen`, or a tool like Lightshot to capture the page.
     - Ensure the screenshot ends up on the clipboard (choose *Copy* in your capture tool).
     - Switch to the Tk window and click **"Paste BOOK Screenshot"**.
     - The GUI will:
       - Store the image in a page list.
       - Show a preview of the latest page and a thumbnail for each pasted screenshot.

4. **Batch-transcribe all pasted book pages**

   - After pasting all pages (e.g., 10–50 screenshots), click **"2. Transcribe Book Screenshots"**.
   - The GUI will:
     - Run local OCR (easyocr) over each screenshot.
     - Update a **progress bar** as it processes pages.
     - Log the **full transcription per page** in the text area, prefixed with `Transcript page N:`.
   - While transcription is running, clicking the same button again requests a graceful stop after the current page.

5. **Transcribe quiz questions from screenshots**

   - In Chrome, navigate to the quiz for the same book.
   - For each question:
     - Capture a screenshot that includes the full question and all answer options.
     - Ensure the screenshot is on the clipboard.
     - In the GUI, click **"Paste QUIZ Screenshot"**.
     - Then click **"Transcribe Quiz Screenshot"** to run OCR on that image.
     - The GUI logs the raw quiz OCR text so you can see what was read.

6. **Ask the AI to answer the quiz from the book**

   - With book pages already transcribed and a quiz screenshot transcribed:
     - Click **"3. Answer Quiz from Book"**.
   - The GUI will:
     - Parse the OCR text into a question + options.
     - Build a book context from the transcribed book pages.
     - Call the LLM to choose the best option.
     - Log a clear block like:

       ```text
       === Quiz (from OCR) ===
       <question>

       Options:
       A. ...  <<< AI CHOSE THIS
       B. ...
       C. ...
       D. ...

       >>> Suggested answer (raw LLM response): A. ...
       ```

   - You then manually click the suggested answer in the SLZ quiz UI.

---

## Design & Architecture Notes

- **Separation of concerns**
  - `config` only knows about configuration and does not depend on Selenium or OpenAI.
  - `automation` only knows about the browser and SLZ UI.
  - `ai` only knows about prompts and LLM APIs.

- **Typed configuration**
  - Uses `dataclasses` for `SLZConfig`, `AutomationConfig`, `LLMConfig`, and `AppConfig`.
  - Centralized config loading makes it easy to enforce required values and provide safe defaults.

- **LLM abstraction**
  - `LLMClient` defines `choose_answer(question, options)`.
  - The default `RemoteLLMClient` is OpenAI-style, but a local or alternative provider can be plugged in later without touching the calling code.

- **Resilience**
  - Manual login keeps you in control and avoids brittle credential automation.
  - Errors from the LLM layer are surfaced via logs with helpful context.

---

## Roadmap

Planned enhancements (some already partially implemented in code/PLAN.md):

- **Book selection** by title or index from the SLZ shelf.
- **Reading automation (console/overlay mode)**:
  - Auto-scroll through the book at a configurable pace.
  - Terminal and/or overlay-based progress bar.
- **Quiz assistant (enhancements)**:
  - More robust parsing of quiz OCR for a variety of layouts.
  - Optional ability to re-ask or override suggestions from the GUI.
- **Provider flexibility**:
  - Additional `LLMClient` implementations for local models or other cloud providers.
- **Testing harness**:
  - Unit tests for prompt building and configuration.
  - Optional integration tests against a mock SLZ page.

---

## Security & Ethics

- Do **not** commit your real `.env` or API keys.
- Only point the automation at accounts you own and have permission to use.
- Use this project as a study helper, not as a way to bypass learning.

---

## License

You can choose and add a license that matches your needs (for example, MIT). Until then, treat this code as “all rights reserved” by default.
