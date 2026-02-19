# Scheduler Guide

## Overview

The Farida Estate Scraping Pipeline includes a flexible scheduler that runs both Layer 1 (WordPress) and Layer 2 (App API) scrapers on configurable intervals.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Settings

Edit `config.yaml` to set your scraping intervals and preferences:

```yaml
intervals:
  layer1_wordpress: 24 # Run WordPress scraper daily
  layer2_app: 6 # Run app scraper every 6 hours
```

### 3. Run the Scheduler

```bash
# Start scheduler (runs indefinitely)
python main.py

# Run both scrapers once and exit
python main.py --once

# Run only Layer 1 (WordPress)
python main.py --layer1

# Run only Layer 2 (App API)
python main.py --layer2
```

---

## Configuration Options

### Intervals

Control how often each layer runs:

```yaml
intervals:
  layer1_wordpress: 24 # Hours between WordPress scrapes
  layer2_app: 6 # Hours between App API scrapes
```

### Request Settings

```yaml
request:
  delay_seconds: 3 # Delay between API requests
  timeout_seconds: 30 # Request timeout
  max_retries: 3 # Max retry attempts
  retry_backoff_base: 2 # Exponential backoff base
```

### Endpoint Toggles

Enable/disable specific scrapers or endpoints:

```yaml
endpoints:
  layer1_enabled: true # Enable/disable WordPress scraper
  layer2_enabled: true # Enable/disable App API scraper

  app_endpoints:
    profile_status: true # Toggle individual endpoints
    wallet_balance: true
    # ... etc
```

### Error Handling

```yaml
error_handling:
  circuit_breaker_threshold: 5 # Stop after N consecutive failures
  continue_on_error: true # Continue with other endpoints on failure
```

### Logging

```yaml
logging:
  level: INFO # DEBUG, INFO, WARNING, ERROR
  file: logs/scraper.log
  max_file_size_mb: 10
  backup_count: 5
```

---

## Usage Examples

### Run Scheduler Continuously

```bash
python main.py
```

This will:

1. Run both scrapers immediately on startup
2. Schedule Layer 1 to run every 24 hours
3. Schedule Layer 2 to run every 6 hours
4. Continue running until stopped with Ctrl+C

### One-Shot Execution

```bash
# Run both layers once
python main.py --once

# Run only WordPress scraper
python main.py --layer1

# Run only App API scraper
python main.py --layer2
```

### Custom Config File

```bash
python main.py --config /path/to/custom-config.yaml
```

---

## Monitoring

### Log Files

All scraping activity is logged to `logs/scraper.log`:

```
2026-02-15 19:53:00 - Starting Layer 2 (App API) scrape
2026-02-15 19:53:10 - Layer 2 scrape completed successfully
```

### Database

Check scrape history in SQLite:

```python
import sqlite3

conn = sqlite3.connect('data/farida.db')

# View recent scrape runs
runs = conn.execute('''
    SELECT * FROM scrape_runs
    ORDER BY started_at DESC
    LIMIT 10
''').fetchall()

for run in runs:
    print(f"{run[1]} - {run[2]}: {run[4]} items, {run[5]} errors")
```

---

## Graceful Shutdown

The scheduler handles shutdown signals gracefully:

- Press `Ctrl+C` to stop
- Sends SIGINT/SIGTERM for clean shutdown
- Completes current scrape before exiting

---

## Production Deployment

### Running as a Service (Linux)

Create `/etc/systemd/system/farida-scraper.service`:

```ini
[Unit]
Description=Farida Estate Scraping Pipeline
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/AI-Scraping
ExecStart=/usr/bin/python3 /path/to/AI-Scraping/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable farida-scraper
sudo systemctl start farida-scraper
sudo systemctl status farida-scraper
```

### Running with Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

CMD ["python", "main.py"]
```

Build and run:

```bash
docker build -t farida-scraper .
docker run -d --name farida-scraper \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  farida-scraper
```

### Running with Screen (Simple)

```bash
screen -S farida-scraper
python main.py
# Press Ctrl+A then D to detach

# Reattach later
screen -r farida-scraper
```

---

## Troubleshooting

### Scheduler Not Running

Check logs:

```bash
tail -f logs/scraper.log
```

### Authentication Errors

Verify token in `.env`:

```bash
grep FARIDA_TOKEN .env
```

Token expires on 2028-09-15. If expired, extract new token from browser.

### Database Locked

If using WAL mode, ensure no other processes are accessing the database:

```bash
# Check for locks
lsof data/farida.db
```

### High Memory Usage

Reduce scraping frequency or implement pagination limits in `config.yaml`.

---

## Next Steps

- **Phase 4**: Add health monitoring and alerts
- **Phase 5**: Implement data export utilities
- **Future**: Add webhook notifications for failures
