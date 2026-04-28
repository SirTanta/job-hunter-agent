"""
tools/ats/ashby.py — Ashby HQ ATS handler.

Ashby is increasingly common at fast-growing startups.
URL pattern: jobs.ashbyhq.com/{company}/{uuid}
Single-page form, React-rendered, clean structure.
"""

import time
from pathlib import Path
from typing import Optional

from tools.ats.base import BaseATSHandler


class AshbyHandler(BaseATSHandler):

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[ashby] Applying at {url}")

        try:
            page.goto(url, timeout=20000)
            time.sleep(2)

            # Ashby has an "Apply" button that opens the form
            apply_btn = page.query_selector(
                "button:has-text('Apply'), "
                "a:has-text('Apply for this position'), "
                "button[data-testid='apply-button']"
            )
            if apply_btn:
                apply_btn.click()
                time.sleep(1.5)

            # Standard fields
            self.fill_standard_fields(page)

            # Resume upload
            self.upload_resume(page, resume_path)

            # Cover letter (Ashby has an optional cover letter text area)
            self.fill_cover_letter(page, cover_path)

            # Additional questions rendered as form fields
            self.answer_all_visible_questions(page)

            # Submit loop handles Ashby's multi-step forms
            submitted = self.submit_loop(page)

            if submitted:
                return self._success("ashby", url)
            return self._manual(url, "Submit flow incomplete")

        except Exception as e:
            print(f"[ashby] Error: {e}")
            return self._manual(url, str(e))
