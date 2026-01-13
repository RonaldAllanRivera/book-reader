# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Screenshot-based reading workflow in the Tkinter GUI:
  - `Paste Screenshot` button to capture any image currently on the clipboard (Windows Print Screen, Snipping Tool, Lightshot, etc.).
  - Thumbnail strip showing all pasted page screenshots.
  - `2. Transcribe Book Screenshots` button to batch-run local OCR (easyocr) over all pasted pages, with a progress bar.
  - Full-page transcripts logged in the GUI, with a progress bar indicating transcription progress.
- Local OCR implementation using `easyocr` + `Pillow` + `numpy` (no external Tesseract executable required).
- Convenience controls in the Tkinter GUI:
  - `Clear All` button to reset book transcripts/screenshots, quiz transcripts/screenshots, and clear the GUI log output.
  - `Enable Easy Screenshot for Book` checkbox (Ubuntu-friendly) that automatically appends new clipboard images as book page screenshots after `PrtSc` + `Ctrl+C`.
  - `Enable Easy Screenshot for Quiz` checkbox (Ubuntu-friendly) that automatically pastes new clipboard images as quiz screenshots, runs quiz OCR, and triggers quiz answering.
    - The Book and Quiz easy-screenshot modes are mutually exclusive to avoid clipboard routing conflicts.
  - Scrollable book screenshot thumbnails (supports large sets like 100+ screenshots).
  - `Copy Book Transcript` button to copy all transcribed book pages to the clipboard in page order.
  - `Lexile Levels` button that reads `LEXILE_FROM` and `LEXILE_TO` from the environment and fills the platform's Lexile Level **From/To** inputs via Selenium/JavaScript.
  - Keyboard shortcuts: `Ctrl+B`/`Ctrl+Q` for pasting book/quiz screenshots and `Ctrl+N`/`Ctrl+W` for transcribing book/quiz screenshots.
  - `Clear BOOK Screenshots` button and per-thumbnail `X` buttons to remove individual book page screenshots and keep transcripts in sync.
- Screenshot-based quiz workflow in the Tkinter GUI:
  - `Paste QUIZ Screenshot` button to capture the current quiz question (question + options) from the clipboard.
  - `Transcribe Quiz Screenshot` button to run OCR over the quiz image and log the raw OCR text.
  - `3. Answer Quiz from Book` button to parse the OCR text into question + options, combine it with the transcribed book text, and call the LLM for a suggested answer.
  - Clear quiz result blocks in the GUI log showing the question, options, and which option the AI chose.
- Browser driver selection in the Tkinter GUI:
  - Driver dropdown with support for **Auto**, **Snap Chromium**, **Selenium Manager**, **WebDriverManager**, and **Custom (env paths)**.
  - Improved Ubuntu compatibility by detecting snap-wrapper `chromedriver` and using the snap-installed Chromium binary when needed.
  - Additional driver startup logging (including full tracebacks in the GUI log on failures).
- Improved error and traceback logging in the GUI.
- Ubuntu launcher helpers:
  - `run_gui.sh` script to launch the Tkinter GUI using the project-local `.venv`.
  - `BookReader.desktop` desktop entry for double-click launching on Ubuntu.

### Changed
- Tkinter GUI reading flow:
  - Previously attempted to drive the browser directly (auto-scroll and live OCR from Selenium screenshots).
  - Now treats the browser purely as a viewer; reading is performed from pasted screenshots in the GUI for greater reliability and user control.
 - Quiz assistant flow:
   - Recommended path is now the Tkinter GUI screenshot-based quiz workflow.
   - The legacy DOM-based quiz extraction with in-page overlay remains available as an optional console/overlay mode for advanced use.

### Existing Features
- Manual login to a web-based reading/quiz platform via Selenium-controlled Chrome.
- Quiz assistant that can either:
  - Extract questions/options from the platform DOM (console/overlay mode), or
  - Work from OCR of pasted quiz screenshots in the Tkinter GUI.
