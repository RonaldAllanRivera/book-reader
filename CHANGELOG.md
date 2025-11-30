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
 - Screenshot-based quiz workflow in the Tkinter GUI:
   - `Paste QUIZ Screenshot` button to capture the current quiz question (question + options) from the clipboard.
   - `Transcribe Quiz Screenshot` button to run OCR over the quiz image and log the raw OCR text.
   - `3. Answer Quiz from Book` button to parse the OCR text into question + options, combine it with the transcribed book text, and call the LLM for a suggested answer.
   - Clear quiz result blocks in the GUI log showing the question, options, and which option the AI chose.
 - Convenience controls in the Tkinter GUI:
   - `Lexile Levels` button that reads `LEXILE_FROM` and `LEXILE_TO` from the environment and fills the platform's Lexile Level **From/To** inputs via Selenium/JavaScript.
   - Keyboard shortcuts: `Ctrl+B`/`Ctrl+Q` for pasting book/quiz screenshots and `Ctrl+N`/`Ctrl+W` for transcribing book/quiz screenshots.
   - `Clear BOOK Screenshots` button and per-thumbnail `X` buttons to remove individual book page screenshots and keep transcripts in sync.

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
