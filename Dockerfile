FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System dependencies for Chrome, Selenium, easyocr / OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcairo2 \
        libxkbcommon0 \
        libnss3 \
        libxss1 \
        libxtst6 \
        libxrandr2 \
        libxdamage1 \
        libxcomposite1 \
        libxshmfence1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libx11-6 \
        libgl1 \
        libgomp1 \
        # Extra Chrome runtime deps
        libx11-xcb1 \
        libxcb1 \
        libgtk-3-0 \
        libdbus-1-3 \
        libgbm1 \
        libpangocairo-1.0-0 \
        libpango-1.0-0 \
        libfontconfig1 \
        libxfixes3 \
        libxi6 \
        libxcursor1 \
        libcups2 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome (used by Selenium + webdriver-manager)
RUN set -eux; \
    wget -qO- https://dl.google.com/linux/linux_signing_key.pub | \
        gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg; \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends google-chrome-stable; \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m appuser

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src
COPY scripts ./scripts
COPY config.yaml ./config.yaml
COPY PLAN.md README.md ./

USER appuser

# Default entrypoint: console workflow
# Run main script directly so that `/app/src` is on sys.path and
# imports like `from config.settings import load_config` work.
# You can override this at runtime to run the Tk GUI: `python scripts/run_gui.py`
CMD ["python", "src/main.py"]
