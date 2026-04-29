"""
tools/auto_apply.py — Universal job application submitter.

Routes each job URL to the correct ATS handler via tools/ats/__init__.py.
Starts a real-time email monitor before each apply session to capture
OTP/verification codes automatically.

Improvements:
  - Prefers company careers page URL over job board buttons
  - Validates ATS keyword match before submission

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
import re
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

        Steps:
          1. Check fit score threshold
          2. Validate ATS keywords in resume/cover before submission
          3. Try to apply via company careers page (preferred)
          4. Fall back to job board ATS if careers page unavailable
          5. Start email monitor for OTP codes

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

        # Step 2: Validate ATS keywords before submission
        keywords_valid, keyword_warning = self._validate_ats_keywords(job, resume_path, cover_path)
        if not keywords_valid:
            print(keyword_warning)
            # Log warning but continue — let the handler decide if critical

        # Step 3: Extract company careers page URL (preferred over job board apply)
        careers_url = self._extract_company_careers_url(job)
        if careers_url:
            print(f"[auto_apply] Using company careers page: {careers_url}")
            job = {**job, "url": careers_url}  # Redirect to company site
            ats_name = "company_site"

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

    def _extract_company_careers_url(self, job: dict) -> Optional[str]:
        """
        Extract company careers page URL from job description or build candidate URL.
        Prefers company website careers page over job board Easy Apply buttons.

        Strategy:
          1. Check if job dict has careers_url or company_careers_url field
          2. Scrape job posting URL for embedded career links
          3. Guess the careers page from company domain (e.g., {company}.com/careers)

        Returns: careers URL if found, None otherwise
        """
        # Check if already provided in job dict
        careers_url = job.get("careers_url") or job.get("company_careers_url")
        if careers_url:
            return careers_url

        # Try to extract from job URL (LinkedIn, job boards often have apply links)
        job_url = job.get("url", "")
        if job_url:
            # Extract company domain from ATS and build careers URL
            try:
                from urllib.parse import urlparse
                parsed = urlparse(job_url)
                domain = parsed.netloc.replace("www.", "")

                # Common ATS domain patterns that should map to company.com/careers
                ats_domains = [
                    "lever.co", "greenhouse.io", "taleo.net",
                    "jobvite.com", "icims.com", "workday.com",
                    "ashby.craft.co", "bamboohr.com", "smartrecruiters.com"
                ]

                if any(ats in domain for ats in ats_domains):
                    company = job.get("company", "")
                    if company:
                        company_slug = company.lower().replace(" ", "-")
                        # Try canonical patterns
                        candidates = [
                            f"https://{company_slug}.com/careers",
                            f"https://www.{company_slug}.com/careers",
                            f"https://jobs.{company_slug}.com",
                        ]
                        print(f"[auto_apply] Company careers candidates: {candidates[:1]}")
                        return candidates[0]  # Return first guess; handler can validate

            except Exception as e:
                print(f"[auto_apply] Career URL extraction failed: {e}")

        return None

    def _validate_ats_keywords(self, job: dict, resume_path: Optional[Path],
                               cover_path: Optional[Path]) -> tuple[bool, str]:
        """
        Check that resume/cover letter contains critical keywords from job description.
        Uses Boolean AND/OR matching: if job requires "Python AND Django", resume must have both.

        Returns:
            (is_valid: bool, warning_msg: str) — (True, "") if all keywords present,
            (False, "msg") if critical keywords missing
        """
        job_desc = job.get("description", "").lower()
        if not job_desc or len(job_desc) < 50:
            return True, ""  # Skip validation if no description

        # Extract resume/cover text
        resume_text = ""
        cover_text = ""

        if resume_path and Path(resume_path).exists():
            resume_text = self._extract_text(resume_path).lower()

        if cover_path and Path(cover_path).exists():
            cover_text = self._extract_text(cover_path).lower()

        combined_text = (resume_text + " " + cover_text).lower()

        # Extract critical keywords from job description (look for tech skills, tools)
        # Simple heuristic: words with 3+ chars followed by numbers or common tech suffixes
        tech_pattern = r'\b([a-z]{3,}(?:\+\+|js|py|net|\.js|\.py)?)\b'
        mentioned_keywords = set(re.findall(tech_pattern, job_desc))

        # Filter to most relevant (top 10 most frequent in job desc)
        keyword_freq = {}
        for kw in mentioned_keywords:
            keyword_freq[kw] = job_desc.count(kw)
        top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = [kw for kw, _ in top_keywords]

        if not top_keywords:
            return True, ""  # No keywords detected

        # Check which keywords are missing from resume/cover
        missing_keywords = []
        for kw in top_keywords:
            if kw not in combined_text:
                missing_keywords.append(kw)

        # Warn if 50%+ of top keywords are missing (potential ATS filter risk)
        missing_pct = len(missing_keywords) / len(top_keywords) if top_keywords else 0

        if missing_pct > 0.5:
            warning = (
                f"[auto_apply] ATS keyword warning: {missing_pct:.0%} of critical keywords missing "
                f"(missing: {', '.join(missing_keywords[:5])}). "
                f"This may reduce ATS matching. Consider updating resume before apply."
            )
            print(warning)
            return False, warning

        return True, ""

    def _extract_text(self, path: Path) -> str:
        """Extract text from .docx, .pdf, or .txt file."""
        try:
            path = Path(path)
            if path.suffix == ".docx":
                try:
                    from docx import Document
                    doc = Document(str(path))
                    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                except ImportError:
                    return ""
            elif path.suffix == ".pdf":
                try:
                    import PyPDF2
                    with open(path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        return "\n".join(page.extract_text() for page in reader.pages)
                except ImportError:
                    return ""
            elif path.suffix == ".txt":
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"[auto_apply] Text extraction failed for {path}: {e}")
        return ""
