"""
tools/email_monitor.py — Real-time email monitor for OTP/verification codes.

Used during the apply flow when an ATS sends a verification code mid-session.
Connects via IMAP to jedwar82@gmail.com and polls for new emails from ATS senders.

Usage:
    monitor = EmailMonitor()
    monitor.start()                          # begin watching in background
    code = monitor.wait_for_code(timeout=90) # block until code arrives
    monitor.stop()

Or as a context manager:
    with EmailMonitor() as monitor:
        # trigger whatever causes the email to be sent
        code = monitor.wait_for_code(timeout=90)
"""

import email
import imaplib
import os
import re
import threading
import time
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# OTP/code patterns — ordered by specificity
CODE_PATTERNS = [
    r"\b(\d{6})\b",           # 6-digit OTP (most common)
    r"\b(\d{4})\b",           # 4-digit PIN
    r"\b([A-Z0-9]{6,10})\b",  # alphanumeric codes (e.g. Workday magic links)
    r"code[:\s]+([A-Z0-9]{4,10})",  # "Your code: ABC123"
    r"pin[:\s]+(\d{4,8})",          # "Your PIN: 1234"
]

# Domains/keywords that indicate a verification email vs spam
VERIFICATION_KEYWORDS = [
    "verification", "verify", "code", "pin", "otp", "one-time",
    "confirm", "authentication", "access code", "sign in", "login",
    "security code", "activate",
]


class EmailMonitor:
    """
    Polls Gmail IMAP for verification codes sent by ATS systems.

    Why polling instead of IMAP IDLE:
      IMAP IDLE is a persistent connection that pushes new-mail events.
      It's faster but harder to manage timeouts and reconnects in a short-lived
      subprocess context. Polling at 3s is fast enough for OTP use (codes
      expire in 10+ minutes) and much simpler to implement reliably.
    """

    def __init__(self,
                 email_addr: str = None,
                 password: str = None,
                 imap_server: str = None,
                 poll_interval: float = 3.0):
        self.email_addr  = email_addr  or os.environ.get("JOB_HUNT_EMAIL", "jedwar82@gmail.com")
        self.password    = password    or os.environ.get("JOB_HUNT_IMAP_PASSWORD", "")
        self.imap_server = imap_server or os.environ.get("JOB_HUNT_IMAP_SERVER", "imap.gmail.com")
        self.poll_interval = poll_interval

        self._conn: Optional[imaplib.IMAP4_SSL] = None
        self._stop_event = threading.Event()
        self._found_code: Optional[str] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._start_uid: Optional[str] = None   # highest UID when monitoring started
        self._sender_filter: Optional[str] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------

    def start(self, sender_filter: str = None) -> bool:
        """
        Connect to IMAP and record the current highest email UID.
        Anything arriving AFTER this point is a candidate for code extraction.

        Args:
            sender_filter: optional email/domain to restrict sender matching
                           e.g. "workday.com" or "noreply@lever.co"

        Returns True on successful connection.
        """
        self._sender_filter = sender_filter
        self._stop_event.clear()
        self._found_code = None

        if not self.password:
            print("[email_monitor] No IMAP password configured — OTP capture disabled")
            return False

        try:
            self._conn = imaplib.IMAP4_SSL(self.imap_server, 993)
            self._conn.login(self.email_addr, self.password)
            self._conn.select("INBOX")

            # Record the current max UID so we only look at NEW emails
            _, data = self._conn.uid("search", None, "ALL")
            uids = data[0].split() if data[0] else []
            self._start_uid = uids[-1].decode() if uids else "0"

            print(f"[email_monitor] Connected. Watching from UID {self._start_uid}")

            # Start background poll thread
            self._watch_thread = threading.Thread(
                target=self._poll_loop, daemon=True
            )
            self._watch_thread.start()
            return True

        except Exception as e:
            print(f"[email_monitor] Connection failed: {e}")
            self._conn = None
            return False

    def stop(self):
        """Signal the poll thread to stop and close the IMAP connection."""
        self._stop_event.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=5)
        if self._conn:
            try:
                self._conn.logout()
            except Exception:
                pass
            self._conn = None
        print("[email_monitor] Stopped")

    # ------------------------------------------------------------------
    # Wait for code
    # ------------------------------------------------------------------

    def wait_for_code(self, timeout: float = 90) -> Optional[str]:
        """
        Block until a verification code is found in a new email or timeout.

        Args:
            timeout: seconds to wait before giving up

        Returns the code string, or None on timeout.
        """
        if not self._conn:
            print("[email_monitor] Not connected — returning None")
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._found_code:
                code = self._found_code
                print(f"[email_monitor] Code captured: {code}")
                return code
            time.sleep(0.5)

        print(f"[email_monitor] Timeout after {timeout}s — no code found")
        return None

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Check for new emails every poll_interval seconds."""
        while not self._stop_event.is_set():
            try:
                self._check_for_new_email()
            except imaplib.IMAP4.abort:
                # Connection dropped — try to reconnect once
                try:
                    self._conn = imaplib.IMAP4_SSL(self.imap_server, 993)
                    self._conn.login(self.email_addr, self.password)
                    self._conn.select("INBOX")
                except Exception:
                    break
            except Exception as e:
                print(f"[email_monitor] Poll error (non-fatal): {e}")

            self._stop_event.wait(self.poll_interval)

    def _check_for_new_email(self):
        """Search for emails with UIDs higher than _start_uid."""
        if not self._start_uid:
            return

        _, data = self._conn.uid("search", None, f"UID {int(self._start_uid)+1}:*")
        new_uids = data[0].split() if data[0] else []

        for uid in new_uids:
            uid_str = uid.decode()
            if int(uid_str) <= int(self._start_uid):
                continue

            _, msg_data = self._conn.uid("fetch", uid_str, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            sender = msg.get("From", "")
            subject = _decode_header_str(msg.get("Subject", ""))

            # Filter by sender if specified
            if self._sender_filter and self._sender_filter.lower() not in sender.lower():
                continue

            # Check subject for verification keywords
            subject_lower = subject.lower()
            is_verification = any(kw in subject_lower for kw in VERIFICATION_KEYWORDS)
            if not is_verification:
                # Also check if sender looks like an ATS
                is_verification = any(
                    domain in sender.lower()
                    for domain in ["workday", "greenhouse", "lever", "ashby",
                                   "smartrecruiters", "bamboohr", "icims",
                                   "jobvite", "taleo", "recruitee", "indeed",
                                   "linkedin", "noreply", "no-reply"]
                )

            if not is_verification:
                continue

            # Extract body text
            body = _get_email_body(msg)
            code = _extract_code(body + " " + subject)

            if code:
                self._found_code = code
                print(f"[email_monitor] Found code '{code}' in email: {subject[:60]}")
                return


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _decode_header_str(raw: str) -> str:
    """Decode RFC 2047 encoded email header to plain string."""
    try:
        parts = decode_header(raw)
        decoded = []
        for part, enc in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                decoded.append(str(part))
        return " ".join(decoded)
    except Exception:
        return raw or ""


def _get_email_body(msg) -> str:
    """Extract plain-text body from an email.Message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    body += part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return body[:3000]


def _extract_code(text: str) -> Optional[str]:
    """
    Extract a verification code from email body text.
    Returns the most specific match (6-digit preferred over 4-digit).
    """
    for pattern in CODE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            code = match.group(1)
            # Filter out obviously wrong matches (years, zip codes, phone fragments)
            if re.match(r"^(19|20)\d{2}$", code):   # year
                continue
            if len(code) == 5:                        # US zip code
                continue
            return code
    return None
