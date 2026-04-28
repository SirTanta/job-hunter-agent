"""
client_hunt_agent.py — Client hunt orchestrator.

Finds companies showing buy signals for AI enablement / L&D consulting,
generates personalized pitches, saves to Notion, and optionally enrolls
contacts in the Apollo "Tanta Holdings - L&D AI Consulting" sequence.

Usage:
    python client_hunt_agent.py --dry-run           # find leads, no writes
    python client_hunt_agent.py --max 10            # process 10 new leads
    python client_hunt_agent.py --max 15 --apollo   # enroll leads in Apollo sequence
    python client_hunt_agent.py --max 10 --drafts   # also write draft files
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

    def __init__(
        self,
        dry_run:       bool = False,
        max_leads:     int  = 10,
        create_drafts: bool = False,
        use_apollo:    bool = False,
    ):
        self.dry_run       = dry_run
        self.max_leads     = max_leads
        self.create_drafts = create_drafts
        self.use_apollo    = use_apollo

        self.lead_finder  = LeadFinder()
        self.pitch_writer = PitchWriter()
        self.notion       = NotionLeadsTracker() if not dry_run else None

        # Apollo sender — only instantiate if requested
        self.apollo = None
        if use_apollo:
            from client_hunt.apollo_sender import ApolloSender
            self.apollo       = ApolloSender()
            self.sequence_id  = self.apollo.create_sequence_if_missing()
            if not self.sequence_id:
                print("[client_hunt] Warning: could not get Apollo sequence ID — Apollo disabled")
                self.apollo = None

        # Ensure output/drafts dir exists
        Path("output/drafts").mkdir(parents=True, exist_ok=True)

    def run(self) -> dict:
        """
        Main flow:
          1. Find raw leads
          2. Filter out leads already in Notion
          3. For each new lead:
             a. _quick_research(lead)
             b. pitch_writer.write(lead, research)
             c. notion_leads.upsert_lead(lead, pitch)
             d. If --apollo: find_or_create_contact + enroll_in_sequence
          4. apollo.bulk_update_notion_from_apollo — sync reply signals
          5. Print summary with links
        """
        print(f"\n[client_hunt] Starting — dry_run={self.dry_run}, max={self.max_leads}, apollo={self.use_apollo}")

        # Step 1: find leads
        all_leads = self.lead_finder.search()
        if not all_leads:
            print("[client_hunt] No leads found")
            return {"found": 0, "processed": 0, "enrolled": 0, "drafted": 0, "errors": 0}

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

        stats = {
            "found":     len(all_leads),
            "processed": 0,
            "enrolled":  0,
            "drafted":   0,
            "errors":    0,
        }

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Step 3: process each lead
        for lead in new_leads:
            company = lead.get("company_name", "Unknown")
            domain  = lead.get("domain", "")
            print(f"\n[client_hunt] Processing: {company} ({lead.get('signal_type')}, score={lead.get('buy_signal_score')})")

            try:
                # 3a. Research the company
                research = self._quick_research(lead)

                # 3b. Generate pitch
                pitch = self.pitch_writer.write(lead, research)
                print(f"  Subject: {pitch.get('subject')}")

                if self.dry_run:
                    print(f"\n--- PITCH for {company} ---")
                    print(f"Subject: {pitch.get('subject')}\n")
                    print(pitch.get("body", ""))
                    print("---")
                    stats["processed"] += 1

                    if self.create_drafts:
                        if self._write_draft_file(lead, pitch):
                            stats["drafted"] += 1
                    continue

                if not self.notion:
                    stats["errors"] += 1
                    continue

                # 3c. Save to Notion
                page_id = self.notion.upsert_lead(lead, pitch)
                if not page_id:
                    print(f"  [client_hunt] Notion upsert failed for {company}")
                    stats["errors"] += 1
                    continue

                stats["processed"] += 1

                # 3d. Apollo: find/create contact and enroll in sequence
                if self.apollo and domain:
                    contact = self.apollo.find_or_create_contact(
                        company_name=company,
                        domain=domain,
                    )

                    if contact:
                        contact_id = contact.get("id", "")
                        enrolled   = self.apollo.enroll_in_sequence(
                            contact_id=contact_id,
                            sequence_id=self.sequence_id,
                            pitch=pitch,
                        )
                        if enrolled:
                            stats["enrolled"] += 1
                            # Update Notion with Apollo contact ID as reference
                            # (stored in "Gmail Draft ID" field — labeled Apollo Contact ID in practice)
                            self.notion.update_after_pitch(
                                domain=domain,
                                draft_id=contact_id,
                                pitch_date=today,
                            )
                            print(f"  Apollo enrolled: {contact_id}")
                    else:
                        print(f"  [apollo] Could not create/find contact for {company}")

                # Write draft file if requested
                if self.create_drafts:
                    if self._write_draft_file(lead, pitch):
                        stats["drafted"] += 1

            except Exception as e:
                print(f"[client_hunt] Error processing {company}: {e}")
                stats["errors"] += 1

        # Step 4: sync Apollo reply signals back to Notion
        if self.apollo and self.notion and not self.dry_run:
            synced = self.apollo.bulk_update_notion_from_apollo(self.notion)
            print(f"[client_hunt] Apollo reply sync: {synced} Notion rows updated")

        print(f"\n[client_hunt] Done: {stats}")
        self._print_summary(stats)
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
            today        = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filename     = f"output/drafts/{company_slug}_{today}.txt"

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

    def _print_summary(self, stats: dict) -> None:
        """Print a clean run summary."""
        print("\n" + "=" * 50)
        print("CLIENT HUNT SUMMARY")
        print("=" * 50)
        print(f"  Leads found:     {stats['found']}")
        print(f"  Processed:       {stats['processed']}")
        if self.use_apollo:
            print(f"  Apollo enrolled: {stats['enrolled']}")
        if self.create_drafts:
            print(f"  Drafts written:  {stats['drafted']}")
        print(f"  Errors:          {stats['errors']}")
        print("=" * 50)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Client Hunt Agent - find and pitch AI enablement leads"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Find leads, print pitches, no Notion or Apollo writes",
    )
    parser.add_argument(
        "--max", type=int, default=10,
        help="Max new leads to process (default 10)",
    )
    parser.add_argument(
        "--drafts", action="store_true",
        help="Write pitch drafts to output/drafts/",
    )
    parser.add_argument(
        "--apollo", action="store_true",
        help="Enroll leads in Apollo sequence (Tanta Holdings - L&D AI Consulting)",
    )
    args = parser.parse_args()

    agent = ClientHuntAgent(
        dry_run=args.dry_run,
        max_leads=args.max,
        create_drafts=args.drafts,
        use_apollo=args.apollo,
    )
    result = agent.run()

    if result.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
