"""Main entry point for Farida Estate Scraping Pipeline.

Usage:
    python main.py              # Start scheduler (runs indefinitely)
    python main.py --once       # Run both scrapers once and exit
    python main.py --layer1     # Run Layer 1 (WordPress) only
    python main.py --layer2     # Run Layer 2 (App API) only
"""

import sys
import argparse

from src.scheduler.scheduler import ScraperScheduler
from src.scrapers.wp_scraper import run_one_shot as run_wp_scraper
from src.scrapers.app_scraper import run_one_shot as run_app_scraper


def main():
    parser = argparse.ArgumentParser(
        description="Farida Estate Scraping Pipeline"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run both scrapers once and exit (no scheduling)"
    )
    parser.add_argument(
        "--layer1",
        action="store_true",
        help="Run Layer 1 (WordPress) scraper only"
    )
    parser.add_argument(
        "--layer2",
        action="store_true",
        help="Run Layer 2 (App API) scraper only"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )
    
    args = parser.parse_args()
    
    # One-shot execution modes
    if args.once:
        print("Running one-shot execution (both layers)...")
        run_wp_scraper()
        print("\n")
        run_app_scraper()
        print("\nOne-shot execution complete.")
        return
    
    if args.layer1:
        print("Running Layer 1 (WordPress) scraper...")
        run_wp_scraper()
        return
    
    if args.layer2:
        print("Running Layer 2 (App API) scraper...")
        run_app_scraper()
        return
    
    # Default: Start scheduler
    print("Starting scheduler...")
    try:
        scheduler = ScraperScheduler(config_path=args.config)
        scheduler.run()
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
