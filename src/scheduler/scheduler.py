"""Recurring scheduler for Farida Estate scraping pipeline.

Runs both Layer 1 (WordPress) and Layer 2 (App API) scrapers on configurable intervals.
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import yaml
import schedule

from src.scrapers.wp_scraper import run_one_shot as run_wp_scraper
from src.scrapers.app_scraper import run_one_shot as run_app_scraper


class ScraperScheduler:
    """Manages scheduled execution of both scraping layers."""

    def __init__(self, config_path="config.yaml"):
        self.config = self._load_config(config_path)
        self.running = True
        self._setup_logging()
        self._setup_signal_handlers()

    def _load_config(self, config_path):
        """Load configuration from YAML file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        """Configure logging based on config settings."""
        log_config = self.config.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO"))
        log_file = log_config.get("file", "logs/scraper.log")
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _setup_signal_handlers(self):
        """Setup graceful shutdown on SIGINT/SIGTERM."""
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

    def _shutdown_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def run_layer1(self):
        """Execute Layer 1 (WordPress) scraper."""
        if not self.config.get("endpoints", {}).get("layer1_enabled", True):
            self.logger.info("Layer 1 scraping disabled in config, skipping.")
            return

        self.logger.info("=" * 60)
        self.logger.info("Starting Layer 1 (WordPress) scrape")
        self.logger.info("=" * 60)
        
        try:
            run_wp_scraper()
            self.logger.info("Layer 1 scrape completed successfully")
        except Exception as e:
            self.logger.error(f"Layer 1 scrape failed: {e}", exc_info=True)
            if not self.config.get("error_handling", {}).get("continue_on_error", True):
                raise

    def run_layer2(self):
        """Execute Layer 2 (App API) scraper."""
        if not self.config.get("endpoints", {}).get("layer2_enabled", True):
            self.logger.info("Layer 2 scraping disabled in config, skipping.")
            return

        self.logger.info("=" * 60)
        self.logger.info("Starting Layer 2 (App API) scrape")
        self.logger.info("=" * 60)
        
        try:
            run_app_scraper()
            self.logger.info("Layer 2 scrape completed successfully")
        except Exception as e:
            self.logger.error(f"Layer 2 scrape failed: {e}", exc_info=True)
            if not self.config.get("error_handling", {}).get("continue_on_error", True):
                raise

    def schedule_jobs(self):
        """Schedule both scraping jobs based on config intervals."""
        intervals = self.config.get("intervals", {})
        
        layer1_interval = intervals.get("layer1_wordpress", 24)
        layer2_interval = intervals.get("layer2_app", 6)
        
        # Schedule Layer 1 (WordPress)
        schedule.every(layer1_interval).hours.do(self.run_layer1)
        self.logger.info(f"Scheduled Layer 1 to run every {layer1_interval} hours")
        
        # Schedule Layer 2 (App API)
        schedule.every(layer2_interval).hours.do(self.run_layer2)
        self.logger.info(f"Scheduled Layer 2 to run every {layer2_interval} hours")
        
        # Run both immediately on startup
        self.logger.info("Running initial scrapes on startup...")
        self.run_layer1()
        time.sleep(5)  # Brief delay between layers
        self.run_layer2()

    def run(self):
        """Start the scheduler and run indefinitely."""
        self.logger.info("=" * 60)
        self.logger.info("Farida Estate Scraping Pipeline - Scheduler Started")
        self.logger.info("=" * 60)
        
        self.schedule_jobs()
        
        self.logger.info("Scheduler running. Press Ctrl+C to stop.")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                if not self.config.get("error_handling", {}).get("continue_on_error", True):
                    break
        
        self.logger.info("Scheduler stopped.")


def main():
    """Entry point for scheduler."""
    try:
        scheduler = ScraperScheduler()
        scheduler.run()
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
