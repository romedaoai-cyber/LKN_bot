#!/bin/bash
# DaoAI LinkedIn Auto-Publisher — runs daily at 9:00 AM PST
# Publishes only APPROVED posts whose date <= today

cd /Users/pin/Kiki
python3 linkedin_publisher.py publish-all-pending >> /Users/pin/Kiki/linkedin_posts/auto_publish.log 2>&1
