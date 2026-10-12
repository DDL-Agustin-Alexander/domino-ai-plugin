#!/bin/bash
# Domino App entry point for a Dash application.
# Domino runs this file when the App starts; app.py must bind 0.0.0.0:8888.

set -e

echo "=== Domino Dash App ==="
echo "Project: $DOMINO_PROJECT_NAME"
echo "Owner: $DOMINO_PROJECT_OWNER"
echo "Started by: $DOMINO_STARTING_USERNAME"

# Project files live in DOMINO_WORKING_DIR (/mnt/code for Git-based projects).
cd "$DOMINO_WORKING_DIR"

# Install dash in the Compute Environment rather than here; pip at start slows every launch.

python app.py
