#!/usr/bin/env bash
# Build React frontend and copy to Python package static directory
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_DIR/frontend"
STATIC_DIR="$PROJECT_DIR/src/docflow/web/static"

echo "Building frontend..."
cd "$FRONTEND_DIR"
npm install --silent
npm run build

echo "Copying to $STATIC_DIR..."
rm -rf "$STATIC_DIR"
cp -r "$FRONTEND_DIR/dist" "$STATIC_DIR"

echo "Frontend build complete."
ls -la "$STATIC_DIR"
