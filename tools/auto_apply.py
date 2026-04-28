"""
tools/auto_apply.py — Universal job application submitter.

Routes each job URL to the correct ATS handler via tools/ats/__init__.py.

Supported ATS systems (dedicated handlers):
  LinkedIn Easy Apply, Indeed Apply, Lever, Greenhouse, Ashby,
  Workday, SmartRecruiters, BambooHR

Generic Claude-powered handler covers:
  iCIMS, Taleo, Jobvite, Breezy HR, Recruitee, Rippling, Wellfound,
  Workable, JazzHR, Pinpoint, Comeet, and any unknown ATS.

Usage:
    applier = AutoApplier(tracker)
    result = applier.apply(job, cv_path, cover_path, company_profile)
"""

import os
import traceback
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from tools.ats import detect_ats, get_handler

# Minimum fit score before auto-applying (override via .env)
MIN_FIT_SCORE = int(os.environ.get("MIN_FIT_SCORE", "6"))


class AutoApplier:
    """
    Routes job applications to the correct ATS handler and launches Playwright.
    """

    def __init__(self, tracker=None):
        self.tracker = tracker

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self, job: dict, cv_path: Optional[Path] = None,
              cover_path: Optional[Path] = None,
              company_profile: Optional[dict] = None) -> dict:
        """
        Submit an application for a job.

        Args:
            job             : job dict — needs at minimum url, title, company
            cv_path         : path to tailored CV .docx
            cover_path      : path to cover letter .docx
            company_profile : company research dict (used for fit_score gate)

        Returns:
            dict with: success, method, message, job_url
        """
        fit_score = (company_profile or {}).get("fit_score", 10)
        if fit_score < MIN_FIT_SCORE:
            return {
                "success": False,
                "method":  "skipped",
                "message": f"Fit score {fit_score}/10 below threshold {MIN_FIT_SCORE}",
                "job_url": job.get("url", ""),
            }

        url = job.get("url", "")
        ats_name, _ = detect_ats(url)
        title = job.get("title", "")
        company = job.get("company", "")
        print(f"\n[auto_apply] {title} @ {company} → {ats_name}")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("[auto_apply] playwright not installed — run: pip install playwright && playwright install chromium")
            return self._manual_fallback(job, "playwright not installed")

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                )
                page = ctx.new_page()

                # Get the ATS-specific handler
                handler = get_handler(url, tracker=self.tracker)

                # Submit
                result = handler.submit(page, job, cv_path, cover_path)
                browser.close()

            # Update tracker
            if result.get("success"):
                self._update_tracker(job, "applied")
            elif result.get("method") == "manual":
                self._update_tracker(job, "manual_review")

            return result

        except Exception as e:
            print(f"[auto_apply] Playwright error: {e}")
            traceback.print_exc()
            return self._manual_fallback(job, str(e))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _manual_fallback(self, job: dict, reason: str = "") -> dict:
        url = job.get("url", "")
        self._update_tracker(job, "manual_review")
        return {
            "success": False,
            "method":  "manual",
            "message": f"Manual review needed: {reason}" if reason else "Manual review needed",
            "job_url": url,
        }

    def _update_tracker(self, job: dict, status: str):
        if not self.tracker:
            return
        try:
            url = job.get("url", "")
            if url:
                self.tracker.update_job_status_by_url(url, status)
        except Exception as e:
            print(f"[auto_apply] Tracker update failed (non-fatal): {e}")
