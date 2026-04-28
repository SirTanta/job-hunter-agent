"""
tools/ats/base.py — Base ATS handler with Claude-powered field answering.

Every ATS handler inherits from BaseATSHandler. The base class provides:
  - Claude-powered screening question answering
  - Standard form field filling (name, email, phone, location)
  - Resume upload
  - Submit loop
  - Result dict construction

Subclasses override only what's different for their ATS.
"""

import os
import re
import time
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

from config import CANDIDATE_PROFILE

HAIKU_MODEL = "claude-haiku-4-5-20251001"


class BaseATSHandler:
    """
    Base class for all ATS handlers.

    Subclasses should override:
      - apply(page, job, resume_path, cover_path) — main entry point
      - _find_apply_button(page) — locate the initial apply button
      - _fill_form(page, resume_path, cover_path) — ATS-specific field filling
    """

    def __init__(self, tracker=None):
        self.tracker = tracker
        self.profile = CANDIDATE_PROFILE
        claude_key = os.environ.get("ANTHROPIC_API_KEY")
        self.claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

    # ------------------------------------------------------------------
    # Public entry point (called by AutoApplier)
    # ------------------------------------------------------------------

    def submit(self, page, job: dict, resume_path: Optional[Path],
               cover_path: Optional[Path]) -> dict:
        """
        Attempt to submit an application on the given page.
        Subclasses should call super().submit() or implement their own.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Claude-powered screening question answerer
    # ------------------------------------------------------------------

    def answer_question(self, question: str, field_type: str = "text",
                        options: list = None) -> str:
        """
        Use Claude Haiku to answer a screening question based on Jon's profile.

        Args:
            question   : the question text
            field_type : "text" | "textarea" | "select" | "radio" | "checkbox" | "yes_no"
            options    : list of option strings for select/radio fields

        Returns:
            The best answer as a string.
        """
        if not self.claude:
            return self._fallback_answer(question, field_type, options)

        profile_summary = self._build_profile_summary()
        options_str = f"\nAvailable options: {options}" if options else ""

        prompt = f"""You are filling out a job application for {self.profile['name']}.

CANDIDATE PROFILE:
{profile_summary}

QUESTION: {question}
FIELD TYPE: {field_type}{options_str}

Rules:
- Answer truthfully based only on the profile above
- For yes/no questions: answer "Yes" or "No"
- For select/radio: return EXACTLY one of the available options (copy it verbatim)
- For numeric fields (years of experience, salary): return just the number
- For text/textarea: 1-3 sentences max, professional tone, no em-dashes
- For "authorized to work" / "sponsorship" type questions: answer "Yes" (US citizen/resident)
- For salary questions: use 120000 as default unless the question specifies a range
- Never fabricate skills or experience not in the profile

Return ONLY the answer — no explanation, no labels, no punctuation wrapper."""

        try:
            msg = self.claude.messages.create(
                model=HAIKU_MODEL,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            print(f"[ats/base] Claude answer failed ({e}) — using fallback")
            return self._fallback_answer(question, field_type, options)

    def _fallback_answer(self, question: str, field_type: str,
                         options: list = None) -> str:
        """Rule-based fallback when Claude is unavailable."""
        q = question.lower()

        if field_type == "yes_no" or "yes/no" in q:
            if any(w in q for w in ("authorized", "eligible", "legally", "citizen", "right to work")):
                return "Yes"
            if any(w in q for w in ("require sponsor", "need sponsor", "visa sponsor")):
                return "No"
            if any(w in q for w in ("willing to relocate", "open to relocation")):
                return "No"
            if any(w in q for w in ("remote", "work from home", "work remotely")):
                return "Yes"
            return "Yes"

        if field_type in ("select", "radio") and options:
            # Pick the most senior / "yes" / "remote" option
            for pref in ("remote", "yes", "senior", "hybrid", "full-time", "bachelor"):
                for opt in options:
                    if pref in opt.lower():
                        return opt
            return options[0]

        if "years" in q and "experience" in q:
            return "10"

        if "salary" in q or "compensation" in q or "pay" in q:
            return "120000"

        if "cover letter" in q:
            return (
                f"I am excited to apply for this role. With 15+ years in instructional "
                f"design and AI enablement, I bring a rare combination of enterprise L&D "
                f"expertise and hands-on AI implementation that directly aligns with this "
                f"position's requirements."
            )

        return self.profile.get("summary", "")[:300]

    def _build_profile_summary(self) -> str:
        p = self.profile
        skills_flat = []
        for group in p.get("skills", {}).values():
            skills_flat.extend(group)

        exp_lines = []
        for e in p.get("experience", [])[:3]:
            exp_lines.append(f"- {e['role']} at {e['company']} ({e['duration']})")

        return (
            f"Name: {p.get('name')}\n"
            f"Location: {p.get('location')}\n"
            f"Email: {p.get('email')}\n"
            f"Phone: {p.get('phone')}\n"
            f"LinkedIn: {p.get('linkedin')}\n"
            f"Summary: {p.get('summary', '')}\n"
            f"Skills: {', '.join(skills_flat[:20])}\n"
            f"Experience:\n" + "\n".join(exp_lines) + "\n"
            f"Education: M.Ed Learning & Technology (WGU 2022), "
            f"B.S. Technology & Training (UNM 2012)\n"
            f"Veteran: Yes (US Navy, 17 years)\n"
            f"Work authorization: US citizen, no sponsorship needed\n"
            f"Preferred work mode: Remote or Hybrid\n"
        )

    # ------------------------------------------------------------------
    # Common form filling helpers
    # ------------------------------------------------------------------

    def fill_standard_fields(self, page) -> None:
        """Fill name, email, phone, location fields common to all ATS."""
        p = self.profile
        _fill_if_present(page, [
            "input[name*='firstName' i], input[id*='firstName' i], "
            "input[placeholder*='First name' i], input[aria-label*='First name' i]",
        ], p.get("name", "").split()[0])

        _fill_if_present(page, [
            "input[name*='lastName' i], input[id*='lastName' i], "
            "input[placeholder*='Last name' i], input[aria-label*='Last name' i]",
        ], p.get("name", "").split()[-1])

        _fill_if_present(page, [
            "input[name*='email' i], input[id*='email' i], "
            "input[type='email'], input[placeholder*='email' i]",
        ], p.get("email", ""))

        _fill_if_present(page, [
            "input[name*='phone' i], input[id*='phone' i], "
            "input[type='tel'], input[placeholder*='phone' i], "
            "input[aria-label*='phone' i]",
        ], p.get("phone", ""))

        _fill_if_present(page, [
            "input[name*='linkedin' i], input[id*='linkedin' i], "
            "input[placeholder*='linkedin' i]",
        ], f"https://{p.get('linkedin', '')}")

        _fill_if_present(page, [
            "input[name*='city' i], input[id*='city' i], "
            "input[placeholder*='city' i]",
        ], "Rio Rancho")

        _fill_if_present(page, [
            "input[name*='location' i], input[id*='location' i], "
            "input[placeholder*='location' i]",
        ], "Rio Rancho, NM")

    def upload_resume(self, page, resume_path: Optional[Path]) -> bool:
        """Upload resume to file input. Returns True if uploaded."""
        if not resume_path or not Path(resume_path).exists():
            return False
        upload = page.query_selector("input[type='file']")
        if upload:
            upload.set_input_files(str(resume_path))
            time.sleep(1)
            print(f"[ats] Resume uploaded: {resume_path.name if hasattr(resume_path, 'name') else resume_path}")
            return True
        return False

    def fill_cover_letter(self, page, cover_path: Optional[Path]) -> bool:
        """Paste cover letter text into textarea if present."""
        if not cover_path or not Path(cover_path).exists():
            return False
        cover_text = _docx_to_text(cover_path)
        if not cover_text:
            return False
        area = page.query_selector(
            "textarea[id*='cover' i], textarea[name*='cover' i], "
            "textarea[placeholder*='cover' i], "
            "div[aria-label*='cover letter' i] textarea"
        )
        if area:
            area.fill(cover_text[:3000])
            return True
        return False

    def answer_all_visible_questions(self, page) -> None:
        """
        Scan for visible question fields and answer them with Claude.
        Handles text inputs, textareas, selects, and radio groups.
        """
        # Text inputs that look like questions (have a label)
        labels = page.query_selector_all("label")
        for label in labels:
            label_text = label.inner_text().strip()
            if len(label_text) < 5:
                continue

            # Find the associated input
            for_attr = label.get_attribute("for")
            if for_attr:
                field = page.query_selector(f"#{for_attr}")
            else:
                field = label.query_selector("input, textarea, select")

            if not field:
                continue

            tag = field.evaluate("el => el.tagName.toLowerCase()")
            field_type = field.get_attribute("type") or tag

            # Skip fields already filled
            current_val = field.input_value() if tag in ("input", "textarea") else ""
            if current_val and len(current_val) > 2:
                continue

            # Skip hidden / submit / file fields
            if field_type in ("hidden", "submit", "file", "button"):
                continue

            if tag == "select":
                options = [o.inner_text() for o in field.query_selector_all("option") if o.inner_text().strip()]
                answer = self.answer_question(label_text, "select", options)
                try:
                    field.select_option(label=answer)
                except Exception:
                    try:
                        field.select_option(value=answer)
                    except Exception:
                        pass
            elif tag == "textarea":
                answer = self.answer_question(label_text, "textarea")
                field.fill(answer)
            elif field_type in ("text", "number", "email", "tel", "url"):
                # Only fill if it looks like a question (has question mark or is long)
                if "?" in label_text or len(label_text) > 20:
                    answer = self.answer_question(label_text, "text")
                    field.fill(answer)

        time.sleep(0.5)

    # ------------------------------------------------------------------
    # Standard submit loop
    # ------------------------------------------------------------------

    def submit_loop(self, page, max_steps: int = 10) -> bool:
        """
        Click through Next/Review/Submit buttons until submitted.
        Returns True on confirmed submission.
        """
        SUBMIT_SELECTORS = [
            "button[type='submit']:has-text('Submit')",
            "button:has-text('Submit application')",
            "button:has-text('Submit Application')",
            "button[aria-label*='Submit' i]",
            "input[type='submit']",
        ]
        NEXT_SELECTORS = [
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "button:has-text('Review')",
            "button[aria-label*='Next' i]",
            "button[aria-label*='Continue' i]",
        ]
        CONFIRM_SELECTORS = [
            ":has-text('Application submitted')",
            ":has-text('application was sent')",
            ":has-text('successfully submitted')",
            ":has-text('Thank you for applying')",
            ":has-text('We received your application')",
        ]

        for step in range(max_steps):
            time.sleep(1.5)

            # Answer any new questions that appeared
            try:
                self.answer_all_visible_questions(page)
            except Exception:
                pass

            # Check for success confirmation
            for sel in CONFIRM_SELECTORS:
                try:
                    if page.query_selector(sel):
                        print(f"[ats] Submission confirmed at step {step+1}")
                        return True
                except Exception:
                    pass

            # Try submit
            for sel in SUBMIT_SELECTORS:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    time.sleep(2)
                    return True

            # Try next/continue
            advanced = False
            for sel in NEXT_SELECTORS:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    time.sleep(1)
                    advanced = True
                    break

            if not advanced:
                print(f"[ats] No button found at step {step+1}")
                break

        return False

    # ------------------------------------------------------------------
    # Result dict builders
    # ------------------------------------------------------------------

    def _success(self, method: str, url: str) -> dict:
        return {"success": True, "method": method, "message": f"Submitted via {method}", "job_url": url}

    def _manual(self, url: str, reason: str = "") -> dict:
        msg = "Manual review needed"
        if reason:
            msg += f": {reason}"
        return {"success": False, "method": "manual", "message": msg, "job_url": url}


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _fill_if_present(page, selectors: list, value: str) -> bool:
    """Try each selector in turn, fill the first match. Returns True if filled."""
    if not value:
        return False
    for sel in selectors:
        try:
            field = page.query_selector(sel)
            if field and field.is_visible():
                existing = field.input_value()
                if not existing or len(existing) < 2:
                    field.fill(value)
                    return True
        except Exception:
            continue
    return False


def _docx_to_text(path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""
