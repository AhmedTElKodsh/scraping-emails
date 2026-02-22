#!/bin/bash
# Railway startup script - handles PORT environment variable

# Use Railway's PORT or default to 8501
PORT=${PORT:-8501}

# Override STREAMLIT_SERVER_PORT with the resolved numeric value
# This prevents issues where Railway sets it to the literal string "$PORT"
export STREAMLIT_SERVER_PORT="$PORT"

echo "Starting Streamlit on port $PORT"

# Start Streamlit with the resolved port
exec streamlit run app.py \
    --server.port="$PORT" \
    --server.headless=true \
    --server.address=0.0.0.0 \
    --browser.gatherUsageStats=false
