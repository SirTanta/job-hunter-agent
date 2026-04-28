"""
tools/notion_tracker.py — Notion job applications database integration.

Mirrors every application to the Job Hunt Dashboard in Notion.
Separate from Tanta Holdings operations — this is Jon's personal job search.

Database: "Applications" (NOTION_APPLICATIONS_DB_ID in .env)
Dashboard: "Job Hunt Dashboard" (NOTION_DASHBOARD_PAGE_ID in .env)

Operations:
  - upsert_application()  — create or update a row when an application is saved
  - update_status()       — change Status + log email summary when emails arrive
  - find_by_url()         — look up an existing row by job URL
"""

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN  = os.environ.get("NOTION_TOKEN", "")
APPLICATIONS_DB = os.environ.get("NOTION_APPLICATIONS_DB_ID", "")
NOTION_VERSION  = "2022-06-28"

# Status mapping from internal tracker statuses to Notion select options
STATUS_MAP = {
    "applied":        "Applied",
    "screening":      "Screening",
    "interview":      "Interview",
    "offer":          "Offer",
    "rejected":       "Rejected",
    "withdrawn":      "Withdrawn",
    "manual_review":  "Manual Review",
    "manual":         "Manual Review",
    "found":          "Applied",
    "researched":     "Applied",
    "expired":        "Withdrawn",
}

# ATS name mapping
ATS_DISPLAY = {
    "linkedin":        "LinkedIn",
    "linkedin_easy_apply": "LinkedIn",
    "indeed":          "Indeed",
    "indeed_apply":    "Indeed",
    "lever":           "Lever",
    "greenhouse":      "Greenhouse",
    "ashby":           "Ashby",
    "workday":         "Workday",
    "smartrecruiters": "SmartRecruiters",
    "bamboohr":        "BambooHR",
    "generic":         "Generic",
    "manual":          "Generic",
    "skipped":         "Generic",
}


class NotionTracker:
    """
    Syncs job applications to Notion.
    Silently no-ops if NOTION_TOKEN or NOTION_APPLICATIONS_DB_ID is missing.
    """

    def __init__(self):
        self.enabled = bool(NOTION_TOKEN and APPLICATIONS_DB)
        if not self.enabled:
            print("[notion] Disabled — set NOTION_TOKEN and NOTION_APPLICATIONS_DB_ID in .env")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_application(self, job: dict, apply_result: dict,
                           company_profile: dict = None,
                           resume_path: str = "") -> Optional[str]:
        """
        Create or update a Notion row for this application.

        Args:
            job            : job dict (title, company, url, location)
            apply_result   : result from AutoApplier (success, method, job_url)
            company_profile: company research dict (fit_score, overview, etc.)
            resume_path        : path to the tailored resume file

        Returns the Notion page ID, or None on failure.
        """
        if not self.enabled:
            return None

        url = job.get("url", "") or apply_result.get("job_url", "")

        # Check if a row already exists for this URL
        existing_id = self.find_by_url(url)

        status_key = "applied" if apply_result.get("success") else "manual_review"
        notion_status = STATUS_MAP.get(status_key, "Applied")
        ats_method    = apply_result.get("method", "generic")
        ats_display   = ATS_DISPLAY.get(ats_method, "Generic")
        fit_score     = (company_profile or {}).get("fit_score")
        resume_filename   = os.path.basename(str(resume_path)) if resume_path else ""

        props = self._build_properties(
            title      = job.get("title", "Unknown Role"),
            company    = job.get("company", ""),
            status     = notion_status,
            ats        = ats_display,
            applied_date = datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            fit_score  = fit_score,
            job_url    = url,
            resume_file    = resume_filename,
            notes      = (company_profile or {}).get("why_apply", "")[:200],
        )

        if existing_id:
            return self._update_page(existing_id, props)
        else:
            return self._create_page(props)

    def update_status(self, job_url: str, status: str,
                      email_subject: str = "", email_summary: str = "",
                      email_date: str = "") -> bool:
        """
        Update the Status, Last Email, and Email Summary fields for an application.
        Called by email_processor when a new ATS email arrives.

        Args:
            job_url       : URL to find the row
            status        : internal status key ("interview", "rejected", etc.)
            email_subject : subject line of the email
            email_summary : Claude-generated summary of the email
            email_date    : ISO date string of the email

        Returns True on success.
        """
        if not self.enabled:
            return False

        page_id = self.find_by_url(job_url)
        if not page_id:
            print(f"[notion] No row found for {job_url[:60]} — skipping update")
            return False

        notion_status = STATUS_MAP.get(status, status.title())
        email_dt = email_date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        props = {}
        if notion_status:
            props["Status"] = {"select": {"name": notion_status}}
        if email_dt:
            props["Last Email"] = {"date": {"start": email_dt}}
        if email_summary:
            summary = f"[{email_subject}] {email_summary}"[:2000]
            props["Email Summary"] = {"rich_text": [{"text": {"content": summary}}]}

        return bool(self._update_page(page_id, props))

    def find_by_url(self, job_url: str) -> Optional[str]:
        """Query the database for a row matching job_url. Returns page ID or None."""
        if not self.enabled or not job_url:
            return None

        payload = {
            "filter": {
                "property": "Job URL",
                "url": {"equals": job_url}
            }
        }
        result = self._request(
            "POST",
            f"https://api.notion.com/v1/databases/{APPLICATIONS_DB}/query",
            payload,
        )
        if result and result.get("results"):
            return result["results"][0]["id"]
        return None

    def get_all_applications(self) -> list[dict]:
        """Return all rows from the Applications database."""
        if not self.enabled:
            return []

        result = self._request(
            "POST",
            f"https://api.notion.com/v1/databases/{APPLICATIONS_DB}/query",
            {"page_size": 100},
        )
        if not result:
            return []

        rows = []
        for page in result.get("results", []):
            props = page.get("properties", {})
            rows.append({
                "page_id":    page["id"],
                "title":      _get_text(props, "Job Title", "title"),
                "company":    _get_text(props, "Company", "rich_text"),
                "status":     _get_select(props, "Status"),
                "job_url":    _get_url(props, "Job URL"),
                "applied_date": _get_date(props, "Applied Date"),
            })
        return rows

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_properties(self, title: str, company: str, status: str,
                           ats: str, applied_date: str, fit_score,
                           job_url: str, resume_file: str, notes: str) -> dict:
        props = {
            "Job Title": {"title": [{"text": {"content": title[:200]}}]},
            "Status":    {"select": {"name": status}},
            "ATS":       {"select": {"name": ats}},
        }
        if company:
            props["Company"] = {"rich_text": [{"text": {"content": company[:200]}}]}
        if applied_date:
            props["Applied Date"] = {"date": {"start": applied_date}}
        if fit_score is not None:
            try:
                props["Fit Score"] = {"number": int(fit_score)}
            except (TypeError, ValueError):
                pass
        if job_url:
            props["Job URL"] = {"url": job_url}
        if resume_file:
            props["Resume File"] = {"rich_text": [{"text": {"content": resume_file}}]}
        if notes:
            props["Notes"] = {"rich_text": [{"text": {"content": notes}}]}
        return props

    def _create_page(self, properties: dict) -> Optional[str]:
        payload = {
            "parent": {"database_id": APPLICATIONS_DB},
            "properties": properties,
        }
        result = self._request("POST", "https://api.notion.com/v1/pages", payload)
        if result:
            page_id = result.get("id")
            print(f"[notion] Created application row: {page_id}")
            return page_id
        return None

    def _update_page(self, page_id: str, properties: dict) -> Optional[str]:
        result = self._request(
            "PATCH",
            f"https://api.notion.com/v1/pages/{page_id}",
            {"properties": properties},
        )
        if result:
            print(f"[notion] Updated row {page_id}")
            return page_id
        return None

    def _request(self, method: str, url: str, payload: dict = None):
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        data = json.dumps(payload).encode() if payload else None
        req  = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            print(f"[notion] {method} {url} → {e.code}: {body}")
            return None
        except Exception as e:
            print(f"[notion] Request failed: {e}")
            return None


# ------------------------------------------------------------------
# Property extraction helpers
# ------------------------------------------------------------------

def _get_text(props: dict, key: str, prop_type: str) -> str:
    try:
        parts = props[key][prop_type]
        return "".join(p.get("plain_text", "") for p in parts)
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


def _get_date(props: dict, key: str) -> str:
    try:
        return props[key]["date"]["start"] or ""
    except (KeyError, TypeError):
        return ""
