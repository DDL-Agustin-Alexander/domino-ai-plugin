#!/bin/bash
# Domino App entry point for a Vite + React application.
# Domino runs this file when the App starts; the server must listen on 0.0.0.0:8888.

set -e

echo "=== Domino Vite React App ==="
echo "Project: $DOMINO_PROJECT_NAME"
echo "Owner: $DOMINO_PROJECT_OWNER"
echo "Started by: $DOMINO_STARTING_USERNAME"

# Run from the directory that holds this script and package.json (the repo root, or the app
# subfolder when app.sh lives there).
cd "$(dirname "$0")"

# Deterministic install from package-lock.json (requires Node in the Compute Environment and
# egress to the npm registry or a private mirror configured in .npmrc; on an air-gapped site
# commit the built dist/ on a deploy branch and skip the install and build steps).
echo "Installing dependencies..."
npm ci

# Production bundle with base: './' (relative asset URLs).
echo "Building production bundle..."
npm run build

# Serve dist/ and proxy model endpoint calls server-side so the token never reaches the browser.
# server.js reads MODEL_API_URL and MODEL_API_TOKEN from the environment (set them in the
# Domino project settings). For a purely static app, replace the line below with:
#   npx serve -s dist -l 8888 --no-clipboard      (add serve to devDependencies first)
echo "Starting server on 0.0.0.0:8888..."
node server.js
