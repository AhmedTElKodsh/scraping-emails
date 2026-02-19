"""Flask server for Railway health checks + background scheduler."""

import os
import threading
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

# Global scheduler instance
scheduler = None
scheduler_thread = None
scheduler_error = None


def check_environment():
    """Check if required environment variables are present."""
    required_vars = ['FARIDA_EMAIL', 'FARIDA_PASSWORD']
    missing = [var for var in required_vars if not os.environ.get(var)]
    return len(missing) == 0, missing


def start_scheduler():
    """Start the scraper scheduler in a background thread."""
    global scheduler, scheduler_error
    
    # Check if required files exist
    if not os.path.exists("config.yaml"):
        scheduler_error = "config.yaml not found"
        print(f"WARNING: {scheduler_error} - scheduler will not start")
        return
    
    # Check environment variables
    env_ok, missing_vars = check_environment()
    if not env_ok:
        scheduler_error = f"Missing environment variables: {', '.join(missing_vars)}"
        print(f"WARNING: {scheduler_error} - scheduler will not start")
        return
    
    # Try to import and start scheduler
    try:
        from src.scheduler.scheduler import ScraperScheduler
        scheduler = ScraperScheduler(config_path="config.yaml")
        print("Scheduler initialized successfully")
        scheduler.run()
    except Exception as e:
        scheduler_error = str(e)
        print(f"Scheduler initialization failed: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - let Flask server continue running


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
    # Always return healthy if Flask is running
    # Railway just needs to know the service is up
    scheduler_status = "running" if scheduler else "not_started"
    if scheduler_error:
        scheduler_status = f"error: {scheduler_error}"
    
    return jsonify({
        "status": "healthy",
        "service": "running",
        "scheduler": scheduler_status,
        "timestamp": datetime.utcnow().isoformat()
    }), 200


@app.route('/status')
def status():
    """Get scraping status from database."""
    try:
        from src.storage.database import Database
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
            "scheduler_running": scheduler is not None,
            "scheduler_error": scheduler_error,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            "error": str(e),
            "scheduler_running": scheduler is not None,
            "scheduler_error": scheduler_error,
            "timestamp": datetime.utcnow().isoformat()
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("Starting Farida Estate Scraping Service")
    print("=" * 60)
    
    # Check environment
    env_ok, missing_vars = check_environment()
    if not env_ok:
        print(f"WARNING: Missing environment variables: {', '.join(missing_vars)}")
        print("Scheduler will not start. Configure these in Railway dashboard.")
    
    # Start scheduler in background thread (will fail gracefully if env not ready)
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Start Flask server (always starts regardless of scheduler status)
    port = int(os.environ.get('PORT', 8080))
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port)
