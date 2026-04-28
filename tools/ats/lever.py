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

    def submit(self, page, job: dict, cv_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[lever] Applying at {url}")

        try:
            page.goto(url, timeout=20000)
            time.sleep(2)

            # Lever shows the form inline — no "Apply" button needed on most postings
            # But some have a modal trigger
            apply_btn = page.query_selector(
                "a.postings-btn:has-text('Apply'), "
                "a[data-qa='btn-apply-modal'], "
                "a:has-text('Apply for this job')"
            )
            if apply_btn:
                apply_btn.click()
                time.sleep(1.5)

            # Fill standard fields
            self.fill_standard_fields(page)

            # Resume upload
            self.upload_resume(page, cv_path)

            # Cover letter textarea (Lever has a dedicated field)
            cl_area = page.query_selector(
                "textarea[name='comments'], "
                "textarea[placeholder*='cover letter' i], "
                "textarea[id*='cover' i]"
            )
            if cl_area and cover_path:
                from tools.ats.base import _docx_to_text
                text = _docx_to_text(cover_path)
                if text:
                    cl_area.fill(text[:3000])

            # Answer any additional questions
            self.answer_all_visible_questions(page)

            # Submit
            submit_btn = page.query_selector(
                "button[type='submit'], "
                "button:has-text('Submit application'), "
                "input[type='submit'][value*='Submit' i]"
            )
            if submit_btn:
                submit_btn.click()
                time.sleep(2)

                # Check for Lever's thank-you page
                if page.query_selector("h1:has-text('Thank'), div.thanks, .thanks-message"):
                    return self._success("lever", url)

                # Check URL change (Lever redirects on success)
                if "confirmation" in page.url or "thank" in page.url.lower():
                    return self._success("lever", url)

            return self._manual(url, "Submit confirmation not detected")

        except Exception as e:
            print(f"[lever] Error: {e}")
            return self._manual(url, str(e))
