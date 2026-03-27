#!/bin/bash
set -e
echo "[INFO] Starting Arztsuche Outreach on port 5055..."
cd /app
exec python3 server.py
