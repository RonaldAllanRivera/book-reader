# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Screenshot-based reading workflow in the Tkinter GUI:
  - `Paste Screenshot` button to capture any image currently on the clipboard (Windows Print Screen, Snipping Tool, Lightshot, etc.).
  - Thumbnail strip showing all pasted page screenshots.
  - `Transcribe Screenshots` button to batch-run local OCR (easyocr) over all pasted pages.
  - Full-page transcripts logged in the GUI, with a progress bar indicating transcription progress.
- Local OCR implementation using `easyocr` + `Pillow` + `numpy` (no external Tesseract executable required).

### Changed
- Tkinter GUI reading flow:
  - Previously attempted to drive the browser directly (auto-scroll and live OCR from Selenium screenshots).
  - Now treats the browser purely as a viewer; reading is performed from pasted screenshots in the GUI for greater reliability and user control.

### Existing Features
- Manual login to Scholastic Learning Zone (SLZ) via Selenium-controlled Chrome.
- Quiz assistant that extracts questions/options from the SLZ DOM, calls a pluggable OpenAI-compatible LLM, and shows suggestions in an in-page overlay.
