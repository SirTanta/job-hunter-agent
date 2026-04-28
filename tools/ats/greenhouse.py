"""
tools/ats/greenhouse.py — Greenhouse ATS handler.

Greenhouse job boards at boards.greenhouse.io/{company}/jobs/{id}.
Form is single-page with file upload + custom questions.
"""

import time
from pathlib import Path
from typing import Optional

from tools.ats.base import BaseATSHandler, _fill_if_present


class GreenhouseHandler(BaseATSHandler):

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[greenhouse] Applying at {url}")

        try:
            page.goto(url, timeout=20000)
            time.sleep(2)

            # Some Greenhouse boards have an "Apply for this Job" button
            apply_btn = page.query_selector(
                "a#apply_button, "
                "a:has-text('Apply for this Job'), "
                "button:has-text('Apply')"
            )
            if apply_btn:
                apply_btn.click()
                time.sleep(1.5)

            # Standard contact fields
            self.fill_standard_fields(page)

            # Greenhouse resume upload — may have both file input and paste-in textarea
            resume_uploaded = self.upload_resume(page, resume_path)

            # If no file input, use the resume textarea
            if not resume_uploaded and resume_path:
                from tools.ats.base import _docx_to_text
                text = _docx_to_text(resume_path)
                resume_area = page.query_selector(
                    "textarea#resume_text, textarea[name*='resume' i]"
                )
                if resume_area and text:
                    resume_area.fill(text[:5000])

            # Cover letter
            self.fill_cover_letter(page, cover_path)

            # Greenhouse custom questions (ul.custom-fields)
            self._answer_greenhouse_questions(page)

            # Submit
            submit_btn = page.query_selector(
                "input#submit_app, "
                "input[type='submit'][value*='Submit' i], "
                "button[type='submit']"
            )
            if submit_btn:
                submit_btn.click()
                time.sleep(3)

                # Greenhouse success page
                if page.query_selector(
                    "p:has-text('application has been submitted'), "
                    "h1:has-text('Thank you'), "
                    ".application-confirmation"
                ):
                    return self._success("greenhouse", url)

            return self._manual(url, "Submit confirmation not detected")

        except Exception as e:
            print(f"[greenhouse] Error: {e}")
            return self._manual(url, str(e))

    def _answer_greenhouse_questions(self, page) -> None:
        """
        Greenhouse custom questions are rendered in a consistent pattern:
        <li class="custom-field"> <label> <input/select/textarea> </li>
        """
        question_items = page.query_selector_all(
            "li.custom-field, div.field, div.question"
        )
        for item in question_items:
            label_el = item.query_selector("label")
            if not label_el:
                continue
            question_text = label_el.inner_text().strip()
            if not question_text:
                continue

            field = item.query_selector("input, textarea, select")
            if not field:
                continue

            tag = field.evaluate("el => el.tagName.toLowerCase()")
            field_type = field.get_attribute("type") or tag

            if field_type in ("hidden", "submit", "file"):
                continue

            current = field.input_value() if tag in ("input", "textarea") else ""
            if current and len(current) > 2:
                continue

            if tag == "select":
                options = [o.inner_text() for o in field.query_selector_all("option")
                           if o.inner_text().strip() and o.get_attribute("value")]
                if options:
                    answer = self.answer_question(question_text, "select", options)
                    try:
                        field.select_option(label=answer)
                    except Exception:
                        pass
            elif tag == "textarea":
                answer = self.answer_question(question_text, "textarea")
                field.fill(answer)
            else:
                answer = self.answer_question(question_text, "text")
                field.fill(answer)
