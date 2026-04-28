"""
tools/email_processor.py — ATS email classification and Notion sync.

Monitors jedwar82@gmail.com for emails from ATS systems AFTER applications
are submitted. Classifies each email (confirmation, interview, rejection, etc.)
with Claude Haiku and updates the corresponding Notion row.

This is different from email_monitor.py which captures real-time OTPs during
the apply flow. This module runs on a schedule (cron or manually) to process
the inbox and keep Notion current.

Usage:
    processor = EmailProcessor()
    processor.process_inbox(lookback_days=7)  # process last 7 days of ATS emails

Or run standalone:
    python tools/email_processor.py
"""

import email
import imaplib
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

from tools.notion_tracker import NotionTracker

# ATS sender domains — only process emails from these
ATS_SENDER_DOMAINS = [
    "workday.com", "myworkdayjobs.com",
    "greenhouse.io", "lever.co", "ashbyhq.com",
    "smartrecruiters.com", "bamboohr.com", "icims.com",
    "taleo.net", "jobvite.com", "breezy.hr", "recruitee.com",
    "workable.com", "jazzhr.com",
    "linkedin.com", "indeed.com",
    # Generic ATS notification patterns
    "noreply", "no-reply", "donotreply", "notifications",
    "careers", "recruiting", "talent", "hr",
]

EMAIL_CATEGORIES = [
    "confirmation",   # "Thank you for applying" — application received
    "interview",      # "We'd like to schedule" / "move forward"
    "rejection",      # "We've decided to move forward with other candidates"
    "assessment",     # Technical test / coding challenge / homework
    "follow_up",      # Generic follow-up, need more info
    "offer",          # Job offer
    "other",          # Unclassifiable ATS email
]

HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Status to write to Notion per email category
CATEGORY_TO_STATUS = {
    "confirmation":  "applied",
    "interview":     "interview",
    "rejection":     "rejected",
    "assessment":    "screening",
    "follow_up":     "screening",
    "offer":         "offer",
    "other":         None,   # don't update status for unclassified
}


class EmailProcessor:

    def __init__(self):
        self.email_addr  = os.environ.get("JOB_HUNT_EMAIL", "jedwar82@gmail.com")
        self.password    = os.environ.get("JOB_HUNT_IMAP_PASSWORD", "")
        self.imap_server = os.environ.get("JOB_HUNT_IMAP_SERVER", "imap.gmail.com")
        self.notion      = NotionTracker()

        claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

        self._conn: Optional[imaplib.IMAP4_SSL] = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_inbox(self, lookback_days: int = 7) -> dict:
        """
        Scan the inbox for ATS emails from the last N days.
        Classify each email and update Notion.

        Returns a summary dict with counts.
        """
        if not self.password:
            print("[email_processor] No IMAP password — skipping")
            return {"processed": 0, "updated": 0}

        print(f"[email_processor] Scanning last {lookback_days} days of ATS emails...")

        try:
            self._conn = imaplib.IMAP4_SSL(self.imap_server, 993)
            self._conn.login(self.email_addr, self.password)
            self._conn.select("INBOX")

            # Search for emails from the lookback window
            since_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days))
            since_str  = since_date.strftime("%d-%b-%Y")

            _, data = self._conn.search(None, f'SINCE "{since_str}"')
            all_ids = data[0].split() if data[0] else []
            print(f"[email_processor] {len(all_ids)} emails in window")

            stats = {"processed": 0, "updated": 0, "skipped": 0}

            for msg_id in all_ids:
                try:
                    result = self._process_message(msg_id)
                    if result == "updated":
                        stats["updated"] += 1
                        stats["processed"] += 1
                    elif result == "processed":
                        stats["processed"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    print(f"[email_processor] Message {msg_id} error: {e}")

            print(f"[email_processor] Done: {stats}")
            return stats

        except Exception as e:
            print(f"[email_processor] IMAP error: {e}")
            return {"processed": 0, "updated": 0, "error": str(e)}
        finally:
            if self._conn:
                try:
                    self._conn.logout()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Per-message processing
    # ------------------------------------------------------------------

    def _process_message(self, msg_id: bytes) -> str:
        """Process one email. Returns 'updated', 'processed', or 'skipped'."""
        _, data = self._conn.fetch(msg_id, "(RFC822)")
        if not data or not data[0]:
            return "skipped"

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        sender  = msg.get("From", "")
        subject = _decode_str(msg.get("Subject", ""))
        date_str = msg.get("Date", "")

        # Only process emails from ATS senders
        if not _is_ats_email(sender, subject):
            return "skipped"

        body = _get_body(msg)
        if not body:
            return "skipped"

        print(f"[email_processor] ATS email: {subject[:60]} | from: {sender[:40]}")

        # Classify the email
        classification = self._classify_email(subject, body, sender)
        category    = classification.get("category", "other")
        summary     = classification.get("summary", "")
        company     = classification.get("company", "")
        role        = classification.get("role", "")
        job_url     = classification.get("job_url", "")

        print(f"[email_processor] Category: {category} | Company: {company} | Role: {role}")

        # Find the Notion row and update it
        status = CATEGORY_TO_STATUS.get(category)
        email_date = _parse_email_date(date_str)

        # Try to find by job URL from email, or by company+role combo
        updated = False
        if job_url:
            updated = self.notion.update_status(
                job_url=job_url, status=status or "screening",
                email_subject=subject, email_summary=summary, email_date=email_date
            )

        if not updated and company:
            # Search Notion for a row matching company + role
            page_id = self._find_by_company_role(company, role)
            if page_id and status:
                props = {}
                if status:
                    from tools.notion_tracker import STATUS_MAP
                    notion_status = STATUS_MAP.get(status, status.title())
                    props["Status"] = {"select": {"name": notion_status}}
                if email_date:
                    props["Last Email"] = {"date": {"start": email_date}}
                if summary:
                    props["Email Summary"] = {"rich_text": [{"text": {"content": f"[{subject}] {summary}"[:2000]}}]}
                if props:
                    self.notion._update_page(page_id, props)
                    updated = True

        return "updated" if updated else "processed"

    # ------------------------------------------------------------------
    # Email classification with Claude
    # ------------------------------------------------------------------

    def _classify_email(self, subject: str, body: str, sender: str) -> dict:
        """
        Use Claude Haiku to classify an ATS email and extract key information.
        Returns a dict with category, summary, company, role, job_url.
        """
        if not self.claude:
            return self._rule_based_classify(subject, body)

        prompt = f"""Classify this job application email.

FROM: {sender}
SUBJECT: {subject}
BODY (first 1500 chars):
{body[:1500]}

Return JSON with these exact keys:
{{
  "category": one of {EMAIL_CATEGORIES},
  "company": "company name or empty string",
  "role": "job title applied for or empty string",
  "job_url": "application URL if visible in email body, or empty string",
  "summary": "1-2 sentence plain English summary of what this email means for the job seeker",
  "next_action": "what Jon should do next, or empty string if no action needed"
}}

Classification guide:
- confirmation: any "thank you for applying", "application received", "we got your application"
- interview: any invitation to interview, schedule a call, move forward
- rejection: any "not moving forward", "other candidates", "position filled", "not a fit"
- assessment: coding challenge, take-home, technical screening, personality test
- follow_up: requests for more info, references, portfolio
- offer: job offer, salary discussion, start date
- other: unclassifiable

Return ONLY the JSON, no markdown."""

        try:
            msg = self.claude.messages.create(
                model=HAIKU_MODEL,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            print(f"[email_processor] Claude classification failed: {e}")
            return self._rule_based_classify(subject, body)

    def _rule_based_classify(self, subject: str, body: str) -> dict:
        """Fallback rule-based classification when Claude is unavailable."""
        text = (subject + " " + body).lower()

        if any(w in text for w in ("thank you for applying", "application received",
                                    "we received your application", "successfully submitted")):
            return {"category": "confirmation", "summary": "Application confirmed.", "company": "", "role": "", "job_url": ""}
        if any(w in text for w in ("interview", "schedule", "meet", "call", "move forward")):
            return {"category": "interview", "summary": "Interview invitation received.", "company": "", "role": "", "job_url": ""}
        if any(w in text for w in ("not moving forward", "other candidates", "not selected",
                                    "position has been filled", "not a fit", "unfortunately")):
            return {"category": "rejection", "summary": "Application rejected.", "company": "", "role": "", "job_url": ""}
        if any(w in text for w in ("assessment", "coding challenge", "take-home", "test")):
            return {"category": "assessment", "summary": "Assessment or test required.", "company": "", "role": "", "job_url": ""}
        return {"category": "other", "summary": subject[:100], "company": "", "role": "", "job_url": ""}

    # ------------------------------------------------------------------
    # Notion lookup helpers
    # ------------------------------------------------------------------

    def _find_by_company_role(self, company: str, role: str) -> Optional[str]:
        """Find a Notion application row by company name."""
        if not company or not self.notion.enabled:
            return None

        from tools.notion_tracker import APPLICATIONS_DB, NOTION_TOKEN, NOTION_VERSION
        import urllib.request

        payload = {
            "filter": {
                "and": [
                    {"property": "Company", "rich_text": {"contains": company[:50]}},
                ]
            }
        }
        result = self.notion._request(
            "POST",
            f"https://api.notion.com/v1/databases/{APPLICATIONS_DB}/query",
            payload,
        )
        if result and result.get("results"):
            return result["results"][0]["id"]
        return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _decode_str(raw: str) -> str:
    try:
        parts = decode_header(raw)
        return " ".join(
            p.decode(enc or "utf-8", errors="replace") if isinstance(p, bytes) else str(p)
            for p, enc in parts
        )
    except Exception:
        return raw or ""


def _get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return ""


def _is_ats_email(sender: str, subject: str) -> bool:
    sender_lower = sender.lower()
    subject_lower = subject.lower()
    if any(domain in sender_lower for domain in ATS_SENDER_DOMAINS):
        return True
    if any(kw in subject_lower for kw in
           ("application", "applied", "interview", "offer", "position",
            "role", "opportunity", "candidacy", "job", "hiring")):
        return True
    return False


def _parse_email_date(date_str: str) -> str:
    """Parse email Date header to ISO format."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    processor = EmailProcessor()
    processor.process_inbox(lookback_days=days)
