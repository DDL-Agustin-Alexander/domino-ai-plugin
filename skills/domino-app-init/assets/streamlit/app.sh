#!/bin/bash
# Domino App entry point for a Streamlit application.
# Domino runs this file when the App starts; Streamlit must listen on 0.0.0.0:8888
# (its default is 8501). Mirrors Domino's published Streamlit example.

set -e

echo "=== Domino Streamlit App ==="
echo "Project: $DOMINO_PROJECT_NAME"
echo "Owner: $DOMINO_PROJECT_OWNER"
echo "Started by: $DOMINO_STARTING_USERNAME"

# Run from the directory that holds this script and app.py (the repo root, or the app
# subfolder when app.sh lives there).
cd "$(dirname "$0")"

# Install streamlit in the Compute Environment rather than here; pip at start slows every launch.

# Domino's published Streamlit example writes this config. enableCORS and
# enableXsrfProtection are set to false there; keep them unless your deployment is known to
# work with the defaults (XSRF protection off weakens file-upload protection).
mkdir -p ~/.streamlit
cat > ~/.streamlit/config.toml << 'EOF'
[server]
port = 8888
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
EOF

# Port and address are also passed explicitly so the binding does not depend on the config file.
streamlit run app.py --server.port 8888 --server.address 0.0.0.0
