# Book Reader Automation – PLAN

## 1. Goals
- **Assist with online reading & quizzes** in a browser-based book platform while keeping you in control:
  - Open a real browser and log in with saved credentials (from `.env` / config, not hardcoded).
  - Navigate to a selected book and read it.
  - Use a **Tkinter desktop GUI** to:
    - Capture **book pages** as screenshots from the clipboard and transcribe them with local OCR (easyocr), showing a progress bar and full-page transcripts.
    - Capture **quiz questions** as screenshots from the clipboard, transcribe them with OCR, and ask an AI model for the best answer using the book transcript as context.
  - You always **manually click the answers** in the reading platform (no auto-answering).
- **Use free / low‑cost AI** where possible.

---

## 2. High-Level Architecture

- **Client machine**: Windows or Linux (Ubuntu supported).
- **Main components (Python)**:
  - **Automation layer**: Selenium (or Playwright) driving a real browser (Chrome/Edge/Firefox).
  - **App layer**: Python application orchestrating the workflow, with a simple GUI.
  - **AI layer**: Pluggable LLM client:
    - Default: free / low-cost models via an open API provider (e.g., OpenAI-compatible but with free tier, or other providers).
    - Optional: local model (e.g., using `llama.cpp`/`ollama` or Hugging Face transformers) if you want fully free but need local compute.

---

## 3. Technology Choices

### 3.1 Browser Automation
- **Preferred**: Playwright for Python
  - Pros: modern, resilient selectors, auto-wait, good for complex SPAs, better for handling dynamic pages.
  - Cons: Heavier initial setup; needs browser binaries.
- **Alternative**: Selenium with selectable driver backends
  - Cross-platform driver provisioning differs across OS and packaging.
  - The Tkinter GUI supports selecting a driver mode at runtime (recommended: **Auto**).

**Plan**: Start with **Selenium** (common, simple) and keep abstraction so we could swap to Playwright later.

### 3.2 AI / LLM

- **Constraints**:
  - You want to avoid a paid OpenAI API key if possible.
  - Need decent reading comprehension & multiple-choice reasoning.

- **Options**:
  - **Hosted free tiers** (OpenAI-compatible APIs):
    - Some providers offer small free quotas/month. We’ll design for a pluggable `LLMClient` interface so you can pick provider.
  - **Local model**:
    - Use `ollama` or similar, run a model like `llama3` locally.
    - Python talks to it via HTTP (`requests`) or local python bindings.

**Plan**: 
- Implement a **generic LLM interface** with two implementations:
  - `RemoteLLMClient` (for any OpenAI-compatible HTTP endpoint; you configure base URL and API key via env vars).
  - `LocalLLMClient` (for calling local model via HTTP or CLI).
- Default to `LocalLLMClient` in config to keep it **free**, and allow you to switch to a hosted provider later by editing a config file / env vars.

### 3.3 Configuration & Secrets
- **Config file**: `config.yaml` or `.env` for
  - Site username, site password (or read from OS keyring) for the reading/quiz platform.
  - Book selector strategy (title / index).
  - LLM type: `local` or `remote`.
  - LLM parameters: base URL, model name, temperature, max tokens.
- Never commit real credentials.

---

## 4. Workflow Design

### 4.1 Login & Navigation

1. Start the Tkinter GUI: `python scripts/run_gui.py` (or equivalent entrypoint).
2. Script steps (reading always followed by quiz assist):
   - Launch browser (Selenium WebDriver).
   - Go to the configured base URL of the reading platform.
   - Locate username/password fields and login button.
   - Submit and wait for landing page.
   - Navigate to the selected program / classroom / bookshelf.
   - Optionally use the GUI **"Lexile Levels"** button (configured via `LEXILE_FROM`/`LEXILE_TO` in `.env`) to pre-fill the Lexile Level **From/To** filters on the Library page before choosing a book.
   - Choose book by:
     - Title match (preferred)
     - Or first/Nth book if title selectors are hard.

### 4.2 Reading Automation

- **Tkinter GUI, screenshot-based (current implementation):**
  - Open the book reader in your chosen platform manually in Chrome.
  - For each page you want to "read":
    - Use Windows Snipping Tool / Print Screen / Lightshot to capture the page (ensure it is copied to the clipboard).
    - In the Tk GUI, click **"Paste BOOK Screenshot"** to add that page. All pages are shown as thumbnails and the latest page appears in a preview area.
    - On Ubuntu, you can optionally enable **"Enable Easy Screenshot for Book"** (below the Driver dropdown) to automatically append new clipboard images as book page screenshots after you take a screenshot and copy it (e.g., `PrtSc` then `Ctrl+C`).
  - When you have pasted all pages for a session, click **"2. Transcribe Book Screenshots"**:
    - The GUI batch-runs local OCR (easyocr) over each screenshot.
    - A **progress bar** shows how many pages have been processed.
    - The **full transcript per page** is logged in the GUI text area as `Transcript page N:` blocks.
  - You can click the same button again while it is running to request a graceful stop after the current page.
  - Reset controls:
    - **Clear BOOK Screenshots** clears the current book screenshots and associated transcripts.
    - **Clear All** clears both book and quiz screenshots/transcripts and resets the GUI state.

### 4.3 Quiz Capture & AI Suggestion

- **Tkinter GUI, screenshot-based quiz (current implementation):**
  - In Chrome, open the quiz for the book you just read.
  - For each question:
    - Capture a screenshot that includes the full question text and all options.
    - With that screenshot on the clipboard, click **"Paste QUIZ Screenshot"** in the Tk GUI.
    - Click **"Transcribe Quiz Screenshot"** to run OCR and log the quiz text.
    - After OCR completes, the GUI automatically triggers the quiz answer flow using the current book transcript as context.
    - You can also click **"3. Answer Quiz from Book"** manually to re-run the answer if needed:
      - The GUI parses the OCR text into a single question string and a list of options.
      - It builds a book context string from all transcribed book pages.
      - It sends question + options (+ optional book context) to the configured LLM with a strict reading-comprehension prompt.
      - The result is logged in the GUI in a clear block, e.g.:
        - `=== Quiz (from OCR) ===`
        - Question line(s)
        - `Options:`
        - `A. ...`
        - `B. ...  <<< AI CHOSE THIS`
        - ...
        - `>>> Suggested answer (raw LLM response): ...`
    - You read the suggestion and **manually click** the chosen answer in the quiz UI.

- Optional future enhancement: allow you to **re-ask** the AI if you disagree with a suggestion (e.g., via a button in the GUI).

---

## 5. Code Structure

Planned project structure:

```text
book-reader/
  PLAN.md
  requirements.txt
  .env (not committed)
  config.yaml
  src/
    __init__.py
    main.py
    automation/
      __init__.py
      browser.py       # Selenium setup & helpers
      selectors.py     # Encapsulated locators for site pages
      workflows.py     # High-level flows: login, open_book, read_book, open_quiz, next_question
    ai/
      __init__.py
      base.py          # LLMClient interface
      local_client.py  # For local models (ollama or similar)
      remote_client.py # For hosted/OpenAI-compatible APIs
      prompts.py       # System & user prompt builders for quiz
    config/
      __init__.py
      settings.py      # Load env + yaml into typed config objects
    ui/
      __init__.py
      tk_gui.py        # Tkinter desktop controller for launching flows and viewing status
  scripts/
    run_gui.py             # Entry point for the Tkinter GUI controller
```

---

## 6. Best Practices & Non-Functional Requirements

- **Respect terms of service**
  - Keep automation rate low.
  - No mass-scraping; use only for your personal learning.
- **Security**
  - Store credentials only in env vars / keyring, not in code.
  - Optionally use `python-keyring` for OS-secure storage.
- **Maintainability**
  - Encapsulate site-specific selectors in `selectors.py` so maintenance is localized if UI changes.
  - Use `logging` module (not `print`) with levels: INFO/DEBUG/ERROR.
- **Reliability**
  - Explicit waits instead of `time.sleep` where possible.
  - Try/except around critical steps with helpful errors and screenshots on failure.
- **Configurability**
  - All tunables in config: scroll delays, max quiz questions, LLM provider.
- **Extensibility**
  - Design so we can later:
    - Support multiple reading programs / platforms.
    - Support full auto-answer (if you decide to trust the LLM that much).

---

## 7. Step-by-Step Implementation Plan

1. **Bootstrap project**
   - Create `requirements.txt` with base deps: `selenium`, `python-dotenv`, `PyYAML`, `requests` (and optionally `keyring`).
   - Set up `src/` structure as above.

2. **Config system**
   - Implement `config/settings.py` to load:
     - `.env` for secrets.
     - `config.yaml` for non-sensitive settings.
   - Define data classes for `SLZConfig`, `LLMConfig`, `AutomationConfig`.

3. **Selenium browser wrapper**
   - Implement `automation/browser.py`:
     - Initialize WebDriver (e.g., Chrome) with options.
     - Helper methods: `find_click`, `wait_for`, `get_text`, `scroll`, `screenshot`.

4. **Site selectors & workflows**
   - Implement `automation/selectors.py` with locator constants/placeholders.
   - Implement `automation/workflows.py`:
     - `login(driver, config)`
     - `open_book(driver, book_title)`
     - `start_reading(driver)`
     - `auto_read(driver, duration, scroll_step)`
     - `stop_reading(driver)`
     - `open_quiz(driver)`
     - `get_current_question(driver)` → returns text + options.

5. **AI layer**
   - Implement `ai/base.py` with `LLMClient` abstract base class.
   - Implement `ai/local_client.py`:
     - Call local HTTP endpoint for `ollama` or similar.
   - Implement `ai/remote_client.py`:
     - Generic OpenAI-compatible client (URL, key, model from config).
   - Implement `ai/prompts.py` to build prompts.

6. **Quiz assistant logic**
   - In `main.py` or dedicated module:
     - Loop through quiz questions:
       - Scrape `question, options`.
       - Call `llm_client.choose_answer(...)`.
       - Show suggestion in console.
       - Wait for user keystroke to move to next question.

7. **Testing & Hardening**
   - Write small tests for text parsing & prompt formatting.
   - Add error handling and clear logs.
   - Add a `--dry-run` mode that just logs actions without clicking.

---

## 8. Next Actions

- Implement project skeleton & `requirements.txt`.
- Decide whether you prefer **local model** (fully free but heavier on your machine) or **hosted free-tier provider** first; configure `LLMClient` accordingly.
- Once the skeleton exists, we’ll:
  - Inspect the target site HTML structure in your browser dev tools.
  - Fill in real selectors in `selectors.py`.
  - Iterate on robustness of quiz extraction & AI suggestions.
