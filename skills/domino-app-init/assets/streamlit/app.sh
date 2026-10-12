#!/bin/bash
# Domino App entry point for a Streamlit application.
# Domino runs this file when the App starts; Streamlit must listen on 0.0.0.0:8888
# (its default is 8501). Mirrors Domino's published Streamlit example.

set -e

echo "=== Domino Streamlit App ==="
echo "Project: $DOMINO_PROJECT_NAME"
echo "Owner: $DOMINO_PROJECT_OWNER"
echo "Started by: $DOMINO_STARTING_USERNAME"

# Project files live in DOMINO_WORKING_DIR (/mnt/code for Git-based projects).
cd "$DOMINO_WORKING_DIR"

# Install streamlit in the Compute Environment rather than here; pip at start slows every launch.

mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << 'EOF'
[server]
port = 8888
address = "0.0.0.0"
headless = true
# Required behind Domino's proxy so the websocket and uploads work.
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
EOF

streamlit run app.py
