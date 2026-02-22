FROM python:3.12-slim

# Install system dependencies needed by Playwright Chromium + Xvfb virtual display
# These complement what `playwright install-deps chromium` installs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtk-3-0 \
    libasound2 \
    libx11-xcb1 \
    libdbus-glib-1-2 \
    xvfb \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright system dependencies for Chromium, then install Chromium browser
RUN playwright install-deps chromium && playwright install chromium

# Download Camoufox browser binary (bake into image, not at runtime)
# Use timeout to prevent hanging during build; failure is non-fatal since we default to Playwright
RUN timeout 300 python -m camoufox fetch || echo "Camoufox fetch timed out/failed — defaulting to Playwright at runtime"

# Copy application code
COPY . .

# Ensure startup script is executable (may not be if built on Windows)
RUN chmod +x /app/start.sh

# Railway provides PORT env variable; default to 8501 locally
ENV PORT=8501
# Default to Playwright (reliable on all platforms); set BROWSER_ENGINE=camoufox for stealth mode
ENV BROWSER_ENGINE=playwright

EXPOSE $PORT

CMD ["/app/start.sh"]
