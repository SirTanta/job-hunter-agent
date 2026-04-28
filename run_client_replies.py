"""
run_client_replies.py — Process client outreach replies from jedwards@tanta-holdings.com.

Scans last 7 days of inbox for replies to cold outreach emails.
Classifies with Claude Haiku using client reply categories.
Updates Notion Client Hunt Dashboard.

Usage:
    python run_client_replies.py
    python run_client_replies.py --days 14
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from tools.email_processor import EmailProcessor, HAIKU_MODEL
from client_hunt.notion_leads import NotionLeadsTracker

# Reply categories for client outreach (different from ATS email categories)
REPLY_CATEGORIES = [
    "interested",    # Positive response, wants to talk
    "objection",     # Has concerns but still engaged
    "not_now",       # "Reach out in Q3", "not in budget right now"
    "wrong_person",  # "You should talk to..." forwarded / redirected
    "ooo",           # Out of office auto-reply
    "unsubscribed",  # "Please remove me from your list"
]

CATEGORY_TO_STATUS_MAP = {
    "interested":    "Replied",
    "objection":     "Replied",
    "not_now":       "Nurture",
    "wrong_person":  "Replied",
    "ooo":           None,     # don't change status for OOO
    "unsubscribed":  "Unsubscribed",
}


class ClientReplyProcessor(EmailProcessor):
    """
    Subclass of EmailProcessor that classifies client outreach replies
    using client-specific categories and updates Notion Client Hunt Dashboard.
    """

    def __init__(self):
        super().__init__()
        # Override the email address to use the Tanta work address
        self.email_addr = os.environ.get("TANTA_EMAIL", "jedwards@tanta-holdings.com")
        self.notion_leads = NotionLeadsTracker()

    def _classify_email(self, subject: str, body: str, sender: str) -> dict:
        """
        Override parent classify to use client reply categories.
        """
        if not self.claude:
            return self._rule_based_reply_classify(subject, body)

        prompt = f"""Classify this reply to a cold outreach email about AI enablement / L&D consulting services.

FROM: {sender}
SUBJECT: {subject}
BODY (first 1500 chars):
{body[:1500]}

Return JSON with these exact keys:
{{
  "category": one of {REPLY_CATEGORIES},
  "company": "company name or empty string",
  "summary": "1-2 sentence plain English summary",
  "next_action": "what Jon should do next, or empty string"
}}

Classification guide:
- interested: positive response, wants to learn more, asks for a call
- objection: has concerns (budget, timing, fit) but still engaged
- not_now: explicitly deferring ("reach out later", "not in budget this quarter")
- wrong_person: forwarded to someone else or says "you should contact X"
- ooo: out of office auto-reply
- unsubscribed: asks to be removed, "not interested", "stop emailing"

Return ONLY the JSON, no markdown."""

        import re
        import json
        try:
            msg = self.claude.messages.create(
                model=HAIKU_MODEL,
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except Exception as e:
            print(f"[client_replies] Claude classification failed: {e}")
            return self._rule_based_reply_classify(subject, body)

    def _rule_based_reply_classify(self, subject: str, body: str) -> dict:
        """Fallback rule-based classification."""
        text = (subject + " " + body).lower()

        if any(w in text for w in ("remove", "unsubscribe", "stop", "not interested", "do not contact")):
            return {"category": "unsubscribed", "summary": "Requested removal.", "company": ""}
        if any(w in text for w in ("out of office", "away from", "ooo", "vacation", "annual leave")):
            return {"category": "ooo", "summary": "Out of office reply.", "company": ""}
        if any(w in text for w in ("not now", "next quarter", "next year", "budget", "later this year")):
            return {"category": "not_now", "summary": "Not now but open in future.", "company": ""}
        if any(w in text for w in ("forward", "you should", "contact", "better person", "right person")):
            return {"category": "wrong_person", "summary": "Redirected to someone else.", "company": ""}
        if any(w in text for w in ("interest", "tell me more", "love to", "schedule", "call", "chat", "meeting")):
            return {"category": "interested", "summary": "Positive reply — wants to connect.", "company": ""}
        if any(w in text for w in ("concern", "question", "not sure", "but", "however", "cost")):
            return {"category": "objection", "summary": "Has questions/concerns.", "company": ""}
        return {"category": "interested", "summary": subject[:100], "company": ""}

    def _process_message(self, msg_id: bytes) -> str:
        """
        Override parent to use client-specific Notion update logic.
        """
        import email
        from tools.email_processor import _decode_str, _get_body, _parse_email_date

        _, data = self._conn.fetch(msg_id, "(RFC822)")
        if not data or not data[0]:
            return "skipped"

        raw = data[0][1]
        msg = email.message_from_bytes(raw)

        sender   = msg.get("From", "")
        subject  = _decode_str(msg.get("Subject", ""))
        date_str = msg.get("Date", "")

        # Only process emails that look like replies to outreach (not our own sent mail)
        # Skip noreply, automated, system emails
        sender_lower = sender.lower()
        if any(skip in sender_lower for skip in ("noreply", "no-reply", "donotreply",
                                                   "automated", "mailer-daemon", "postmaster")):
            return "skipped"

        body = _get_body(msg)
        if not body:
            return "skipped"

        print(f"[client_replies] Reply: {subject[:60]} | from: {sender[:40]}")

        classification = self._classify_email(subject, body, sender)
        category = classification.get("category", "interested")
        summary  = classification.get("summary", "")
        company  = classification.get("company", "")

        print(f"[client_replies] Category: {category} | Company: {company}")

        # Extract domain from sender to find the Notion lead
        import re
        domain_match = re.search(r"@([\w.-]+)", sender)
        domain = domain_match.group(1) if domain_match else ""

        # Strip subdomains to get registrable domain
        if domain:
            parts = domain.split(".")
            if len(parts) >= 2:
                domain = ".".join(parts[-2:])

        # Update Notion Client Hunt Dashboard
        updated = False
        if domain and self.notion_leads.enabled:
            updated = self.notion_leads.update_after_reply(domain, category, summary)

        if not updated and company and self.notion_leads.enabled:
            # Try by company name as fallback — search Notes field
            print(f"[client_replies] Domain lookup missed — trying company name: {company}")

        return "updated" if updated else "processed"


def main():
    parser = argparse.ArgumentParser(description="Process client outreach replies")
    parser.add_argument("--days", type=int, default=7, help="Lookback days (default 7)")
    args = parser.parse_args()

    processor = ClientReplyProcessor()
    result = processor.process_inbox(lookback_days=args.days)
    print(f"\n[client_replies] Summary: {result}")


if __name__ == "__main__":
    main()
