"""
tools/ats/lever.py — Lever ATS handler.

Lever uses a consistent single-page application form at jobs.lever.co/{company}/{id}.
No login required. Standard fields + resume upload + optional cover letter.
"""

import time
from pathlib import Path
from typing import Optional

from tools.ats.base import BaseATSHandler


class LeverHandler(BaseATSHandler):

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[lever] Applying at {url}")

        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(2)

            # Bail on stale/404 listings
            title = page.title().lower()
            body_text = page.evaluate("() => document.body.innerText.substring(0, 300)").lower()
            if any(x in title + body_text for x in [
                "404", "not found", "no longer available", "position has been filled",
                "job has been closed", "no longer accepting",
            ]):
                return self._manual(url, "Lever: job posting is no longer active")

            # Lever shows the form inline — no "Apply" button needed on most postings
            # But some have a modal trigger
            apply_btn = page.query_selector(
                "a.postings-btn:has-text('Apply'), "
                "a[data-qa='btn-apply-modal'], "
                "a:has-text('Apply for this job'), "
                "button:has-text('Apply for this job'), "
                "a:has-text('Apply Now'), "
                "button:has-text('Apply Now')"
            )
            if apply_btn and apply_btn.is_visible():
                apply_btn.click()
                time.sleep(1.5)

            # Fill standard fields
            self.fill_standard_fields(page)

            # Resume upload
            self.upload_resume(page, resume_path)

            # Cover letter textarea (Lever has a dedicated field)
            cl_area = page.query_selector(
                "textarea[name='comments'], "
                "textarea[placeholder*='cover letter' i], "
                "textarea[id*='cover' i], "
                "textarea[name*='cover' i]"
            )
            if cl_area and cover_path:
                from tools.ats.base import _docx_to_text
                text = _docx_to_text(cover_path)
                if text:
                    cl_area.fill(text[:3000])

            # Answer any additional questions
            self.answer_all_visible_questions(page)

            # Use submit_loop (handles CAPTCHA + email verification too)
            submitted = self.submit_loop(page)
            if submitted:
                return self._success("lever", url)

            # Fallback: try direct submit button click + confirm
            submit_btn = page.query_selector(
                "button[type='submit'], "
                "button:has-text('Submit application'), "
                "button:has-text('Submit Application'), "
                "button:has-text('Submit'), "
                "input[type='submit']"
            )
            if submit_btn and submit_btn.is_visible():
                submit_btn.click()
                time.sleep(3)

                if self._is_success_page(page):
                    return self._success("lever", url)

            return self._manual(url, "Submit confirmation not detected")

        except Exception as e:
            print(f"[lever] Error: {e}")
            return self._manual(url, str(e))

    def _is_success_page(self, page) -> bool:
        """Broad check for Lever success signals."""
        try:
            url_lower = page.url.lower()
            if any(x in url_lower for x in ["confirmation", "thank", "success", "submitted", "complete"]):
                return True

            # DOM signals
            selectors = [
                "h1:has-text('Thank')", "h2:has-text('Thank')",
                "h1:has-text('Application submitted')", "h2:has-text('Application submitted')",
                "h1:has-text('Application received')", "h2:has-text('Application received')",
                "div.thanks", ".thanks-message", ".confirmation-message",
                "[data-qa='confirmation']", ".application-confirmation",
                "p:has-text('successfully submitted')", "p:has-text('We\\'ll be in touch')",
                "p:has-text('Thank you for applying')",
            ]
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        return True
                except Exception:
                    continue

            # Body text fallback
            body = page.evaluate("() => document.body.innerText.substring(0, 600)").lower()
            if any(x in body for x in [
                "thank you for applying", "application submitted", "application received",
                "we'll be in touch", "we received your application", "application was submitted",
                "successfully applied",
            ]):
                return True

        except Exception:
            pass
        return False
