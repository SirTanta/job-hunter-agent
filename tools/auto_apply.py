"""
tools/auto_apply.py — Automated job application submission via Playwright.

Supports:
  - LinkedIn Easy Apply (session cookie auth)
  - Indeed Apply
  - Generic form fallback (opens URL, marks for manual review)

Usage:
    applier = AutoApplier(tracker)
    result = applier.apply(job, cv_path, cover_path)
"""

import os
import time
import traceback
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from config import CANDIDATE_PROFILE

# Minimum fit score required before auto-applying (0 = apply to everything)
MIN_FIT_SCORE = int(os.environ.get("MIN_FIT_SCORE", "6"))


def _get_linkedin_cookie() -> str:
    return os.environ.get("LINKEDIN_LI_AT", "")


class AutoApplier:
    """
    Submits job applications automatically where possible.

    Priority order per job:
      1. LinkedIn Easy Apply  (if job URL is linkedin.com)
      2. Indeed Apply         (if job URL is indeed.com)
      3. Generic fallback     (mark for manual review, log apply URL)
    """

    def __init__(self, tracker=None):
        self.tracker = tracker
        self._pw = None
        self._browser = None

    # ------------------------------------------------------------------
    # apply() — public entry point
    # ------------------------------------------------------------------

    def apply(self, job: dict, cv_path: Optional[Path] = None,
              cover_path: Optional[Path] = None,
              company_profile: Optional[dict] = None) -> dict:
        """
        Attempt to submit an application for a job.

        Args:
            job             : job dict from job_finder
            cv_path         : path to tailored CV .docx
            cover_path      : path to cover letter .docx
            company_profile : company research dict (used for fit_score gate)

        Returns:
            dict with keys:
              success  : bool
              method   : "linkedin_easy_apply" | "indeed_apply" | "manual"
              message  : human-readable result
              job_url  : the application URL
        """
        fit_score = (company_profile or {}).get("fit_score", 10)
        if fit_score < MIN_FIT_SCORE:
            return {
                "success": False,
                "method":  "skipped",
                "message": f"Fit score {fit_score} below threshold {MIN_FIT_SCORE} — skipped",
                "job_url": job.get("url", ""),
            }

        url = job.get("url", "")
        title = job.get("title", "")
        company = job.get("company", "")
        print(f"\n[auto_apply] Applying: {title} @ {company}")
        print(f"[auto_apply] URL: {url}")

        if "linkedin.com" in url:
            return self._apply_linkedin(job, cv_path, cover_path)
        elif "indeed.com" in url:
            return self._apply_indeed(job, cv_path, cover_path)
        else:
            return self._manual_fallback(job)

    # ------------------------------------------------------------------
    # LinkedIn Easy Apply
    # ------------------------------------------------------------------

    def _apply_linkedin(self, job: dict, cv_path: Optional[Path],
                        cover_path: Optional[Path]) -> dict:
        """
        Submit via LinkedIn Easy Apply using the li_at session cookie.

        Flow:
          1. Launch Playwright with li_at cookie injected
          2. Navigate to the job URL
          3. Click "Easy Apply" button
          4. Fill the multi-step form:
             - Contact info (pre-filled from profile)
             - Resume upload (cv_path .docx)
             - Cover letter (plain text paste)
             - Phone / location fields
          5. Submit and capture confirmation
          6. Update tracker status to "applied"
        """
        li_at = _get_linkedin_cookie()
        if not li_at:
            print("[auto_apply] No LINKEDIN_LI_AT cookie — falling back to manual")
            return self._manual_fallback(job)

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            print("[auto_apply] playwright not installed — pip install playwright")
            return self._manual_fallback(job)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                # Inject li_at session cookie
                ctx.add_cookies([{
                    "name":   "li_at",
                    "value":  li_at,
                    "domain": ".linkedin.com",
                    "path":   "/",
                }])
                page = ctx.new_page()

                # Navigate to job posting
                page.goto(job["url"], timeout=20000)
                time.sleep(2)

                # Check for Easy Apply button
                easy_apply_btn = page.query_selector(
                    "button.jobs-apply-button, "
                    "button[aria-label*='Easy Apply'], "
                    "button.jobs-s-apply__button"
                )
                if not easy_apply_btn:
                    print("[auto_apply] No Easy Apply button found")
                    browser.close()
                    return self._manual_fallback(job)

                easy_apply_btn.click()
                time.sleep(1)

                # Fill form fields across all steps
                self._fill_linkedin_form(page, cv_path, cover_path)

                # Click Submit / Review / Next through all steps
                submitted = self._linkedin_submit_loop(page)
                browser.close()

                if submitted:
                    self._update_tracker(job, "applied")
                    print("[auto_apply] LinkedIn Easy Apply submitted")
                    return {
                        "success": True,
                        "method":  "linkedin_easy_apply",
                        "message": "Submitted via LinkedIn Easy Apply",
                        "job_url": job.get("url", ""),
                    }
                else:
                    return self._manual_fallback(job, reason="Submit button not found")

        except Exception as e:
            print(f"[auto_apply] LinkedIn apply error: {e}")
            traceback.print_exc()
            return self._manual_fallback(job, reason=str(e))

    def _fill_linkedin_form(self, page, cv_path: Optional[Path],
                            cover_path: Optional[Path]):
        """Fill standard LinkedIn Easy Apply form fields."""
        profile = CANDIDATE_PROFILE

        # Phone number
        phone_field = page.query_selector("input[id*='phoneNumber'], input[name*='phone']")
        if phone_field:
            phone_field.fill(profile.get("phone", ""))

        # Resume upload — LinkedIn accepts PDF/DOCX
        if cv_path and Path(cv_path).exists():
            upload_btn = page.query_selector("input[type='file']")
            if upload_btn:
                upload_btn.set_input_files(str(cv_path))
                time.sleep(1)
                print(f"[auto_apply] CV uploaded: {cv_path}")

        # Cover letter text area (if present)
        if cover_path and Path(cover_path).exists():
            cover_text = _docx_to_text(cover_path)
            if cover_text:
                cover_area = page.query_selector(
                    "textarea[id*='coverLetter'], "
                    "textarea[placeholder*='cover letter'], "
                    "div[aria-label*='Cover letter'] textarea"
                )
                if cover_area:
                    cover_area.fill(cover_text[:3000])

        # City/location if prompted
        city_field = page.query_selector("input[id*='city'], input[placeholder*='City']")
        if city_field:
            city_field.fill("Rio Rancho")

    def _linkedin_submit_loop(self, page, max_steps: int = 8) -> bool:
        """
        Click through Next/Review/Submit buttons until the form is done.
        Returns True if a Submit confirmation is detected.
        """
        for step in range(max_steps):
            time.sleep(1)

            # Check for "Application submitted" confirmation
            confirm = page.query_selector(
                "h3:has-text('Application submitted'), "
                "div:has-text('application was sent'), "
                ".artdeco-inline-feedback--success"
            )
            if confirm:
                return True

            # Try Submit button first
            submit_btn = page.query_selector(
                "button[aria-label*='Submit application'], "
                "button:has-text('Submit application')"
            )
            if submit_btn:
                submit_btn.click()
                time.sleep(2)
                return True

            # Try Next / Review
            next_btn = page.query_selector(
                "button[aria-label*='Continue'], "
                "button[aria-label*='Next'], "
                "button[aria-label*='Review'], "
                "button:has-text('Next'), "
                "button:has-text('Review')"
            )
            if next_btn:
                next_btn.click()
                time.sleep(1)
                continue

            # No actionable button found
            print(f"[auto_apply] Step {step+1}: no button found — stopping")
            break

        return False

    # ------------------------------------------------------------------
    # Indeed Apply
    # ------------------------------------------------------------------

    def _apply_indeed(self, job: dict, cv_path: Optional[Path],
                      cover_path: Optional[Path]) -> dict:
        """
        Submit via Indeed Apply.

        Indeed's apply flow requires a logged-in session. We use the
        INDEED_SESSION env var (cookie string) if available, otherwise
        fall back to manual.
        """
        indeed_session = os.environ.get("INDEED_SESSION", "")
        if not indeed_session:
            print("[auto_apply] No INDEED_SESSION cookie — falling back to manual")
            return self._manual_fallback(job)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return self._manual_fallback(job)

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                ctx = browser.new_context()

                # Parse and inject Indeed session cookies
                for pair in indeed_session.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        name, _, val = pair.partition("=")
                        ctx.add_cookies([{
                            "name":   name.strip(),
                            "value":  val.strip(),
                            "domain": ".indeed.com",
                            "path":   "/",
                        }])

                page = ctx.new_page()
                page.goto(job["url"], timeout=20000)
                time.sleep(2)

                # Click Apply Now
                apply_btn = page.query_selector(
                    "button#indeedApplyButton, "
                    "a#applyButtonLinkContainer, "
                    "button[data-testid='job-apply-button']"
                )
                if not apply_btn:
                    browser.close()
                    return self._manual_fallback(job)

                apply_btn.click()
                time.sleep(2)

                # Upload resume
                if cv_path and Path(cv_path).exists():
                    upload = page.query_selector("input[type='file']")
                    if upload:
                        upload.set_input_files(str(cv_path))
                        time.sleep(1)

                # Submit loop
                submitted = self._linkedin_submit_loop(page)
                browser.close()

                if submitted:
                    self._update_tracker(job, "applied")
                    return {
                        "success": True,
                        "method":  "indeed_apply",
                        "message": "Submitted via Indeed Apply",
                        "job_url": job.get("url", ""),
                    }
                else:
                    return self._manual_fallback(job, reason="Submit flow incomplete")

        except Exception as e:
            print(f"[auto_apply] Indeed apply error: {e}")
            return self._manual_fallback(job, reason=str(e))

    # ------------------------------------------------------------------
    # Manual fallback
    # ------------------------------------------------------------------

    def _manual_fallback(self, job: dict, reason: str = "") -> dict:
        """
        When auto-apply isn't possible, log the job for manual review.
        The URL is printed prominently so Jon can open it directly.
        """
        url = job.get("url", "")
        title = job.get("title", "")
        company = job.get("company", "")
        msg = f"Manual review needed: {title} @ {company}"
        if reason:
            msg += f" ({reason})"
        print(f"[auto_apply] MANUAL: {url}")
        self._update_tracker(job, "manual_review")
        return {
            "success": False,
            "method":  "manual",
            "message": msg,
            "job_url": url,
        }

    # ------------------------------------------------------------------
    # Tracker update
    # ------------------------------------------------------------------

    def _update_tracker(self, job: dict, status: str):
        if not self.tracker:
            return
        try:
            url = job.get("url", "")
            if url:
                self.tracker.update_job_status_by_url(url, status)
        except Exception as e:
            print(f"[auto_apply] Tracker update failed (non-fatal): {e}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _docx_to_text(path: Path) -> str:
    """Extract plain text from a .docx for pasting into cover letter fields."""
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""
