"""
client_hunt/notion_leads.py — Notion Client Hunt Dashboard.

Creates and manages a "Client Hunt Dashboard" database in Notion.
Parent page: NOTION_DASHBOARD_PAGE_ID (Job Hunt Dashboard page).

On first run: creates the database if NOTION_LEADS_DB_ID is not set.
Saves the generated DB ID to .notion_leads_db_id for subsequent runs.

Uses pure urllib.request — no SDK required.
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN      = os.environ.get("NOTION_TOKEN", "")
NOTION_VERSION    = "2022-06-28"
DASHBOARD_PAGE_ID = os.environ.get("NOTION_DASHBOARD_PAGE_ID", "35084b11-8b54-813a-8ef2-eca2cf434a03")

# Local cache file for the DB ID
_DB_ID_FILE = Path(__file__).parent.parent / ".notion_leads_db_id"


class NotionLeadsTracker:
    """
    Tracks client hunt leads in a Notion database.
    Creates the database on first instantiation if needed.
    """

    def __init__(self):
        self.token   = NOTION_TOKEN
        self.enabled = bool(self.token)
        if not self.enabled:
            print("[notion_leads] Disabled — set NOTION_TOKEN in .env")
            self.db_id = ""
            return

        self.db_id = self._load_db_id()
        if not self.db_id:
            self.db_id = self._ensure_database()
            if self.db_id:
                self._save_db_id(self.db_id)
                print(f"[notion_leads] Created Client Hunt Dashboard: {self.db_id}")
            else:
                print("[notion_leads] Failed to create database")
        else:
            print(f"[notion_leads] Using DB: {self.db_id}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_lead(self, lead: dict, pitch: dict) -> Optional[str]:
        """
        Create or update a Notion row for this lead.
        Returns the page ID or None.
        """
        if not self.enabled or not self.db_id:
            return None

        domain    = lead.get("domain", "")
        page_id   = self.find_by_domain(domain)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        signal_date = lead.get("signal_date", "")
        # Normalize signal_date to YYYY-MM-DD if it has time component
        if signal_date and "T" in signal_date:
            signal_date = signal_date[:10]

        props = self._build_properties(
            company_name     = lead.get("company_name", "Unknown"),
            status           = "New Lead",
            signal_type      = lead.get("signal_type", "ai_initiative"),
            buy_signal_score = lead.get("buy_signal_score", 5),
            signal_text      = lead.get("signal_text", "")[:2000],
            signal_url       = lead.get("signal_url", ""),
            signal_date      = signal_date or today,
            pitch_subject    = pitch.get("subject", ""),
            notes            = f"Source: {lead.get('source', '')}\nDomain: {domain}",
        )

        if page_id:
            result = self._update_page(page_id, props)
            return result
        else:
            return self._create_page(props)

    def find_by_domain(self, domain: str) -> Optional[str]:
        """Find a Notion page by company domain. Returns page_id or None."""
        if not self.enabled or not self.db_id or not domain:
            return None

        payload = {
            "filter": {
                "property": "Notes",
                "rich_text": {"contains": f"Domain: {domain}"}
            }
        }
        result = self._request("POST", f"https://api.notion.com/v1/databases/{self.db_id}/query", payload)
        if result and result.get("results"):
            return result["results"][0]["id"]
        return None

    def update_after_pitch(self, domain: str, draft_id: str, pitch_date: str = "") -> bool:
        """Set Status=Pitched, store Gmail draft ID, set pitched date."""
        if not self.enabled:
            return False

        page_id = self.find_by_domain(domain)
        if not page_id:
            return False

        today = pitch_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        props = {
            "Status":        {"select": {"name": "Pitched"}},
            "Gmail Draft ID": {"rich_text": [{"text": {"content": draft_id[:2000]}}]},
            "Pitched Date":  {"date": {"start": today}},
        }
        return bool(self._update_page(page_id, props))

    def update_after_reply(self, domain: str, category: str, summary: str) -> bool:
        """Set reply category and summary after a reply arrives."""
        if not self.enabled:
            return False

        page_id = self.find_by_domain(domain)
        if not page_id:
            return False

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        props = {
            "Reply Category":  {"select": {"name": category}},
            "Reply Summary":   {"rich_text": [{"text": {"content": summary[:2000]}}]},
            "Last Reply Date": {"date": {"start": today}},
        }
        return bool(self._update_page(page_id, props))

    def get_unpitched_leads(self, limit: int = 50) -> list[dict]:
        """Return rows where Status = New Lead."""
        if not self.enabled or not self.db_id:
            return []

        payload = {
            "filter": {
                "property": "Status",
                "select":   {"equals": "New Lead"},
            },
            "page_size": min(limit, 100),
        }
        result = self._request("POST", f"https://api.notion.com/v1/databases/{self.db_id}/query", payload)
        if not result:
            return []

        rows = []
        for page in result.get("results", []):
            props = page.get("properties", {})
            rows.append({
                "page_id":     page["id"],
                "company_name": _get_title(props, "Company"),
                "status":      _get_select(props, "Status"),
                "signal_type": _get_select(props, "Signal Type"),
                "signal_url":  _get_url(props, "Signal URL"),
                "notes":       _get_rich_text(props, "Notes"),
            })
        return rows

    # ------------------------------------------------------------------
    # Database creation
    # ------------------------------------------------------------------

    def _ensure_database(self) -> Optional[str]:
        """Create the Client Hunt Dashboard database under the Job Hunt Dashboard page."""
        payload = {
            "parent": {"type": "page_id", "page_id": DASHBOARD_PAGE_ID},
            "title": [{"type": "text", "text": {"content": "Client Hunt Dashboard"}}],
            "properties": {
                "Company": {
                    "title": {}
                },
                "Status": {
                    "select": {
                        "options": [
                            {"name": "New Lead",       "color": "blue"},
                            {"name": "Pitched",        "color": "yellow"},
                            {"name": "Replied",        "color": "green"},
                            {"name": "Meeting Booked", "color": "purple"},
                            {"name": "Proposal Sent",  "color": "orange"},
                            {"name": "Closed Won",     "color": "green"},
                            {"name": "Closed Lost",    "color": "red"},
                            {"name": "Nurture",        "color": "gray"},
                            {"name": "Unsubscribed",   "color": "default"},
                        ]
                    }
                },
                "Signal Type": {
                    "select": {
                        "options": [
                            {"name": "ai_initiative", "color": "blue"},
                            {"name": "hiring_ld",     "color": "green"},
                            {"name": "funding",       "color": "yellow"},
                            {"name": "lms_migration", "color": "orange"},
                        ]
                    }
                },
                "Buy Signal Score": {"number": {}},
                "Signal Text":      {"rich_text": {}},
                "Signal URL":       {"url": {}},
                "Signal Date":      {"date": {}},
                "Pitch Subject":    {"rich_text": {}},
                "Pitched Date":     {"date": {}},
                "Last Reply Date":  {"date": {}},
                "Reply Category": {
                    "select": {
                        "options": [
                            {"name": "interested",    "color": "green"},
                            {"name": "objection",     "color": "yellow"},
                            {"name": "not_now",       "color": "orange"},
                            {"name": "wrong_person",  "color": "gray"},
                            {"name": "ooo",           "color": "blue"},
                            {"name": "unsubscribed",  "color": "red"},
                        ]
                    }
                },
                "Reply Summary":  {"rich_text": {}},
                "Gmail Draft ID": {"rich_text": {}},
                "Notes":          {"rich_text": {}},
            },
        }
        result = self._request("POST", "https://api.notion.com/v1/databases", payload)
        if result:
            return result.get("id")
        return None

    # ------------------------------------------------------------------
    # Page operations
    # ------------------------------------------------------------------

    def _build_properties(self, company_name: str, status: str, signal_type: str,
                           buy_signal_score: int, signal_text: str, signal_url: str,
                           signal_date: str, pitch_subject: str, notes: str) -> dict:
        props: dict = {
            "Company": {"title": [{"text": {"content": company_name[:200]}}]},
            "Status":  {"select": {"name": status}},
        }
        if signal_type:
            props["Signal Type"] = {"select": {"name": signal_type}}
        if buy_signal_score is not None:
            props["Buy Signal Score"] = {"number": buy_signal_score}
        if signal_text:
            props["Signal Text"] = {"rich_text": [{"text": {"content": signal_text[:2000]}}]}
        if signal_url:
            props["Signal URL"] = {"url": signal_url}
        if signal_date:
            props["Signal Date"] = {"date": {"start": signal_date}}
        if pitch_subject:
            props["Pitch Subject"] = {"rich_text": [{"text": {"content": pitch_subject[:2000]}}]}
        if notes:
            props["Notes"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}
        return props

    def _create_page(self, properties: dict) -> Optional[str]:
        payload = {
            "parent": {"database_id": self.db_id},
            "properties": properties,
        }
        result = self._request("POST", "https://api.notion.com/v1/pages", payload)
        if result:
            page_id = result.get("id")
            print(f"[notion_leads] Created lead row: {page_id}")
            return page_id
        return None

    def _update_page(self, page_id: str, properties: dict) -> Optional[str]:
        result = self._request(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            {"properties": properties},
        )
        if result:
            print(f"[notion_leads] Updated lead row: {page_id}")
            return page_id
        return None

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _request(self, method: str, url: str, payload: dict = None):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode() if payload else None
        req  = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:400]
            print(f"[notion_leads] HTTP {e.code} on {method} {url[-60:]}: {body}")
            return None
        except Exception as e:
            print(f"[notion_leads] Request failed: {e}")
            return None

    # ------------------------------------------------------------------
    # DB ID persistence
    # ------------------------------------------------------------------

    def _load_db_id(self) -> str:
        """Load DB ID from env var or local cache file."""
        env_id = os.environ.get("NOTION_LEADS_DB_ID", "")
        if env_id:
            return env_id
        if _DB_ID_FILE.exists():
            return _DB_ID_FILE.read_text().strip()
        return ""

    def _save_db_id(self, db_id: str) -> None:
        """Save DB ID to local cache file."""
        try:
            _DB_ID_FILE.write_text(db_id)
        except Exception as e:
            print(f"[notion_leads] Could not save DB ID to file: {e}")


# ------------------------------------------------------------------
# Property extraction helpers
# ------------------------------------------------------------------

def _get_title(props: dict, key: str) -> str:
    try:
        return "".join(p.get("plain_text", "") for p in props[key]["title"])
    except (KeyError, TypeError):
        return ""


def _get_rich_text(props: dict, key: str) -> str:
    try:
        return "".join(p.get("plain_text", "") for p in props[key]["rich_text"])
    except (KeyError, TypeError):
        return ""


def _get_select(props: dict, key: str) -> str:
    try:
        return props[key]["select"]["name"]
    except (KeyError, TypeError):
        return ""


def _get_url(props: dict, key: str) -> str:
    try:
        return props[key]["url"] or ""
    except (KeyError, TypeError):
        return ""
