#!/bin/bash
# Job Hunt + Client Hunt Agent — VM runner
# Logs to /var/log/kipi/job-hunt.log

export PYTHONIOENCODING=utf-8
LOG=/var/log/kipi/job-hunt.log
mkdir -p /var/log/kipi

echo "" >> $LOG
echo "=== RUN: $(date '+%Y-%m-%d %H:%M MDT') ===" >> $LOG

cd /root/job-hunter-agent

# Pull latest code
git pull origin main >> $LOG 2>&1

# Run job hunt — 20 jobs, generate resumes + sync Notion + auto-apply
venv/bin/python agent.py --max 20 --auto-apply >> $LOG 2>&1
EXIT=$?

# Sync email replies to Notion
venv/bin/python run_email_sync.py 1 >> $LOG 2>&1

# Run client hunt — find leads, enroll in Apollo sequence
venv/bin/python client_hunt_agent.py --max 15 --apollo >> $LOG 2>&1

echo "=== EXIT: $EXIT | $(date '+%H:%M') ===" >> $LOG
