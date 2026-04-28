"""
client_hunt/apollo_sender.py — Apollo.io outreach integration.

Replaces the Gmail draft approach with Apollo-powered sequence enrollment.
All contacts are enrolled in "Tanta Holdings - L&D AI Consulting" sequence.

API base: https://api.apollo.io/api/v1
Auth:     x-api-key header (APOLLO_API_KEY env var)

Apollo terminology note: sequences are called "emailer_campaigns" in the API.
The add-to-sequence endpoint is POST /emailer_campaigns/{id}/add_contact_ids.
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

APOLLO_BASE = "https://api.apollo.io/api/v1"

# Module-level sequence ID cache — avoid repeated API calls
_sequence_id_cache: Optional[str] = None


class ApolloSender:
    """
    Manages Apollo.io contact creation and sequence enrollment for
    the client hunt pipeline.
    """

    def __init__(self):
        self.api_key = os.environ.get("APOLLO_API_KEY", "")
        if not self.api_key:
            print("[apollo] Warning: APOLLO_API_KEY not set — Apollo disabled")

        # Import here to avoid circular imports
        from client_hunt.config import APOLLO_SEQUENCE_NAME, APOLLO_EMAIL_ACCOUNT_ID
        self.sequence_name    = APOLLO_SEQUENCE_NAME
        self.email_account_id = APOLLO_EMAIL_ACCOUNT_ID

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_or_create_contact(
        self,
        company_name: str,
        domain: str,
        contact_name: str = "",
        contact_title: str = "",
        email_guess: str = "",
    ) -> Optional[dict]:
        """
        Search Apollo for an existing contact at the given domain.
        If not found, create one.

        Returns dict with {id, email, name} or None on error.
        """
        if not self.api_key:
            return None

        # Search for existing contacts at this domain
        existing = self._search_contacts_by_domain(domain)
        if existing:
            contact = existing[0]
            print(f"[apollo] Found existing contact: {contact.get('name')} at {domain}")
            return {
                "id":    contact.get("id"),
                "email": contact.get("email") or "",
                "name":  contact.get("name") or "",
            }

        # Create a new contact
        return self._create_contact(
            company_name=company_name,
            domain=domain,
            contact_name=contact_name,
            contact_title=contact_title,
            email_guess=email_guess,
        )

    def enroll_in_sequence(
        self,
        contact_id: str,
        sequence_id: str,
        pitch: dict,
    ) -> bool:
        """
        Enroll a contact in the given Apollo sequence.

        Stores pitch subject and signal info in the contact's notes/title
        so Apollo personalization tokens can reference them.

        Returns True on success.
        """
        if not self.api_key or not contact_id or not sequence_id:
            return False

        # Update contact with pitch context before enrolling
        self._update_contact_notes(contact_id, pitch)

        payload = {
            "contact_ids":                    [contact_id],
            "emailer_campaign_id":            sequence_id,
            "send_email_from_email_account_id": self.email_account_id,
        }

        result = self._request(
            "POST",
            f"{APOLLO_BASE}/emailer_campaigns/{sequence_id}/add_contact_ids",
            payload,
        )

        if result is None:
            return False

        enrolled = result.get("contacts", [])
        skipped  = result.get("skipped_contact_ids", {})

        if contact_id in skipped:
            reason = skipped[contact_id]
            print(f"[apollo] Contact skipped from sequence (reason: {reason})")
            # "already_in_campaign" is not a failure — contact is already enrolled
            if reason == "already_in_campaign":
                return True
            return False

        if enrolled:
            print(f"[apollo] Enrolled contact {contact_id} in sequence")
            return True

        print(f"[apollo] Unexpected enroll response: {result}")
        return False

    def get_sequence_id(self, sequence_name: Optional[str] = None) -> Optional[str]:
        """
        Find the Apollo sequence ID by name.
        Caches result at module level to avoid repeated API calls.
        Returns sequence ID string or None.
        """
        global _sequence_id_cache

        if _sequence_id_cache:
            return _sequence_id_cache

        name = sequence_name or self.sequence_name

        result = self._request(
            "POST",
            f"{APOLLO_BASE}/emailer_campaigns/search",
            {"page": 1, "per_page": 50},
        )

        if not result:
            return None

        for campaign in result.get("emailer_campaigns", []):
            if campaign.get("name", "").strip() == name:
                _sequence_id_cache = campaign["id"]
                print(f"[apollo] Found sequence '{name}': {_sequence_id_cache}")
                return _sequence_id_cache

        print(f"[apollo] Sequence '{name}' not found")
        return None

    def create_sequence_if_missing(self) -> Optional[str]:
        """
        Returns the existing sequence ID if found, otherwise creates
        a new 'Tanta Holdings - L&D AI Consulting' sequence.
        """
        existing = self.get_sequence_id()
        if existing:
            return existing

        print(f"[apollo] Creating sequence: {self.sequence_name}")
        result = self._request(
            "POST",
            f"{APOLLO_BASE}/emailer_campaigns",
            {"name": self.sequence_name},
        )

        if not result:
            return None

        campaign = result.get("emailer_campaign", {})
        seq_id   = campaign.get("id")

        if seq_id:
            global _sequence_id_cache
            _sequence_id_cache = seq_id
            print(f"[apollo] Created sequence: {seq_id}")

        return seq_id

    def get_contact_reply_status(self, contact_id: str) -> dict:
        """
        Fetch contact reply/engagement status from Apollo.

        Returns:
            {replied, opened, bounced, unsubscribed}
        """
        default = {"replied": False, "opened": False, "bounced": False, "unsubscribed": False}

        if not self.api_key or not contact_id:
            return default

        result = self._request("GET", f"{APOLLO_BASE}/contacts/{contact_id}")
        if not result:
            return default

        contact  = result.get("contact", {})
        statuses = contact.get("contact_campaign_statuses", [])

        replied       = False
        opened        = False
        bounced       = False
        unsubscribed  = bool(contact.get("email_unsubscribed"))

        email_status = (contact.get("email_status") or "").lower()
        if email_status in ("bounced", "invalid"):
            bounced = True

        for s in statuses:
            status_val = (s.get("status") or "").lower()
            if status_val in ("replied", "reply"):
                replied = True
            if status_val in ("opened", "open"):
                opened = True
            if status_val in ("bounced",):
                bounced = True
            if status_val in ("unsubscribed",):
                unsubscribed = True

        return {
            "replied":       replied,
            "opened":        opened,
            "bounced":       bounced,
            "unsubscribed":  unsubscribed,
        }

    def bulk_update_notion_from_apollo(self, notion_tracker) -> int:
        """
        Sync Apollo reply/engagement signals back to Notion.

        Iterates contacts in the sequence, finds those with activity,
        and updates Notion rows accordingly.

        Returns count of rows updated.
        """
        if not self.api_key:
            return 0

        sequence_id = self.get_sequence_id()
        if not sequence_id:
            print("[apollo] No sequence found — skipping Notion sync")
            return 0

        updated = 0
        page    = 1

        while True:
            result = self._request(
                "POST",
                f"{APOLLO_BASE}/contacts/search",
                {
                    "emailer_campaign_id": sequence_id,
                    "page":                page,
                    "per_page":            50,
                },
            )
            if not result:
                break

            contacts = result.get("contacts", [])
            if not contacts:
                break

            for contact in contacts:
                contact_id = contact.get("id")
                domain     = _domain_from_contact(contact)

                if not contact_id or not domain:
                    continue

                status = self.get_contact_reply_status(contact_id)

                # Only update Notion if there's a meaningful signal
                if not any(status.values()):
                    continue

                # Map Apollo signals to Notion reply category
                # Human triage handles intent classification
                if status["replied"]:
                    category = "interested"   # placeholder — human reviews actual reply
                    summary  = "Apollo: contact replied to sequence email"
                elif status["unsubscribed"]:
                    category = "unsubscribed"
                    summary  = "Apollo: contact unsubscribed"
                elif status["bounced"]:
                    category = "unsubscribed"
                    summary  = "Apollo: email bounced"
                else:
                    continue

                ok = notion_tracker.update_after_reply(domain, category, summary)
                if ok:
                    updated += 1

            # Check if more pages
            pagination = result.get("pagination", {})
            if page >= pagination.get("total_pages", 1):
                break
            page += 1

        print(f"[apollo] Synced {updated} Notion rows from Apollo")
        return updated

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _search_contacts_by_domain(self, domain: str) -> list:
        """Search Apollo for contacts at a given domain."""
        result = self._request(
            "POST",
            f"{APOLLO_BASE}/contacts/search",
            {"q_organization_domains": [domain], "page": 1, "per_page": 5},
        )
        if not result:
            return []
        return result.get("contacts", [])

    def _create_contact(
        self,
        company_name: str,
        domain: str,
        contact_name: str,
        contact_title: str,
        email_guess: str,
    ) -> Optional[dict]:
        """Create a new Apollo contact."""
        # Parse first/last name if provided
        first_name, last_name = _split_name(contact_name)

        payload: dict = {
            "organization_name": company_name,
            "website_url":       domain,
        }
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if contact_title:
            payload["title"] = contact_title
        if email_guess:
            payload["email"] = email_guess

        result = self._request("POST", f"{APOLLO_BASE}/contacts", payload)
        if not result:
            return None

        contact = result.get("contact", {})
        if not contact.get("id"):
            return None

        print(f"[apollo] Created contact {contact.get('name', 'unnamed')} at {domain}: {contact['id']}")
        return {
            "id":    contact["id"],
            "email": contact.get("email") or "",
            "name":  contact.get("name") or contact_name or "",
        }

    def _update_contact_notes(self, contact_id: str, pitch: dict) -> None:
        """
        Store pitch subject in contact notes so Apollo personalization
        tokens have context. Silently skips on error.
        """
        subject = pitch.get("subject", "")
        company = pitch.get("company_name", "")
        signal  = pitch.get("signal_type", "")

        if not subject:
            return

        note = f"Outreach: {subject}"
        if company:
            note += f" | Company: {company}"
        if signal:
            note += f" | Signal: {signal}"

        self._request(
            "PATCH",
            f"{APOLLO_BASE}/contacts/{contact_id}",
            {"label_names": [], "raw_address": "", "note": note},
        )

    def _request(
        self,
        method: str,
        url: str,
        payload: Optional[dict] = None,
    ) -> Optional[dict]:
        """
        Make an Apollo API request. Returns parsed JSON or None on error.
        Never raises — all errors are printed and swallowed.
        """
        if not self.api_key:
            return None

        headers = {
            "x-api-key":    self.api_key,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }
        data = json.dumps(payload).encode() if payload is not None else None
        req  = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            print(f"[apollo] HTTP {e.code} on {method} {url.split('/')[-1]}: {body}")
            return None
        except Exception as e:
            print(f"[apollo] {e}")
            return None


# ------------------------------------------------------------------
# Module helpers
# ------------------------------------------------------------------

def _split_name(full_name: str) -> tuple[str, str]:
    """Split 'First Last' into (first, last). Returns ('', '') if empty."""
    if not full_name:
        return "", ""
    parts = full_name.strip().split(None, 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _domain_from_contact(contact: dict) -> str:
    """Extract registrable domain from a contact's account or email."""
    # Try account website
    account = contact.get("account", {}) or {}
    website = account.get("website_url", "") or ""
    if website:
        from urllib.parse import urlparse
        host  = urlparse(website).hostname or website
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])

    # Fall back to email domain
    email = contact.get("email", "") or ""
    if "@" in email:
        return email.split("@")[1]

    return ""
