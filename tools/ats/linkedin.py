"""
tools/ats/linkedin.py — LinkedIn Easy Apply handler (moved from auto_apply.py).
"""
import os
import time
from pathlib import Path
from typing import Optional
from tools.ats.base import BaseATSHandler, _docx_to_text


class LinkedInHandler(BaseATSHandler):

    def submit(self, page, job: dict, cv_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        li_at = os.environ.get("LINKEDIN_LI_AT", "")
        if not li_at:
            return self._manual(url, "No LINKEDIN_LI_AT cookie")

        print(f"[linkedin] Applying at {url}")
        try:
            page.context.add_cookies([{
                "name": "li_at", "value": li_at,
                "domain": ".linkedin.com", "path": "/",
            }])
            page.goto(url, timeout=20000)
            time.sleep(2)

            easy_apply = page.query_selector(
                "button.jobs-apply-button, "
                "button[aria-label*='Easy Apply'], "
                "button.jobs-s-apply__button"
            )
            if not easy_apply:
                return self._manual(url, "No Easy Apply button")

            easy_apply.click()
            time.sleep(1)

            self.fill_standard_fields(page)
            self.upload_resume(page, cv_path)

            if cover_path:
                cover_text = _docx_to_text(cover_path)
                if cover_text:
                    cover_area = page.query_selector(
                        "textarea[id*='coverLetter'], "
                        "textarea[placeholder*='cover letter' i]"
                    )
                    if cover_area:
                        cover_area.fill(cover_text[:3000])

            submitted = self.submit_loop(page)
            if submitted:
                return self._success("linkedin_easy_apply", url)
            return self._manual(url, "Submit loop ended without confirmation")
        except Exception as e:
            return self._manual(url, str(e))
