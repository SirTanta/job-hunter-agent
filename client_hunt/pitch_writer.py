"""
client_hunt/pitch_writer.py — Cold outreach email generator.

Uses Claude Sonnet to write personalized cold emails for Jon Edwards
based on company buy signals. 3 short paragraphs, 150 words max.
"""

import os
import re
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

SONNET_MODEL = "claude-sonnet-4-6"

JON_PROFILE = """- Title: AI Enablement Consultant & Instructional Designer
- Company: Tanta Holdings LLC
- Background: 15+ years L&D, federal/defense/healthcare/energy sectors
- Key clients: SAIC (FAA modernization), Cox Communications (Sales Academy), DoE (3,000+ hrs compliance eLearning), SCE, Northrop Grumman
- Specialty: AI enablement curriculum, LMS buildouts, workforce upskilling
- Education: M.Ed Learning & Technology (WGU), Navy veteran"""

PITCH_PROMPT = """You are writing a cold outreach email for Jon Edwards, founder of Tanta Holdings LLC.

JON'S PROFILE:
{profile}

TARGET COMPANY: {company_name}
SIGNAL THAT TRIGGERED THIS: {signal_type} — {signal_text}
ADDITIONAL CONTEXT: {research_summary}

Write exactly 3 short paragraphs. No subject line in body. No signature block.

P1 (2-3 sentences): Lead with their specific signal — name what's happening at their company. Frame it as a gap or challenge. Do NOT start with "I" or "We".
P2 (3 sentences): One specific Tanta deliverable that maps to their situation. Reference one proof point from Jon's background.
P3 (1 sentence): Low-commitment CTA — ask for 15 minutes.

150 words max. Plain text only. No em-dashes.

Then on a new line write: SUBJECT: [subject line under 60 chars that references their specific situation]"""


class PitchWriter:
    """
    Generates personalized cold outreach emails using Claude Sonnet.
    Falls back to a template pitch if Claude is unavailable.
    """

    def __init__(self):
        import anthropic
        claude_key = os.environ.get("ANTHROPIC_API_KEY")
        self.claude = anthropic.Anthropic(api_key=claude_key) if claude_key else None

    def write(self, lead: dict, research_summary: str = "") -> dict:
        """
        Generate a cold outreach pitch for a lead.

        Args:
            lead: lead dict from LeadFinder
            research_summary: Exa snippet about the company

        Returns:
            {subject, body, company_name, signal_type}
        """
        if not self.claude:
            return self._build_fallback_pitch(lead)

        prompt = PITCH_PROMPT.format(
            profile=JON_PROFILE,
            company_name=lead.get("company_name", "your company"),
            signal_type=lead.get("signal_type", ""),
            signal_text=lead.get("signal_text", "")[:300],
            research_summary=(research_summary or "")[:500],
        )

        try:
            msg = self.claude.messages.create(
                model=SONNET_MODEL,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            return self._parse_pitch(raw, lead)
        except Exception as e:
            print(f"[pitch_writer] Claude failed ({e}) — using fallback")
            return self._build_fallback_pitch(lead)

    def _parse_pitch(self, raw: str, lead: dict) -> dict:
        """Extract body and subject from Claude's output."""
        subject = ""
        body_lines = []

        for line in raw.splitlines():
            if line.upper().startswith("SUBJECT:"):
                subject = line.split(":", 1)[1].strip()
            else:
                body_lines.append(line)

        body = "\n".join(body_lines).strip()
        # Clean any stray em-dashes Claude may slip in
        body = body.replace("—", "-").replace("–", "-")

        if not subject:
            subject = f"AI enablement for {lead.get('company_name', 'your team')}"

        return {
            "subject":      subject[:80],
            "body":         body,
            "company_name": lead.get("company_name", ""),
            "signal_type":  lead.get("signal_type", ""),
        }

    def _build_fallback_pitch(self, lead: dict) -> dict:
        """Generic pitch when Claude is unavailable."""
        company = lead.get("company_name", "your organization")
        signal_type = lead.get("signal_type", "ai_initiative")

        signal_map = {
            "ai_initiative": "AI enablement initiative",
            "hiring_ld":     "L&D leadership search",
            "funding":       "recent funding round",
            "lms_migration": "learning platform migration",
        }
        signal_label = signal_map.get(signal_type, "growth signal")

        body = (
            f"{company}'s {signal_label} signals a real shift in how your workforce learns and adapts. "
            f"Companies at this stage often find their L&D infrastructure hasn't kept pace.\n\n"
            f"Tanta Holdings builds AI enablement curricula and LMS architectures for organizations "
            f"moving at exactly this speed. We delivered 3,000+ hours of compliance eLearning for the "
            f"DoE and built Cox Communications' Sales Academy from scratch.\n\n"
            f"Would you have 15 minutes this week to explore if there's a fit?"
        )

        return {
            "subject":      f"AI enablement support for {company}",
            "body":         body,
            "company_name": company,
            "signal_type":  signal_type,
        }
