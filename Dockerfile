FROM python:3.12-slim

# Install system dependencies for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (the only browser we need for Railway)
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create .streamlit config directory
RUN mkdir -p /app/.streamlit

# Copy startup script and fix line endings
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# Use Playwright on Railway (not Camoufox — simpler and more reliable)
ENV BROWSER_ENGINE=playwright
ENV PYTHONUNBUFFERED=1

# Railway injects PORT at runtime — don't hardcode it
EXPOSE 8501

CMD ["/app/start.sh"]
