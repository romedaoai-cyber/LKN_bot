#!/bin/bash
# DaoAI LinkedIn Auto-Publisher — runs on schedule via cron
# Publishes only APPROVED posts whose scheduled datetime <= now

# Always run from the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 linkedin_publisher.py publish-all-pending >> "$SCRIPT_DIR/auto_publish.log" 2>&1
