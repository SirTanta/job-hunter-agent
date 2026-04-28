"""
run_email_sync.py — Standalone email-to-Notion sync.

Scans jedwar82@gmail.com for ATS emails and updates the Job Hunt Dashboard
in Notion with the latest status for each application.

Schedule this to run a few times a day, or run manually after checking email.

Usage:
    python run_email_sync.py              # scan last 7 days
    python run_email_sync.py 14           # scan last 14 days
    python run_email_sync.py --since 2026-04-20   # scan since a specific date
"""

import sys
from dotenv import load_dotenv

load_dotenv()

from tools.email_processor import EmailProcessor


def main():
    days = 7

    for arg in sys.argv[1:]:
        if arg.isdigit():
            days = int(arg)

    print(f"[email_sync] Scanning last {days} days for ATS emails...")
    processor = EmailProcessor()
    stats = processor.process_inbox(lookback_days=days)

    print(f"\n[email_sync] Results:")
    print(f"  Emails processed : {stats.get('processed', 0)}")
    print(f"  Notion updated   : {stats.get('updated', 0)}")
    print(f"  Skipped          : {stats.get('skipped', 0)}")
    if stats.get("error"):
        print(f"  Error            : {stats['error']}")


if __name__ == "__main__":
    main()
