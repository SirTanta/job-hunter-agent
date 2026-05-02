"""
tools/auto_apply.py — Universal job application submitter.

Routes each job URL to the correct ATS handler via tools/ats/__init__.py.
Starts a real-time email monitor before each apply session to capture
OTP/verification codes automatically.

Supported ATS systems (dedicated handlers):
  LinkedIn Easy Apply, Indeed Apply, Lever, Greenhouse, Ashby,
  Workday (with tab handling + OTP), SmartRecruiters, BambooHR

Generic Claude-powered handler covers everything else:
  iCIMS, Taleo, Jobvite, Breezy HR, Recruitee, Rippling, Wellfound,
  Workable, JazzHR, Pinpoint, Comeet, and any unknown ATS.

Usage:
    applier = AutoApplier(tracker)
    result = applier.apply(job, resume_path, cover_path, company_profile)
"""

import os
import traceback
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from tools.ats import detect_ats, get_handler
from tools.email_monitor import EmailMonitor

MIN_FIT_SCORE = int(os.environ.get("MIN_FIT_SCORE", "5"))


class AutoApplier:

    def __init__(self, tracker=None):
        self.tracker = tracker

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(self, job: dict, resume_path: Optional[Path] = None,
              cover_path: Optional[Path] = None,
              company_profile: Optional[dict] = None) -> dict:
        """
        Submit an application for a job.

        Starts an email monitor before launching Playwright so any
        OTP/verification code that arrives mid-apply is captured automatically.
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
        print(f"\n[auto_apply] {job.get('title')} @ {job.get('company')} -> {ats_name}")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._manual_fallback(job, "playwright not installed — run: pip install playwright && playwright install chromium")

        # Start email monitor BEFORE launching browser
        # so it's already watching when the ATS sends a code
        monitor = EmailMonitor()
        monitor_active = monitor.start()
        if not monitor_active:
            print("[auto_apply] Email monitor inactive — OTP capture disabled")
            monitor = None

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--disable-extensions",
                    ],
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

                # Get handler — pass email_monitor for Workday + any OTP-gated ATS
                handler = get_handler(
                    url,
                    tracker=self.tracker,
                    email_monitor=monitor,
                )

                result = handler.submit(page, job, resume_path, cover_path)
                browser.close()

        except Exception as e:
            print(f"[auto_apply] Playwright error: {e}")
            traceback.print_exc()
            result = self._manual_fallback(job, str(e))
        finally:
            if monitor:
                monitor.stop()

        # Update tracker
        if result.get("success"):
            self._update_tracker(job, "applied")
        elif result.get("method") == "manual":
            self._update_tracker(job, "manual_review")

        return result

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
