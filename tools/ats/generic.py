"""
tools/ats/generic.py — Claude-powered generic handler for any ATS.

For ATS systems without a dedicated handler (iCIMS, Taleo, Jobvite,
Breezy, Recruitee, Rippling, Wellfound, Workable, JazzHR, etc.),
this handler uses Claude to understand the page and fill it intelligently.

Strategy:
  1. Navigate to the job URL
  2. Find and click an Apply button if present
  3. Extract the full form HTML
  4. Let Claude identify all fields and produce fill instructions
  5. Execute the fill instructions
  6. Run the submit loop
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

from tools.ats.base import BaseATSHandler

SONNET_MODEL = "claude-sonnet-4-6"


class GenericHandler(BaseATSHandler):

    def __init__(self, ats_name: str = "generic", tracker=None):
        super().__init__(tracker=tracker)
        self.ats_name = ats_name

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        url = job.get("url", "")
        print(f"[{self.ats_name}] Generic handler for {url}")

        try:
            page.goto(url, timeout=25000)
            time.sleep(2)

            # Try to find and click an Apply button
            self._click_apply_button(page)
            time.sleep(1.5)

            # Always fill standard contact fields first
            self.fill_standard_fields(page)

            # Upload resume
            self.upload_resume(page, resume_path)

            # Cover letter
            self.fill_cover_letter(page, cover_path)

            # Use Claude to analyze the form and fill remaining fields
            self._claude_fill_form(page, job)

            # Submit loop
            submitted = self.submit_loop(page)

            if submitted:
                return self._success(self.ats_name, url)
            return self._manual(url, f"{self.ats_name}: submit flow incomplete")

        except Exception as e:
            print(f"[{self.ats_name}] Error: {e}")
            return self._manual(url, str(e))

    def _click_apply_button(self, page) -> bool:
        """Try common Apply button patterns."""
        selectors = [
            "a:has-text('Apply Now')", "a:has-text('Apply for this job')",
            "button:has-text('Apply Now')", "button:has-text('Apply')",
            "a.apply-btn", "button.apply-btn",
            "[data-qa='btn-apply']", "[id*='apply' i]",
        ]
        for sel in selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    return True
            except Exception:
                continue
        return False

    def _claude_fill_form(self, page, job: dict) -> None:
        """
        Extract form HTML, send to Claude Sonnet, get back field instructions,
        execute them.

        We use Sonnet here because understanding arbitrary form HTML requires
        more reasoning than Haiku can reliably provide.
        """
        if not self.claude:
            # Fall back to dumb question-answering
            self.answer_all_visible_questions(page)
            return

        try:
            # Extract form HTML (truncated to avoid token explosion)
            form_html = page.evaluate("""() => {
                const form = document.querySelector('form') ||
                             document.querySelector('[role="form"]') ||
                             document.querySelector('main');
                return form ? form.innerHTML.substring(0, 8000) : document.body.innerHTML.substring(0, 8000);
            }""")

            profile_summary = self._build_profile_summary()

            prompt = f"""You are filling out a job application form on behalf of a candidate.

CANDIDATE PROFILE:
{profile_summary}

JOB: {job.get('title', '')} at {job.get('company', '')}

FORM HTML (truncated):
{form_html}

Analyze this form HTML and return a JSON array of fill instructions.
Each instruction must have:
  - "selector": CSS selector to target the field (use id, name, or data attributes — be specific)
  - "action": one of "fill", "select", "check", "skip"
  - "value": the value to enter (for fill/select) or true/false (for check)
  - "field_name": human-readable field name

Rules:
- Skip fields already clearly filled (email if already has an @ sign, etc.)
- Skip file upload fields, hidden fields, CSRF tokens
- For select dropdowns, value must be the EXACT option text
- For checkboxes, only check if the question warrants it (e.g. "I agree to terms" → true, "Receive spam" → false)
- Answer truthfully based on the candidate profile
- For work authorization: "Yes" / authorized
- For sponsorship required: "No"
- Skip fields you cannot confidently answer

Return ONLY a valid JSON array, no markdown, no explanation.
Example: [{{"selector": "#firstName", "action": "fill", "value": "Jon", "field_name": "First Name"}}]"""

            msg = self.claude.messages.create(
                model=SONNET_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()

            # Strip markdown fences if present
            import re
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            instructions = json.loads(raw)
            self._execute_instructions(page, instructions)

        except json.JSONDecodeError:
            print(f"[{self.ats_name}] Claude returned invalid JSON — falling back to dumb fill")
            self.answer_all_visible_questions(page)
        except Exception as e:
            print(f"[{self.ats_name}] Claude form analysis failed ({e}) — falling back")
            self.answer_all_visible_questions(page)

    def _execute_instructions(self, page, instructions: list) -> None:
        """Execute fill instructions from Claude."""
        for inst in instructions:
            sel = inst.get("selector", "")
            action = inst.get("action", "skip")
            value = inst.get("value", "")
            field_name = inst.get("field_name", sel)

            if action == "skip" or not sel:
                continue

            try:
                field = page.query_selector(sel)
                if not field or not field.is_visible():
                    continue

                if action == "fill":
                    current = field.input_value()
                    if not current or len(current) < 2:
                        field.fill(str(value))
                        print(f"[{self.ats_name}] Filled '{field_name}': {str(value)[:40]}")

                elif action == "select":
                    try:
                        field.select_option(label=str(value))
                    except Exception:
                        field.select_option(value=str(value))
                    print(f"[{self.ats_name}] Selected '{field_name}': {value}")

                elif action == "check":
                    is_checked = field.is_checked()
                    if bool(value) and not is_checked:
                        field.check()
                    elif not bool(value) and is_checked:
                        field.uncheck()

            except Exception as e:
                print(f"[{self.ats_name}] Could not fill '{field_name}' ({sel}): {e}")

        time.sleep(0.5)
