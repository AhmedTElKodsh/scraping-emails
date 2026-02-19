FROM python:3.12-slim

# Install system dependencies for Camoufox (Firefox) + Xvfb for virtual display
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtk-3-0 \
    libasound2 \
    libx11-xcb1 \
    libdbus-glib-1-2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser dependencies (must come before camoufox fetch)
RUN playwright install-deps

# Download Camoufox browser binary (bake into image, not at runtime)
RUN python -m camoufox fetch

# Copy application code
COPY . .

EXPOSE 8501

# Health check (using Python since curl is not in slim image)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.headless=true", \
    "--server.address=0.0.0.0", \
    "--browser.gatherUsageStats=false"]
