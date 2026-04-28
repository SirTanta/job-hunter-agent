"""
client_hunt_agent.py — Client hunt orchestrator.

Finds companies showing buy signals for AI enablement / L&D consulting,
generates personalized pitches, saves to Notion, and optionally writes
Gmail draft files.

Usage:
    python client_hunt_agent.py --dry-run        # find leads, no Notion writes
    python client_hunt_agent.py --max 10         # process 10 new leads, save to Notion
    python client_hunt_agent.py --max 10 --drafts # also write draft files
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from client_hunt.lead_finder import LeadFinder
from client_hunt.pitch_writer import PitchWriter
from client_hunt.notion_leads import NotionLeadsTracker


class ClientHuntAgent:

    def __init__(self, dry_run: bool = False, max_leads: int = 10,
                 create_drafts: bool = False):
        self.dry_run       = dry_run
        self.max_leads     = max_leads
        self.create_drafts = create_drafts

        self.lead_finder = LeadFinder()
        self.pitch_writer = PitchWriter()
        self.notion = NotionLeadsTracker() if not dry_run else None

        # Ensure output/drafts dir exists
        Path("output/drafts").mkdir(parents=True, exist_ok=True)

    def run(self) -> dict:
        """
        Main flow:
          1. Find raw leads
          2. Filter out leads already in Notion
          3. For each new lead: research + pitch + save + (optional) draft
          4. Return summary
        """
        print(f"\n[client_hunt] Starting — dry_run={self.dry_run}, max={self.max_leads}")

        # Step 1: find leads
        all_leads = self.lead_finder.search()
        if not all_leads:
            print("[client_hunt] No leads found")
            return {"found": 0, "processed": 0, "drafted": 0}

        # Step 2: filter out leads already in Notion
        new_leads = []
        if self.notion and not self.dry_run:
            for lead in all_leads:
                domain = lead.get("domain", "")
                if domain and not self.notion.find_by_domain(domain):
                    new_leads.append(lead)
            print(f"[client_hunt] {len(all_leads)} found, {len(new_leads)} new (not in Notion)")
        else:
            new_leads = all_leads
            print(f"[client_hunt] {len(all_leads)} leads (dry run — skipping Notion dedup)")

        # Limit to max_leads
        new_leads = new_leads[:self.max_leads]

        stats = {"found": len(all_leads), "processed": 0, "drafted": 0, "errors": 0}

        # Step 3: process each lead
        for lead in new_leads:
            company = lead.get("company_name", "Unknown")
            print(f"\n[client_hunt] Processing: {company} ({lead.get('signal_type')}, score={lead.get('buy_signal_score')})")

            try:
                # Research the company
                research = self._quick_research(lead)

                # Generate pitch
                pitch = self.pitch_writer.write(lead, research)
                print(f"  Subject: {pitch.get('subject')}")

                if not self.dry_run and self.notion:
                    # Save to Notion
                    page_id = self.notion.upsert_lead(lead, pitch)
                    if page_id:
                        stats["processed"] += 1

                        # Create draft file if requested
                        if self.create_drafts:
                            drafted = self._write_draft_file(lead, pitch)
                            if drafted:
                                stats["drafted"] += 1
                    else:
                        stats["errors"] += 1
                else:
                    # Dry run: print the pitch
                    print(f"\n--- PITCH for {company} ---")
                    print(f"Subject: {pitch.get('subject')}\n")
                    print(pitch.get("body", ""))
                    print("---")
                    stats["processed"] += 1

                    if self.create_drafts:
                        drafted = self._write_draft_file(lead, pitch)
                        if drafted:
                            stats["drafted"] += 1

            except Exception as e:
                print(f"[client_hunt] Error processing {company}: {e}")
                stats["errors"] += 1

        print(f"\n[client_hunt] Done: {stats}")
        return stats

    def _quick_research(self, lead: dict) -> str:
        """
        Single Exa call for company context (500 char highlights).
        Returns a brief research summary string.
        """
        company = lead.get("company_name", "")
        if not company or company == "Unknown Company":
            return ""

        try:
            res = self.lead_finder.exa.search_and_contents(
                f"{company} company overview culture technology",
                num_results=3,
                highlights={"max_characters": 500},
            )
            parts = []
            for r in res.results:
                if r.highlights:
                    parts.append(r.highlights[0])
            return " ".join(parts)[:1000]
        except Exception as e:
            print(f"[client_hunt] Research failed for {company}: {e}")
            return ""

    def _write_draft_file(self, lead: dict, pitch: dict) -> bool:
        """Write pitch to output/drafts/{company}_{date}.txt"""
        try:
            company_slug = lead.get("company_name", "unknown").lower()
            company_slug = "".join(c if c.isalnum() else "_" for c in company_slug)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filename = f"output/drafts/{company_slug}_{today}.txt"

            content = (
                f"TO: [find contact at {lead.get('company_name', '')}]\n"
                f"FROM: jedwards@tanta-holdings.com\n"
                f"SUBJECT: {pitch.get('subject', '')}\n"
                f"SIGNAL: {lead.get('signal_type', '')} | {lead.get('signal_url', '')}\n"
                f"\n"
                f"{pitch.get('body', '')}\n"
                f"\n"
                f"--\n"
                f"Jon Edwards\n"
                f"AI Enablement Consultant | Tanta Holdings LLC\n"
                f"jedwards@tanta-holdings.com\n"
            )

            Path(filename).write_text(content, encoding="utf-8")
            print(f"  Draft saved: {filename}")
            return True
        except Exception as e:
            print(f"[client_hunt] Draft write failed: {e}")
            return False


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Client Hunt Agent — find and pitch AI enablement leads")
    parser.add_argument("--dry-run",  action="store_true", help="Find leads, print pitches, no Notion writes")
    parser.add_argument("--max",      type=int, default=10, help="Max new leads to process (default 10)")
    parser.add_argument("--drafts",   action="store_true", help="Write pitch drafts to output/drafts/")
    args = parser.parse_args()

    agent = ClientHuntAgent(
        dry_run=args.dry_run,
        max_leads=args.max,
        create_drafts=args.drafts,
    )
    result = agent.run()

    if result.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
