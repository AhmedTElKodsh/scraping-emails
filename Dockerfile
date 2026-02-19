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

# Install Playwright browser dependencies and Chromium
RUN playwright install-deps && playwright install chromium

# Download Camoufox browser binary (bake into image, not at runtime)
# Use timeout to prevent hanging during build
RUN timeout 300 python -m camoufox fetch || echo "Camoufox fetch timed out, will fetch at runtime if needed"

# Copy application code
COPY . .

# Copy startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Railway provides PORT env variable
ENV PORT=8501
EXPOSE $PORT

# Run startup script that handles PORT variable
CMD ["/app/start.sh"]
