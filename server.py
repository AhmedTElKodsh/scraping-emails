"""Flask server for Railway health checks + background scheduler."""

import os
import threading
from flask import Flask, jsonify
from datetime import datetime
from src.scheduler.scheduler import ScraperScheduler
from src.storage.database import Database

app = Flask(__name__)

# Global scheduler instance
scheduler = None
scheduler_thread = None


def start_scheduler():
    """Start the scraper scheduler in a background thread."""
    global scheduler
    try:
        scheduler = ScraperScheduler(config_path="config.yaml")
        scheduler.run()
    except Exception as e:
        print(f"Scheduler error: {e}")


@app.route('/')
def home():
    """Root endpoint - shows service status."""
    return jsonify({
        "service": "Farida Estate Scraping Pipeline",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/health')
def health():
    """Health check endpoint for Railway."""
    try:
        # Check database connectivity
        db = Database()
        db.close()
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "scheduler": "running" if scheduler else "not_started",
            "timestamp": datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


@app.route('/status')
def status():
    """Get scraping status from database."""
    try:
        db = Database()
        cursor = db.conn.cursor()
        
        # Get last 5 scrape runs
        cursor.execute("""
            SELECT layer, status, items_scraped, started_at, completed_at, error_message
            FROM scrape_runs
            ORDER BY started_at DESC
            LIMIT 5
        """)
        
        runs = []
        for row in cursor.fetchall():
            runs.append({
                "layer": row[0],
                "status": row[1],
                "items_scraped": row[2],
                "started_at": row[3],
                "completed_at": row[4],
                "error": row[5]
            })
        
        db.close()
        
        return jsonify({
            "recent_runs": runs,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500


if __name__ == '__main__':
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start Flask server
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
