#!/usr/bin/env python3
"""
Build Tanta Holdings Infrastructure Map in Notion.
Parent page: 34e84b11-8b54-81b3-ac6e-faa0a7a5d873 (Ops Hub)
"""

import json
import os
import urllib.request
import urllib.error

# --- Credentials ---
with open("D:/Claude/Code/job-hunter-agent/.env") as f:
    for line in f:
        if line.startswith("NOTION_TOKEN="):
            TOKEN = line.split("=", 1)[1].strip()
            break

PARENT_ID = "34e84b11-8b54-81b3-ac6e-faa0a7a5d873"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def notion_call(url, payload, method="POST"):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP {e.code} error: {body}")
        raise

def safe(s):
    """Sanitize string for Notion API - no em dashes, trim to 1900 chars."""
    if not s:
        return ""
    s = s.replace("—", " - ").replace("–", " - ").replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    return s[:1900]

# --- Block helpers ---
def h1(text):
    return {
        "object": "block",
        "type": "heading_1",
        "heading_1": {"rich_text": [{"type": "text", "text": {"content": safe(text)}}]}
    }

def h2(text):
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": safe(text)}}]}
    }

def h3(text):
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": [{"type": "text", "text": {"content": safe(text)}}]}
    }

def bullet(text):
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": safe(text)}}]}
    }

def todo(text):
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {
            "rich_text": [{"type": "text", "text": {"content": safe(text)}}],
            "checked": False
        }
    }

def para(text):
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": safe(text)}}]}
    }

def divider():
    return {"object": "block", "type": "divider", "divider": {}}

# --- Build all blocks ---
blocks = []

# Header
blocks.append(para("Last updated: 2026-04-28 | Tanta Holdings LLC full infrastructure map. Read before starting any major task."))
blocks.append(divider())

# ================================================================
# SECTION 1: BUSINESS UNITS
# ================================================================
blocks.append(h1("1. Business Units"))

blocks.append(h2("Tanta Global Academy (TGA)"))
blocks.append(bullet("Status: Active"))
blocks.append(bullet("URL: academy.tantaglobal.com"))
blocks.append(bullet("What it does: VA certification + eLearning (VA101-105), custom LMS with Supabase + Stripe, exam certification ($5/exam, $25 bundle), Academy Shop (13 products + VA Bundle)"))
blocks.append(bullet("Revenue state: Courses free, paid exams live ($5 each), shop live (Stripe checkout), 0 sales on Gumroad apps to date"))
blocks.append(bullet("LMS: Next.js + Supabase + Stripe deployed at academy.tantaglobal.com | LearnWorlds: cancelled Apr 15 2026"))
blocks.append(bullet("Curriculum: 28 storyboards done across CR, HRM, MKT, SAL, VA, AS tracks. 14 planned. Nightly Mikasa build."))

blocks.append(h2("Tanta Global Assist (TGA-A)"))
blocks.append(bullet("Status: Active"))
blocks.append(bullet("URL: tanta-global-assist.com"))
blocks.append(bullet("What it does: VA workforce development + placement marketplace. Two-sided: VA intake + employer intake. HubSpot pipeline (New Lead -> Certified -> Placement Ready)."))
blocks.append(bullet("Revenue state: Placement fee TBD. VA intake forms live. HubSpot configured, Make.com automation pending."))
blocks.append(bullet("Social automation: Drives all content production (FB, LinkedIn, TikTok, Instagram, Reddit, Threads, Bluesky, YouTube)"))
blocks.append(bullet("CRM: HubSpot free tier, 1252 contacts. Apollo consulting sequence launched Apr 2026."))

blocks.append(h2("Tanta Holdings LLC (Consulting + Parent)"))
blocks.append(bullet("Status: Active - positioning as AI Enablement Lead / LLM Enablement Consultant"))
blocks.append(bullet("URL: tanta-holdings.com"))
blocks.append(bullet("What it does: Jon's consulting practice. AI Enablement, Instructional Design, LLM Consulting for enterprise HR/L&D."))
blocks.append(bullet("Pricing: $2,500 starter / $8,500 full curriculum / retainer options / $85-150/hr"))
blocks.append(bullet("Revenue state: Active pipeline via Apollo. Government contracting angle (UC Systems / OMNIA Partners)."))
blocks.append(bullet("Books (KDP): 2 live (Documentation Standard, American Standard), 5 Standard Series ready to upload, 2 Built-to-Standard in development"))
blocks.append(bullet("Amazon Ads: American Standard campaign live Apr 24 - May 8 2026. $10/day. ASIN B0GWS2Z4CG."))

blocks.append(h2("Janice's Tutoring Division"))
blocks.append(bullet("Status: Building (~60% complete, feature flag OFF)"))
blocks.append(bullet("URL: academy.tantaglobal.com/tutoring (not public)"))
blocks.append(bullet("What it does: Tutoring marketplace under TGA umbrella. Janice Edwards runs day-to-day."))
blocks.append(bullet("Revenue state: Pre-revenue. 8 gaps blocking launch (see Open Items section)."))
blocks.append(bullet("Janice also manages: Booksprout ARC campaigns, day-to-day book review management"))

blocks.append(h2("RemoteReady Mobile App"))
blocks.append(bullet("Status: Building - pre-launch (app built, not publicly released)"))
blocks.append(bullet("Platform: iOS + Android (Expo/React Native) | Bundle ID: com.tantaholdings.remoteready"))
blocks.append(bullet("What it does: Mobile-first VA career tools. eLearning access, exam cert, VA tools library, template marketplace."))
blocks.append(bullet("Pricing: $4.99/month | Launch promo: code RREADY = $1.25 first month"))
blocks.append(bullet("Revenue state: Pre-revenue. RevenueCat backend integrated. Play Store products not yet configured."))
blocks.append(bullet("GitHub: SirTanta/remoteready-mobile | Version: 1.0.4"))
blocks.append(bullet("Key rule: Pro does NOT grant free exam access. $2 discount only ($3 vs $5). Never describe as free."))

blocks.append(h2("Books / Publishing"))
blocks.append(bullet("Status: Active"))
blocks.append(bullet("Platform: Amazon KDP + Booksprout + BookSirens (pending)"))
blocks.append(bullet("Published: The Documentation Standard (B0FJ5D7L17 / B0GWHPDYLC, $7.99/$14.99) | The American Standard (B0GWS2Z4CG / B0GWVDV76V, $9.99/$19.99)"))
blocks.append(bullet("Ready to upload: AI Enablement, Delegation, Onboarding, Facilitation, Remote Work Standards ($7.99/$14.99 each) - all Motoko QA passed"))
blocks.append(bullet("In development: The Design Standard (~16k words, needs expansion) | The Learning Standard (~25.4k, Chs 17-19 need work)"))
blocks.append(bullet("Ship order: American Standard (done) -> AI Enablement -> Delegation -> Onboarding -> Facilitation -> Remote Work -> Learning -> Design"))
blocks.append(bullet("Booksprout: $29/mo plan, 20-copy limit, campaigns running Apr 20 - May 20 2026"))
blocks.append(bullet("Pricing rule: Standard Series $7.99/$14.99 | American Standard $9.99/$19.99 | No discounts without Jon approval"))

blocks.append(h2("Tanta Visa Pathways (TVP)"))
blocks.append(bullet("Status: Backburner"))
blocks.append(bullet("URL: tantavisapathways.com"))
blocks.append(bullet("What it does: US visa consulting. Firebase stack."))
blocks.append(bullet("Revenue state: Not active. Dashboard panel shows BACKBURNER state, no DB calls."))

blocks.append(divider())

# ================================================================
# SECTION 2: TECHNOLOGY INFRASTRUCTURE
# ================================================================
blocks.append(h1("2. Technology Infrastructure"))

blocks.append(h2("Hosting & Compute"))

blocks.append(h3("Kipi Automation Hub VM"))
blocks.append(bullet("IP: 146.190.145.245 | DigitalOcean Droplet 564703731"))
blocks.append(bullet("Purpose: Main automation hub - job hunt, client hunt, OpenTabs browser automation, cron jobs"))
blocks.append(bullet("SSH: ssh -i C:/Users/jedwa/.ssh/kipi_automation_hub root@146.190.145.245"))
blocks.append(bullet("Stack: OpenTabs 0.0.97 (all 6 plugins), Chromium 147, Xvfb, PM2 (empty - scripts not yet deployed)"))
blocks.append(bullet("Cron: 2am git pull from /root/Kipi-system. Amazon Ads monitor 8am UTC."))
blocks.append(bullet("Cost: $6/month (main). Total VM fleet: $30/month."))
blocks.append(bullet("Credentials: SSH key at C:/Users/jedwa/.ssh/kipi_automation_hub | Infisical machine identity redmarz-deed"))
blocks.append(bullet("Facebook work: Load FB cookies from Infisical -> OpenTabs create_group_post for group posting"))

blocks.append(h3("Streaming VM 1 - @TantaRemote"))
blocks.append(bullet("IP: 146.190.124.12"))
blocks.append(bullet("Purpose: 24/7 YouTube live stream for @TantaRemote channel"))
blocks.append(bullet("SSH: ssh -i C:/Users/jedwa/.ssh/kipi_automation_hub root@146.190.124.12"))
blocks.append(bullet("Stream restart: nohup /root/streams/tantaremote/stream.sh &"))
blocks.append(bullet("Token: YOUTUBE_TANTAREMOTE_REFRESH_TOKEN in Infisical prod"))
blocks.append(bullet("Cost: $12/month"))

blocks.append(h3("Streaming VM 2 - @TantaHoldings"))
blocks.append(bullet("IP: 165.232.158.190"))
blocks.append(bullet("Purpose: 24/7 YouTube live stream for @TantaHoldings channel (repurposed Apr 26 2026)"))
blocks.append(bullet("SSH: ssh -i C:/Users/jedwa/.ssh/kipi_automation_hub root@165.232.158.190"))
blocks.append(bullet("Stream restart: nohup /root/streams/tantaholdings/stream.sh &"))
blocks.append(bullet("Token: MISSING - refresh token not yet on file (see Open Items)"))
blocks.append(bullet("Cost: $12/month"))

blocks.append(h3("Vercel"))
blocks.append(bullet("Purpose: Frontend deployments"))
blocks.append(bullet("Active projects: tanta-holdings.com, dashboard.tantaholdings.com, academy.tantaglobal.com"))
blocks.append(bullet("Auth: dashboard migrated to Supabase email/password 2026-04-10"))
blocks.append(bullet("Token: VERCEL_TOKEN in Infisical prod"))

blocks.append(h3("WordPress - tantaglobal.com"))
blocks.append(bullet("Purpose: Main marketing website"))
blocks.append(bullet("Host: LiteSpeed/Namecheap"))
blocks.append(bullet("Credentials: WORDPRESS_USER, WORDPRESS_APP_PASSWORD in Infisical prod"))
blocks.append(bullet("Nav block ID: 18 = Header Navigation. REST API active."))

blocks.append(h2("Databases"))

blocks.append(h3("Supabase - TGA Academy"))
blocks.append(bullet("Project ref: oyekorltsadcjzwncnjb"))
blocks.append(bullet("Purpose: TGA Academy DB - users, courses, exams, enrollments, exam_purchases, products, storage"))
blocks.append(bullet("Storage bucket: products (public) - ZIP file delivery for Academy Shop"))
blocks.append(bullet("Credentials: SUPABASE_SERVICE_KEY, SUPABASE_JWT in Infisical prod"))
blocks.append(bullet("Auth: Email/password (Supabase Auth). No mock DBs in tests - real DB only."))

blocks.append(h3("SQLite on VM"))
blocks.append(bullet("Purpose: Job tracker / client hunt local state"))
blocks.append(bullet("Location: /root/ on kipi-automation-hub VM (146.190.145.245)"))

blocks.append(h2("Code Repositories (SirTanta GitHub)"))
blocks.append(bullet("kipi-system - Main ops repo. All automation, workflows, wiki, deliverables, social queues."))
blocks.append(bullet("tga-academy - LMS platform (Next.js + Supabase + Stripe). Deployed to academy.tantaglobal.com via Vercel."))
blocks.append(bullet("remoteready-mobile - React Native app (Expo). iOS + Android. RevenueCat subscriptions."))
blocks.append(bullet("job-hunter-agent - Job search + client hunt automation. SQLite tracker. Daily GitHub Actions."))
blocks.append(bullet("tanta-ops-dashboard - Ops dashboard at dashboard.tantaholdings.com"))

blocks.append(h2("Secrets Management"))
blocks.append(bullet("Platform: Infisical - project 585b5bee-a123-4323-bd32-4d924d98b950"))
blocks.append(bullet("Machine Identity: 713a38bc (universal auth - redmarz-deed on local, auto on VM)"))
blocks.append(bullet("dev environment: API keys (Anthropic, OpenAI, etc.)"))
blocks.append(bullet("prod environment: Social cookies (FB, LinkedIn), Amazon, publishing keys, Stripe, Supabase, all OAuth tokens"))
blocks.append(bullet("Count: 39+ secrets across environments"))
blocks.append(bullet("GitHub Secrets (SirTanta/Kipi-system): UPLOAD_POST_API_KEY, PEXELS_API_KEY, ANTHROPIC_API_KEY, LINKEDIN_ACCESS_TOKEN (exp Jun 2026), YOUTUBE_* tokens, REDDIT_USERNAME/PASSWORD, SUBSTACK_SESSION_COOKIE"))
blocks.append(bullet("Golden rule: All API keys in Infisical. GitHub secrets = deployed version. .env.local = local version."))

blocks.append(divider())

# ================================================================
# SECTION 3: AUTOMATION & WORKFLOWS
# ================================================================
blocks.append(h1("3. Automation & Workflows"))
blocks.append(para("All workflows in SirTanta/Kipi-system GitHub Actions. Status: Active unless noted."))

blocks.append(h2("Kitasan - Content & Social"))
blocks.append(bullet("Social Distributor - Video: 6pm MDT daily. Posts video to FB, Instagram, TikTok, LinkedIn, Threads, Bluesky. Day-aware routing (Mon=long-form, Tue/Sat=AI, Wed=Jon ID)."))
blocks.append(bullet("Social Distributor - Text/Image: 9am + 10pm MDT. Non-video days only (Sun/Thu/Fri). FB text + Instagram image."))
blocks.append(bullet("Social Content Generator: Mondays 6am MDT. Claude Haiku fills queues when any platform drops below 10 items. Guardrails active."))
blocks.append(bullet("LinkedIn/IG Poster: 8am MDT daily (skips Mon/Tue/Wed/Sat). LinkedIn text + Pexels image."))
blocks.append(bullet("Post Book Promo: Book promotion posts to social queues."))
blocks.append(bullet("Facebook Full Setup / FB Cancel & Reschedule: Facebook group and page management."))
blocks.append(bullet("Pinterest Pin Poster: Daily 9am MDT - pins to Tanta Holdings board."))
blocks.append(bullet("FB Group Joiner: Facebook group growth automation."))
blocks.append(bullet("Content Coordinator: Daily queue refresh. Preserves posted_at timestamps on refresh (critical - do not remove)."))

blocks.append(h2("Mako - DevOps & Infrastructure"))
blocks.append(bullet("Sync Infisical Secrets -> GitHub: Keeps GitHub secrets in sync with Infisical prod vault."))
blocks.append(bullet("YouTube 24/7 Live Stream: Manages live stream health on @TantaRemote and @TantaHoldings VMs."))
blocks.append(bullet("YouTube - Update Channel Metadata: Weekly Monday 6am UTC. Banners, SEO, descriptions from /root/youtube-manager/ on VM."))
blocks.append(bullet("Upload-Post Schedule Cleanup: Removes stale scheduled posts from Upload-Post dashboard."))
blocks.append(bullet("Make Check: Monitors Make.com scenario health."))
blocks.append(bullet("Hot Dispatch Executor: Executes VM commands via GitHub Actions dispatch."))
blocks.append(bullet("YouTube Queue Sync / Drive-YouTube Matcher / YouTube Queue Audit: Video pipeline management."))
blocks.append(bullet("Synthesia to YouTube Publisher: Publishes Synthesia product videos to YouTube."))
blocks.append(bullet("YouTube - Make Product Videos Public / Add RemoteReady CTA / Create RemoteReady Playlist: Video metadata management."))

blocks.append(h2("Tsunade - Monitoring"))
blocks.append(bullet("Social Activity Dashboard: 9pm MDT daily -> GitHub Issue #50. Posts platform status (OK/COLD/NEVER) for all social channels."))
blocks.append(bullet("Email Digest - All Inboxes: Daily. Summarizes jedwards@ and info@ inboxes to GitHub issue."))
blocks.append(bullet("Morning Ops Report: 7am MDT daily. Workflow health + queue depths -> deliverables/_ops/morning-report.json"))
blocks.append(bullet("Facebook Weekly Progress Report: Weekly social performance summary."))
blocks.append(bullet("YouTube Status Check / YouTube Audit Unlisted: Video health monitoring."))

blocks.append(h2("Oguri Cap - CRM & Outreach"))
blocks.append(bullet("HubSpot - Create Custom Contact Properties: Sets up HubSpot contact schema for VA pipeline."))
blocks.append(bullet("HubSpot - VA101 Enrollment Pipeline Setup: Automates VA101 enrollment tracking in HubSpot."))
blocks.append(bullet("HubSpot Employer Cold Email Batch: Sends cold outreach to employer contacts via HubSpot."))
blocks.append(bullet("LinkedIn Employer Outreach Brief: Generates LinkedIn outreach briefs for employer targets."))
blocks.append(bullet("Daily Blog Publisher: Publishes daily blog content."))
blocks.append(bullet("Deploy VA Pipeline Forms: Deploys VA + employer intake forms to Vercel."))
blocks.append(bullet("WordPress SEO Sync: Syncs SEO metadata to tantaglobal.com WordPress."))

blocks.append(h2("Deed - Job Hunt & Infrastructure"))
blocks.append(bullet("Job Search Daily: Daily. Runs job search pipeline on VM. SQLite tracker. Apollo integration."))
blocks.append(bullet("Send Email: Utility workflow for system notifications."))
blocks.append(bullet("Fix TGA Academy Link: Utility fix workflow."))

blocks.append(h2("VM Cron Jobs (Not GitHub Actions)"))
blocks.append(bullet("Job Hunt: VM cron - searches job boards, tracks applications in SQLite, logs to GitHub"))
blocks.append(bullet("Client Hunt / Apollo: VM cron - Apollo sequence management, outreach tracking"))
blocks.append(bullet("Amazon Ads Monitor: 8am UTC daily - checks campaign status -> updates Issue #50"))
blocks.append(bullet("YouTube Manager: Mondays 6am UTC from /root/youtube-manager/ - channel metadata updates"))

blocks.append(divider())

# ================================================================
# SECTION 4: SOCIAL & CONTENT PLATFORMS
# ================================================================
blocks.append(h1("4. Social & Content Platforms"))
blocks.append(para("Status dashboard: GitHub Issue #50 (updated 9pm MDT daily). Monitor for COLD/NEVER alerts."))

blocks.append(h2("YouTube"))
blocks.append(bullet("@TantaTeam (UC-gZqeyVHS3Jhq5VKeSVDww): ACTIVE - main content channel. 31 videos queued. Tue+Sat 9am MDT scheduler. Token: YOUTUBE_TANTATEAM_REFRESH_TOKEN in Infisical."))
blocks.append(bullet("@TantaRemote: ACTIVE - 24/7 live stream. VM: 146.190.124.12. Token: YOUTUBE_TANTAREMOTE_REFRESH_TOKEN."))
blocks.append(bullet("@TantaHQ: ACTIVE - channel updated Apr 26 2026. Token: YOUTUBE_TANTAHQ_REFRESH_TOKEN in Infisical."))
blocks.append(bullet("@TantaSkills: ACTIVE - channel updated Apr 26 2026. Token: YOUTUBE_TANTASKILLS_REFRESH_TOKEN in Infisical."))
blocks.append(bullet("@TantaTraining: ACTIVE - channel updated Apr 26 2026. Token: YOUTUBE_TANTATRAINING_REFRESH_TOKEN in Infisical."))
blocks.append(bullet("@TantaHoldings (UC-gZqeyVHS3Jhq5VKeSVDww): REPURPOSED as 24/7 live stream. VM: 165.232.158.190. Token: MISSING (see Open Items)."))
blocks.append(bullet("OAuth: YOUTUBE_OAUTH_CLIENT_ID / YOUTUBE_OAUTH_CLIENT_SECRET in Infisical. All 4 main channels refreshed Apr 26 2026."))
blocks.append(bullet("Profile pictures: In C:/Users/jedwa/Downloads/ - manual upload needed in YouTube Studio."))

blocks.append(h2("Facebook"))
blocks.append(bullet("Tanta Global Assist page (ID 710339802154571): ACTIVE - primary posting page. Daily video reels + text posts via Upload-Post."))
blocks.append(bullet("Tanta Holdings page (ID 61576177182868): ACTIVE - secondary posting page. Dual-post with 2s delay. fb_only=True prevents duplicate IG/TikTok/LinkedIn posts from this page."))
blocks.append(bullet("Automation: social-distributor.yml (video 6pm MDT) + social-distributor-text-image.yml (text 9am/image 10pm MDT)"))
blocks.append(bullet("Group automation: FB Group Joiner workflow. Cookie-based auth via Infisical (FB_COOKIE_XS, FB_COOKIE_C_USER, FB_COOKIE_DATR, FB_COOKIE_B64)."))

blocks.append(h2("LinkedIn"))
blocks.append(bullet("Account: Tanta Holdings org (107785563) + Jon Edwards personal profile"))
blocks.append(bullet("Status: ACTIVE - daily text + image posts"))
blocks.append(bullet("Automation: linkedin-ig-poster.yml (8am MDT, skips video days) + social-distributor.yml (video 6pm MDT)"))
blocks.append(bullet("Token: LINKEDIN_ACCESS_TOKEN in GitHub secrets. EXPIRES JUNE 2026 - refresh before May 2026."))

blocks.append(h2("Instagram"))
blocks.append(bullet("Status: ACTIVE - video reels + image posts"))
blocks.append(bullet("Automation: social-distributor.yml (video 6pm MDT) + social-distributor-text-image.yml (image 10pm MDT, non-video days)"))
blocks.append(bullet("Posting via: Upload-Post.com API"))

blocks.append(h2("TikTok"))
blocks.append(bullet("Status: ACTIVE (video posts) | PAUSED (auto-follows - blocked on TIKTOK_SESSION_B64)"))
blocks.append(bullet("Video posts: Daily via social-distributor.yml"))
blocks.append(bullet("Auto-follows: 25/day at 8am MDT - needs TIKTOK_SESSION_B64 secret to resume"))
blocks.append(bullet("Posting via: Upload-Post.com API"))

blocks.append(h2("Reddit"))
blocks.append(bullet("Account: SirTanta | Subreddit: r/TantaHoldings"))
blocks.append(bullet("Status: ACTIVE - 2x daily (8am + 6pm MDT). 10-hour global cooldown between posts."))
blocks.append(bullet("Automation: reddit-poster.yml via Upload-Post. Manual deletions must be done by Jon at reddit.com."))
blocks.append(bullet("Queue: deliverables/production/tga-assist/social/social-growth/reddit-post-queue.json"))
blocks.append(bullet("Note: New account - API app creation blocked by Reddit policy. Upload-Post handles posting."))

blocks.append(h2("Threads & Bluesky"))
blocks.append(bullet("Status: ACTIVE - video posts Mon-Sat via social-distributor.yml"))
blocks.append(bullet("Posting via: Upload-Post.com API"))
blocks.append(bullet("No separate text queues yet"))

blocks.append(h2("Pinterest"))
blocks.append(bullet("Status: ACTIVE - daily 9am MDT via Pinterest Pin Poster workflow"))
blocks.append(bullet("Posting via: Upload-Post.com API"))
blocks.append(bullet("Board: Tanta Holdings"))

blocks.append(h2("X/Twitter"))
blocks.append(bullet("Status: NOT ACTIVE"))
blocks.append(bullet("Reason: Upload-Post does not support video posting to X. Would require native API management."))

blocks.append(divider())

# ================================================================
# SECTION 5: REVENUE CHANNELS
# ================================================================
blocks.append(h1("5. Revenue Channels"))

blocks.append(h2("KDP Books (Amazon)"))
blocks.append(bullet("The Documentation Standard: LIVE. Kindle B0FJ5D7L17 ($7.99) / Paperback B0GWHPDYLC ($14.99). Series: Standard Series."))
blocks.append(bullet("The American Standard: LIVE Apr 2026. Kindle B0GWS2Z4CG ($9.99) / Paperback B0GWVDV76V ($19.99). Amazon Ads campaign live Apr 24 - May 8, $10/day."))
blocks.append(bullet("The AI Enablement Standard: Kindle LIVE Apr 21 2026 ($7.99). Paperback pending review."))
blocks.append(bullet("The Delegation Standard: READY TO UPLOAD. $7.99/$14.99."))
blocks.append(bullet("The Onboarding Standard: READY TO UPLOAD. $7.99/$14.99."))
blocks.append(bullet("The Facilitation Standard: READY TO UPLOAD. $7.99/$14.99."))
blocks.append(bullet("The Remote Work Standard: READY TO UPLOAD. $7.99/$14.99."))
blocks.append(bullet("Amazon Ads: Entity ENTITYBQYR469SH68S. ADS_ENTITY_ID in Infisical prod. Monitor 8am UTC daily."))
blocks.append(bullet("Booksprout ARC: Both books in campaign Apr 20 - May 20. 20 copies max. Reviews due June 3. Janice manages."))
blocks.append(bullet("BookSirens: Application submitted, awaiting approval (watch jedwards@tanta-holdings.com, 3-day turnaround)"))

blocks.append(h2("Gumroad - Digital Products"))
blocks.append(bullet("Account: Tanta Team (info@tanta-holdings.com) | Seller ID: 4zoQp994-qtnpokLstlOBg=="))
blocks.append(bullet("VA Business Launch Planner: $47 - https://tantateam.gumroad.com/l/launchplan"))
blocks.append(bullet("Client Communication Workbook: $37 - https://tantateam.gumroad.com/l/commworkbook"))
blocks.append(bullet("First 90 Days Client Tracker: $37 - https://tantateam.gumroad.com/l/clientracker"))
blocks.append(bullet("Remote Work Setup Audit: $19 - https://tantateam.gumroad.com/l/setupaudit"))
blocks.append(bullet("VA Certification Readiness Tracker: $27 - https://tantateam.gumroad.com/l/readtrack"))
blocks.append(bullet("Status: All 5 LIVE as of 2026-04-09. 0 sales to date. Synthesia demo videos ready but not yet linked."))
blocks.append(bullet("Etsy: 13 listing images + 5 demo videos ready. BLOCKED on API key from Etsy."))

blocks.append(h2("TGA Academy"))
blocks.append(bullet("Courses: VA101-105 FREE (open access). Migrated to custom LMS."))
blocks.append(bullet("Exams: $5 each, $25 bundle (all 5). E1-E5 live. Stripe + Supabase payment flow."))
blocks.append(bullet("Academy Shop: 13 products + VA Bundle at academy.tantaglobal.com/shop. Stripe checkout live."))
blocks.append(bullet("Curriculum pipeline: 28 storyboards done. Nightly Mikasa builds."))

blocks.append(h2("Stripe"))
blocks.append(bullet("TGA Academy: Exam payments + shop checkout. STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY in Infisical."))
blocks.append(bullet("RemoteReady: RevenueCat backend + Stripe for web subscriptions. SDK keys need setup + Play Store products."))

blocks.append(h2("Amazon Ads"))
blocks.append(bullet("Campaign: The American Standard - SP Auto (Sponsored Products, Automatic targeting)"))
blocks.append(bullet("ASIN: B0GWS2Z4CG (Kindle) | Budget: $10/day max | Run: Apr 24 - May 8 2026 | Default bid: $0.75"))
blocks.append(bullet("Entity: ENTITYBQYR469SH68S | Monitor: VM cron 8am UTC -> Issue #50"))

blocks.append(h2("Consulting (Tanta Solutions)"))
blocks.append(bullet("Model: AI Enablement, Instructional Design, LLM Consulting for enterprise HR/L&D"))
blocks.append(bullet("Pricing: $2,500 starter / $8,500 full curriculum / retainer / $85-150/hr"))
blocks.append(bullet("Pipeline: Apollo sequence launched Apr 2026 (Tanta Holdings L&D AI Consulting sequence)"))
blocks.append(bullet("Target: HR directors, CLOs, VP L&D at enterprises (healthcare, financial services, government, tech)"))
blocks.append(bullet("Government contracting: UC Systems / OMNIA Partners vehicle (active pipeline)"))
blocks.append(bullet("Market signals: 35.8% Microsoft Copilot adoption = training gap. 80% US health systems exploring AI."))

blocks.append(divider())

# ================================================================
# SECTION 6: CRM & OUTREACH
# ================================================================
blocks.append(h1("6. CRM & Outreach"))

blocks.append(h2("HubSpot"))
blocks.append(bullet("Workspace: jedwards@tanta-holdings.com | Tier: Free"))
blocks.append(bullet("Contacts: 1252 total. VA pipeline active (New Lead -> Certified -> Placement Ready)."))
blocks.append(bullet("Workflows: VA101 enrollment pipeline, employer cold email batch, custom contact properties set up."))
blocks.append(bullet("Status: 0 new contacts/24h - intake form audit needed (see Open Items)"))
blocks.append(bullet("Make.com: Scenarios designed for VA + employer webhook routing. Not yet built (pending credentials)."))
blocks.append(bullet("Tally forms: 'Not configured' in marketing ops monitor (see Open Items)"))

blocks.append(h2("Apollo"))
blocks.append(bullet("Sequence: Tanta Holdings L&D AI Consulting - just activated Apr 2026"))
blocks.append(bullet("Purpose: Outbound to enterprise HR/L&D decision-makers"))
blocks.append(bullet("VM: Client hunt cron job runs on kipi-automation-hub (146.190.145.245)"))

blocks.append(h2("Email"))
blocks.append(bullet("jedwards@tanta-holdings.com: Primary work email. Google Workspace. All work product delivered here."))
blocks.append(bullet("info@tanta-holdings.com: ALL automated system notifications + customer intake. Never use jedwards@ for system emails."))
blocks.append(bullet("jedwa82@gmail.com: Jon's personal email. Do NOT use for business."))
blocks.append(bullet("Gmail automation rule: NEVER use OAuth refresh tokens. Use Google Apps Script only. OAuth expires; Apps Script doesn't."))
blocks.append(bullet("MailerLite: Launching Apr 22. Free tier (1k subscribers, 12k emails/mo). Marketing organic list."))

blocks.append(h2("VA Pipeline (Two-Sided Marketplace)"))
blocks.append(bullet("VA Intake Form: deliverables/finals/va-pipeline/va-intake-form.html"))
blocks.append(bullet("Employer Intake Form: deliverables/finals/va-pipeline/employer-intake-form.html"))
blocks.append(bullet("Landing Page: deliverables/finals/va-pipeline/landing-page.html"))
blocks.append(bullet("HubSpot Pipeline: 6 stages configured. Webhook routing via Vercel."))
blocks.append(bullet("Placement fee: TBD. Design phase only."))

blocks.append(divider())

# ================================================================
# SECTION 7: OPEN ITEMS / KNOWN GAPS
# ================================================================
blocks.append(h1("7. Open Items / Known Gaps"))
blocks.append(para("All items below are active gaps requiring action. Owner in parens."))

blocks.append(h2("Urgent / Blocking"))
blocks.append(todo("@TantaHoldings YouTube refresh token missing - streaming VM 2 (165.232.158.190) cannot auto-recover without it. Get token and add to Infisical prod as YOUTUBE_TANTAHOLDINGS_REFRESH_TOKEN. (Deed)"))
blocks.append(todo("TikTok session key missing (TIKTOK_SESSION_B64) - 25/day auto-follow workflow is paused. (Jon - requires manual browser session extraction)"))
blocks.append(todo("LinkedIn access token EXPIRES JUNE 2026 - refresh before May 2026. Set reminder. (Deed)"))

blocks.append(h2("Janice Tutoring Division - 8 Launch Gaps"))
blocks.append(todo("Calendly: Set up booking calendar for tutoring sessions (Jon/Janice)"))
blocks.append(todo("Stripe checkout: Configure tutoring payment flow at academy.tantaglobal.com/tutoring (Mikasa)"))
blocks.append(todo("Webhook: Connect Calendly booking to Supabase + HubSpot pipeline (Mikasa)"))
blocks.append(todo("Feature flag: Flip tutoring feature flag ON when above 3 are complete (Deed)"))
blocks.append(todo("Visual identity: Tutoring division brand assets (Janice/Jon decision)"))
blocks.append(todo("Market research validation: Confirm tutoring demand before full launch (Jon)"))
blocks.append(todo("Curriculum inventory: Document what Janice can teach + create first course storyboard (Janice)"))
blocks.append(todo("Notion workspace: Set up Janice's workspace for managing tutoring pipeline (Deed)"))

blocks.append(h2("Publishing"))
blocks.append(todo("Upload The Delegation Standard to KDP (READY - generate DOCX first via generate-docx.py, then upload)"))
blocks.append(todo("Upload The Onboarding Standard to KDP (READY - same process)"))
blocks.append(todo("Upload The Facilitation Standard to KDP (READY - same process)"))
blocks.append(todo("Upload The Remote Work Standard to KDP (READY - same process)"))
blocks.append(todo("AI Enablement Standard paperback: review pending before upload"))
blocks.append(todo("Pass 4 review all Standard Series before each upload: verify Eliza name, composite client stories, DOE facilitation, Navy drill details, Remote Work scaling 9->15"))
blocks.append(todo("Expand The Design Standard (~9k more words needed + 3 structural fixes: Master Chief story x3, Ch8/Ch9 reference, Ch5 mini-SME)"))
blocks.append(todo("Fix The Learning Standard Chs 17-19 + one off-voice line"))
blocks.append(todo("Etsy: Receive API key from Etsy. Then upload 13 listing images + 5 demo videos (all ready in repo)."))
blocks.append(todo("Synthesia product videos: Make 4 unlisted YouTube videos PUBLIC and link to Gumroad product pages"))

blocks.append(h2("CRM & Lead Flow"))
blocks.append(todo("HubSpot: 0 new contacts/24h - audit VA intake form. Verify form webhook is routing to HubSpot. (Oguri Cap)"))
blocks.append(todo("Tally forms: 'Not configured' in marketing ops monitor - configure Tally form webhooks (Oguri Cap)"))
blocks.append(todo("Make.com: Build VA + Employer webhook scenarios (blueprints ready). Jon needs to grant Make.com credentials. (Deed waits on Jon)"))
blocks.append(todo("HubSpot intake form: Verify employer intake form routes to correct HubSpot pipeline stage"))

blocks.append(h2("RemoteReady Launch"))
blocks.append(todo("Play Store: Configure subscription products (remoteready_pro_monthly) in Google Play Console"))
blocks.append(todo("RevenueCat: Set up RC webhook secret + SDK keys. Initialize in _layout.tsx."))
blocks.append(todo("EAS build: Download signed AAB (build 34f33c50) and upload to Play Store"))
blocks.append(todo("iOS: Configure com.tantaholdings.remoteready.pro_monthly in App Store Connect"))
blocks.append(todo("Public launch: When all above complete, change marketing from 'Coming Soon' to 'Available Now'"))

blocks.append(h2("VM & Automation"))
blocks.append(todo("VM PM2: Deploy job hunt + client hunt scripts to PM2 on kipi-automation-hub. See REMOTE-AUTOMATION-STACK.md."))
blocks.append(todo("JobRight.ai session cookie: Will expire. Build refresh process or document manual refresh steps. (Deed)"))
blocks.append(todo("DigitalOcean SSH key: Add private key to Infisical for backup/recovery. Currently only in C:/Users/jedwa/.ssh/"))
blocks.append(todo("Substack cookie: Will expire. substack_get_cookie.py ready in C:/Users/jedwa/AppData/Local/Temp/ - run when needed. (Jon triggers)"))
blocks.append(todo("BookSirens: Application pending. Watch jedwards@tanta-holdings.com for approval (3-day turnaround)."))

blocks.append(h2("Curriculum"))
blocks.append(todo("VA102-105: Load SCORM content into custom LMS (courses designed, not yet uploaded to new platform)"))
blocks.append(todo("Next storyboards due: CR303, HRM103, MKT103, SAL103 (nightly Mikasa workflow handles these)"))
blocks.append(todo("Profile pictures: Upload new channel icons to YouTube Studio for all 4 channels. Files in C:/Users/jedwa/Downloads/"))

blocks.append(divider())

# ================================================================
# SECTION 8: STANDING RULES REFERENCE
# ================================================================
blocks.append(h1("8. Standing Rules Reference"))
blocks.append(para("Non-negotiable rules. If in doubt, these override everything."))

blocks.append(bullet("Global positioning: Zero country-specific language. No 'Filipino VA,' 'Philippines,' '#FilipinoVA.' Audience is global."))
blocks.append(bullet("Social voice: All content writes as Jon Edwards - US military veteran, entrepreneur. No corporate speak. No em-dashes. No bullet lists on every post."))
blocks.append(bullet("RemoteReady pricing: $4.99/month always. $9.99 is wrong. Launch promo: $1.25/first month with code RREADY."))
blocks.append(bullet("Pro exam access: RemoteReady Pro does NOT grant free exams. $2 discount only ($3 vs $5). Never grant hasPurchased=true to Pro users."))
blocks.append(bullet("Content guardrails: validateContent() in social-content-generator.js blocks banned content. If it throws, content does NOT post. Do not bypass."))
blocks.append(bullet("Banned content patterns: Filipino/Philippines, #filipinova, app store references, false 'free' claims, AI giveaway openers."))
blocks.append(bullet("Email routing: System notifications -> info@. Jon's work -> jedwards@. Never jedwa82@gmail.com for business."))
blocks.append(bullet("OAuth rule: NEVER build Gmail/Google automation on OAuth refresh tokens. Use Google Apps Script."))
blocks.append(bullet("Email platform: HubSpot only. Brevo is not in use."))
blocks.append(bullet("Copyright: 2026 Tanta Holdings LLC on everything - apps, PDFs, courses, docs, templates, code files."))
blocks.append(bullet("Credentials: All API keys in Infisical. Never ask Jon to do platform work Deed can do with existing credentials."))
blocks.append(bullet("Work product: All deliverables -> jedwards@tanta-holdings.com Drive. Never jedwa82@gmail.com Drive."))
blocks.append(bullet("Model tiers: Haiku for content/scripts/queue-fills. Sonnet for code/multi-file builds. Opus for high-stakes decisions only."))
blocks.append(bullet("Verification protocol: After fixing any workflow, run gh run list --workflow=<name>.yml --limit 3 to confirm it fired. Trust commands, not edits."))

# ================================================================
# Now create the Notion page and append blocks
# ================================================================

print("Creating Notion page...")
page_payload = {
    "parent": {"type": "page_id", "page_id": PARENT_ID},
    "properties": {
        "title": {
            "title": [{"type": "text", "text": {"content": "Tanta Holdings - Infrastructure Map"}}]
        }
    }
}

page_resp = notion_call("https://api.notion.com/v1/pages", page_payload, method="POST")
page_id = page_resp["id"]
page_url = page_resp["url"]
print(f"Page created: {page_url}")
print(f"Page ID: {page_id}")

# Append blocks in chunks of 100
chunk_size = 100
total_blocks = len(blocks)
print(f"Total blocks to append: {total_blocks}")

for i in range(0, total_blocks, chunk_size):
    chunk = blocks[i:i + chunk_size]
    chunk_num = i // chunk_size + 1
    print(f"Appending chunk {chunk_num} ({len(chunk)} blocks, positions {i}-{i+len(chunk)-1})...")

    append_payload = {"children": chunk}
    notion_call(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        append_payload,
        method="PATCH"
    )
    print(f"  Chunk {chunk_num} OK")

print(f"\nDone! Notion page: {page_url}")
print(f"Total blocks written: {total_blocks}")
