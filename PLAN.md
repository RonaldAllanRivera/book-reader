# Scholastic Learning Zone Automation – PLAN

## 1. Goals
- **Automate reading workflow** in Scholastic Learning Zone (SLZ):
  - Open browser
  - Log in with saved credentials (not hardcoded in repo)
  - Navigate to a selected book
  - Click `READ` / `START READING`
  - Optionally auto-scroll pages for a configurable time
  - Click `STOP READING`
  - Click `QUIZ` and show questions
- **Assist with quiz answers**:
  - Capture quiz questions and options from the page
  - Use an AI model to propose the best answer
  - You manually click the answer (no auto-answering to reduce risk & keep control)
- **Use free / low‑cost AI** where possible.

---

## 2. High-Level Architecture

- **Client machine**: Your Windows PC.
- **Main components (Python)**:
  - **Automation layer**: Selenium (or Playwright) driving a real browser (Chrome/Edge/Firefox).
  - **App layer**: Python application orchestrating the workflow, with a simple CLI or small GUI.
  - **AI layer**: Pluggable LLM client:
    - Default: free / low-cost models via an open API provider (e.g., OpenAI-compatible but with free tier, or other providers).
    - Optional: local model (e.g., using `llama.cpp`/`ollama` or Hugging Face transformers) if you want fully free but need local compute.

---

## 3. Technology Choices

### 3.1 Browser Automation
- **Preferred**: Playwright for Python
  - Pros: modern, resilient selectors, auto-wait, good for complex SPAs, better for handling dynamic pages.
  - Cons: Heavier initial setup; needs browser binaries.
- **Alternative**: Selenium with webdriver-manager
  - Easier mental model; many examples.

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
  - SLZ username, SLZ password (or read from OS keyring).
  - Book selector strategy (title / index).
  - LLM type: `local` or `remote`.
  - LLM parameters: base URL, model name, temperature, max tokens.
- Never commit real credentials.

---

## 4. Workflow Design

### 4.1 Login & Navigation

1. Start Python script: `python run_slz_automation.py`.
2. Script steps (reading always followed by quiz assist):
   - Launch browser (Selenium WebDriver).
   - Go to `https://scholasticlearningzone.com`.
   - Locate username/password fields and login button.
   - Submit and wait for landing page.
   - Navigate to the selected program / classroom / bookshelf.
   - Choose book by:
     - Title match (preferred)
     - Or first/Nth book if title selectors are hard.

### 4.2 Reading Automation

- After opening book page:
  - Click `READ` button.
  - Wait for reading iframe / new window.
  - Optionally **auto-scroll** slowly through pages/viewport:
    - Scroll step every X seconds.
    - Scroll duration configurable.
    - Show a reading progress bar/indicator (e.g., based on elapsed time or page count) so you can see reading progress while it runs.
  - Click `STOP READING` (or close reading window) when done.

### 4.3 Quiz Capture & AI Suggestion

- After reading is done:
  - Click `QUIZ` button or equivalent.
  - For each question page:
    - Scrape:
      - Question text
      - Answer options text
    - Build a structured payload, e.g.:
      ```json
      {
        "question": "...",
        "options": ["A ...", "B ...", "C ...", "D ..."]
      }
      ```
    - Send that to LLM with a **strict system prompt**:
      - You are a reading comprehension assistant.
      - Choose the single best option.
      - Answer only with the letter and full option text.
    - Display AI answer inside the same browser tab using a small in-page overlay/panel injected via JavaScript (e.g., fixed box at bottom/right):
      - `Q1: Suggestion -> B: ...`
    - You manually click the answer.

- Optional: ask if you want to **re-ask** AI if you disagree.

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
      selectors.py     # Encapsulated locators for SLZ pages
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
    run_slz_automation.py
    run_gui.py         # Entry point for the Tkinter GUI controller
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
  - Encapsulate SLZ-specific selectors in `selectors.py` so maintenance is localized if UI changes.
  - Use `logging` module (not `print`) with levels: INFO/DEBUG/ERROR.
- **Reliability**
  - Explicit waits instead of `time.sleep` where possible.
  - Try/except around critical steps with helpful errors and screenshots on failure.
- **Configurability**
  - All tunables in config: scroll delays, max quiz questions, LLM provider.
- **Extensibility**
  - Design so we can later:
    - Support multiple programs within SLZ.
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

4. **SLZ selectors & workflows**
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

7. **CLI / Runner script**
   - `scripts/run_slz_automation.py`:
     - Parse CLI args / interactive menu.
     - Initialize config, LLM client, WebDriver.
     - Run chosen workflow.

8. **Testing & Hardening**
   - Write small tests for text parsing & prompt formatting.
   - Add error handling and clear logs.
   - Add a `--dry-run` mode that just logs actions without clicking.

---

## 8. Next Actions

- Implement project skeleton & `requirements.txt`.
- Decide whether you prefer **local model** (fully free but heavier on your machine) or **hosted free-tier provider** first; configure `LLMClient` accordingly.
- Once the skeleton exists, we’ll:
  - Inspect SLZ HTML structure in your browser dev tools.
  - Fill in real selectors in `selectors.py`.
  - Iterate on robustness of quiz extraction & AI suggestions.
