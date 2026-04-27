"""Fill all `[REPLACE: ...]` markers in the canvas-90-day festival task files.

Runs inside WSL (reads absolute /root/... paths). Preserves the fest
frontmatter block and the `# Task: <name>` heading. Rewrites the body
between the heading and end of file with concrete Objective /
Requirements / Implementation / Done When sections.

Invoke from Windows via:
  wsl -d Ubuntu -- python3 "/mnt/c/Users/bruke/Pre Atlas/doctrine/scripts/fill_canvas_tasks.py"
"""
from __future__ import annotations

import re
from pathlib import Path

FEST_ROOT = Path("/root/festival-project/festivals/ready/canvas-90-day-CD0001")

# { relative_path: { "obj": str, "reqs": [str, ...], "impl": str, "verify": str } }
TASKS: dict[str, dict] = {
    # c1 demo video
    "001_C1_DEMO_VIDEO/01_record/02_record_demo.md": {
        "obj": "Record a screen capture showing the sitepull workflow end to end.",
        "reqs": [
            "Capture at 1080p 30fps, 3 to 8 minutes total length.",
            "Clean voiceover explaining each step as it happens.",
            "One complete sitepull run shown from URL entry to pulled assets.",
        ],
        "impl": "Open the sitepull tool, start recording, walk through a real pull against a live URL, narrate what the viewer is seeing. Re-record if you stumble on a key beat. Save the raw footage to a demo/raw/ folder.",
        "verify": "A single .mp4 or .mov file exists with the full flow captured and clear audio.",
    },
    "001_C1_DEMO_VIDEO/01_record/03_edit_video.md": {
        "obj": "Trim dead air and fumbles out of the raw recording.",
        "reqs": [
            "Silent gaps longer than 2 seconds removed.",
            "Any restart attempts or fumbles cut out.",
            "Final length under 5 minutes.",
        ],
        "impl": "Open the raw footage in CapCut, DaVinci Resolve, or a similar editor. Slice out pauses and mistakes. Export to demo/final_demo.mp4 at 1080p H.264.",
        "verify": "A final_demo.mp4 file under 200MB, under 5 minutes, that plays cleanly with audio.",
    },
    "001_C1_DEMO_VIDEO/02_publish/01_upload_to_platform.md": {
        "obj": "Host the final video somewhere anyone with a link can watch.",
        "reqs": [
            "Video uploaded to YouTube (unlisted or public) or Loom.",
            "Shareable URL copied into demo/publish.md.",
            "Title and one sentence description set on the upload.",
        ],
        "impl": "Pick YouTube for permanence or Loom for speed. Upload final_demo.mp4. Title it something like \"Sitepull demo\". Grab the share URL.",
        "verify": "The URL plays the video for a logged out viewer.",
    },
    "001_C1_DEMO_VIDEO/02_publish/02_share_post.md": {
        "obj": "Post the demo link somewhere people who care will see it.",
        "reqs": [
            "Posted to at least one channel (X, LinkedIn, Discord, group chat, or email list).",
            "Post includes the demo link and one line of context.",
            "Link verified clickable from the published version of the post.",
        ],
        "impl": "Write a 2 to 3 sentence post: what it is, what it does, the link. Post it. Open the posted version and click the link to confirm it resolves.",
        "verify": "Screenshot or URL of the published post with a working demo link.",
    },

    # c2 brand
    "002_C2_BRAND/01_name/01_brainstorm_shortlist.md": {
        "obj": "Produce a list of 10 to 15 candidate brand names for the canvas product.",
        "reqs": [
            "At least 10 candidates written down.",
            "All candidates in one file, not scattered notes.",
            "Each name has one sentence of reasoning next to it.",
        ],
        "impl": "Free associate for 20 minutes with no filtering. Mix themes: canvas, blank, draft, fresh start, space, frame, reframe. Pull in words from the 8 Steps vocabulary. Save to brand/shortlist.md.",
        "verify": "brand/shortlist.md exists with 10+ candidates and a sentence of reasoning per name.",
    },
    "002_C2_BRAND/01_name/02_trademark_check.md": {
        "obj": "Knock out candidates that are trademarked or too close to existing brands.",
        "reqs": [
            "Each shortlist name checked on tmsearch.uspto.gov.",
            "Each shortlist name googled for direct brand collisions.",
            "Each name tagged CLEAR, RISKY, or BLOCKED in shortlist.md.",
        ],
        "impl": "For each name, open the USPTO TESS search and the first page of Google. Tag conflicts right next to the name. Do the whole list in one sitting.",
        "verify": "Every name in brand/shortlist.md has a CLEAR, RISKY, or BLOCKED tag.",
    },
    "002_C2_BRAND/01_name/03_pick_final_name.md": {
        "obj": "Pick the one name you will commit to, with a one sentence rationale.",
        "reqs": [
            "One name chosen from the CLEAR candidates.",
            "Decision written into brand/decision.md.",
            "Rationale is a single sentence, no hedging.",
        ],
        "impl": "From the CLEAR candidates, filter by: easy to say out loud, easy to spell from hearing, .com or a short alternative available. Pick the one that makes you want to buy the domain today.",
        "verify": "brand/decision.md contains one name and one sentence explaining why.",
    },
    "002_C2_BRAND/02_domain/01_check_availability.md": {
        "obj": "Confirm the chosen brand has a usable domain and price out alternates.",
        "reqs": [
            "The .com checked on Namecheap or Porkbun.",
            "At least one fallback TLD checked (.ai, .app, .co, or a short variant).",
            "Availability and price captured in brand/domains.md.",
        ],
        "impl": "Go to Namecheap, type the brand. Record which TLDs are free and their prices. If .com is taken, note whether it is a squatter or an active site.",
        "verify": "brand/domains.md lists each option with TLD, price, and status.",
    },
    "002_C2_BRAND/02_domain/02_purchase_domain.md": {
        "obj": "Actually buy the domain so the brand is real.",
        "reqs": [
            "Chosen TLD purchased under your account.",
            "WHOIS privacy turned on.",
            "Receipt archived in brand/receipts/.",
        ],
        "impl": "Buy 2 to 3 years up front so the renewal does not get missed. Turn on auto renew. Save the confirmation email as a PDF in brand/receipts/.",
        "verify": "Domain shows active in the registrar dashboard and the receipt file exists.",
    },

    # c3 prototype
    "003_C3_PROTOTYPE/01_scaffold/01_choose_stack.md": {
        "obj": "Pick the exact tech stack for the canvas prototype in under 30 minutes.",
        "reqs": [
            "Decision documented in stack.md at the repo root.",
            "Explicit choice for frontend, backend, styling, deploy target.",
            "No \"I will decide later\" placeholders.",
        ],
        "impl": "Default to Next.js on Vercel with Tailwind unless you have a strong reason otherwise. Pick a minimal state approach (React state, no Redux). Write the stack.md as a short bulleted list.",
        "verify": "stack.md exists with one concrete answer per layer.",
    },
    "003_C3_PROTOTYPE/01_scaffold/02_bootstrap_repo.md": {
        "obj": "Create the project repo and push an empty scaffold to GitHub.",
        "reqs": [
            "New repo created under your GitHub account.",
            "Initial commit pushed to main.",
            "README with one line about what the project is.",
        ],
        "impl": "Run `npx create-next-app@latest canvas` (or the equivalent for your stack choice). Init git, create a private GitHub repo, push. Keep private until c6.",
        "verify": "GitHub shows the repo with at least one commit and a populated README.",
    },
    "003_C3_PROTOTYPE/01_scaffold/03_routing_skeleton.md": {
        "obj": "Set up the empty pages/routes the canvas will use.",
        "reqs": [
            "Home route exists at /.",
            "Canvas route exists at /c/[slug] (or App Router equivalent).",
            "Both render a placeholder with the route name visible.",
        ],
        "impl": "Create app/page.tsx and app/c/[slug]/page.tsx. Each returns a div whose text is the route path. No styling yet.",
        "verify": "Running the dev server, visiting / and /c/test1 shows the corresponding placeholder text.",
    },
    "003_C3_PROTOTYPE/02_entry_points/01_url_entry_point.md": {
        "obj": "Make /c/[slug] actually load something keyed by the slug.",
        "reqs": [
            "A new slug generates a blank canvas state.",
            "Visiting an existing slug loads its saved state.",
            "State persisted in localStorage keyed by slug.",
        ],
        "impl": "In the canvas page, read the slug from the URL. If localStorage[slug] exists, hydrate from it. Otherwise initialize empty state and write it on first edit.",
        "verify": "Typing /c/test1 in the URL bar opens an empty canvas. Refreshing the tab keeps whatever was typed.",
    },
    "003_C3_PROTOTYPE/02_entry_points/02_prompt_entry_point.md": {
        "obj": "Let the user enter a prompt on the home page and land on a canvas seeded with it.",
        "reqs": [
            "A text input on the home page.",
            "Submitting creates a new canvas with a random slug.",
            "The prompt text appears on the new canvas.",
        ],
        "impl": "Add an input + button on the home page. On submit, generate a short slug with nanoid, route to /c/[slug], pass the prompt via query param or initial state.",
        "verify": "Typing \"hello\" on the home page and pressing enter lands on /c/<random> showing \"hello\" as the seed.",
    },
    "003_C3_PROTOTYPE/02_entry_points/03_minimal_canvas_ui.md": {
        "obj": "Put a visible, usable minimum canvas on the /c/[slug] page.",
        "reqs": [
            "A text area or contenteditable block the user can type into.",
            "At least one visible action button.",
            "Styled enough that you would show it to a friend.",
        ],
        "impl": "Place a contenteditable div or textarea in the center. Add a Save button below. Match the visual style of today.html so it feels on brand.",
        "verify": "/c/test1 shows an editable surface, a button, and does not look like a dev stub.",
    },

    # c4 edit loop
    "004_C4_EDIT_LOOP/01_api_wire/01_claude_api_call.md": {
        "obj": "Make one real Anthropic API call from the canvas server.",
        "reqs": [
            "ANTHROPIC_API_KEY loaded from .env.local.",
            "/api/edit route exists.",
            "POST to /api/edit returns 200 with a Claude completion.",
        ],
        "impl": "Run `npm install @anthropic-ai/sdk`. Create app/api/edit/route.ts. Load the key from env. Call messages.create with claude-sonnet-4-6, a hardcoded prompt, and return the response.",
        "verify": "curl POST http://localhost:3000/api/edit returns valid JSON containing a Claude completion.",
    },
    "004_C4_EDIT_LOOP/01_api_wire/02_edit_request_format.md": {
        "obj": "Define the JSON request/response shape the client and Claude share.",
        "reqs": [
            "Shape documented in edit_contract.md.",
            "Request contains at minimum: canvas_content, edit_instruction.",
            "Response contains: new_canvas_content, reasoning.",
        ],
        "impl": "Write edit_contract.md with a sample request and sample response. Update /api/edit to accept that shape. Feed the instruction plus current canvas into Claude and ask for the new canvas back.",
        "verify": "POST /api/edit with the documented request shape returns the documented response shape.",
    },
    "004_C4_EDIT_LOOP/02_ui/01_edit_input.md": {
        "obj": "Give the user a place on the canvas to type an edit instruction.",
        "reqs": [
            "An input field below or beside the canvas.",
            "An Apply button next to it.",
            "Empty input disables the button.",
        ],
        "impl": "Add an input + button row to the canvas page. Disable the button when the input value is empty. Wire the button to call /api/edit with the current canvas content and the input text.",
        "verify": "You can type an instruction and click Apply without errors, and empty input grays out the button.",
    },
    "004_C4_EDIT_LOOP/02_ui/02_edit_apply.md": {
        "obj": "Replace the canvas content with Claude's edited version when Apply is clicked.",
        "reqs": [
            "API response swaps into the canvas on success.",
            "Loading state shown while waiting for the API.",
            "Errors surface visibly (no silent failure).",
        ],
        "impl": "On Apply: set loading true, POST /api/edit, on success replace canvas with new_canvas_content, on failure show an error toast, finally set loading false.",
        "verify": "Typing \"make this a haiku\" changes the canvas content visibly within a few seconds.",
    },
    "004_C4_EDIT_LOOP/02_ui/03_roundtrip_test.md": {
        "obj": "Run the full edit loop 5 times in a row without the app breaking.",
        "reqs": [
            "5 consecutive edits applied on the same canvas.",
            "No errors in the browser console.",
            "Canvas content evolves coherently across the 5 steps.",
        ],
        "impl": "Open a canvas. Type instruction 1, apply. Type instruction 2, apply. Repeat until 5 edits are applied. Screenshot each state into demo/edit_loop/.",
        "verify": "5 screenshots in demo/edit_loop/ showing progression and a clean console at the end.",
    },

    # c5 interviews
    "005_C5_INTERVIEWS/01_prep/01_outreach_list.md": {
        "obj": "Build a named list of 60+ people to reach out to for interviews.",
        "reqs": [
            "60 or more names in outreach_list.csv.",
            "Columns: name, contact channel, relationship tag.",
            "Mix of cold, warm, and community contacts.",
        ],
        "impl": "Pull from LinkedIn connections, past conversations, Discord and Slack communities you are in, school and work networks. Aim for 2x the 30 you actually want to interview so you have buffer for no-shows.",
        "verify": "outreach_list.csv exists with 60+ rows and the three required columns.",
    },
    "005_C5_INTERVIEWS/01_prep/02_interview_script.md": {
        "obj": "Write a repeatable script for 30 minute user interviews.",
        "reqs": [
            "5 to 8 open ended questions.",
            "Sections: warm up, problem, current workaround, magic wand, wrap.",
            "Fits on one printed page.",
        ],
        "impl": "Follow The Mom Test format. No \"would you use this\" questions. All past tense and specific behavior. Save to interviews/script.md.",
        "verify": "interviews/script.md exists, under one printed page, 5 to 8 numbered questions.",
    },
    "005_C5_INTERVIEWS/01_prep/03_scheduling_tool.md": {
        "obj": "Give people one link they can use to book time with you.",
        "reqs": [
            "Cal.com or Calendly account set up.",
            "30 minute slot with 15 minute buffer.",
            "Public booking link saved to interviews/booking_link.txt.",
        ],
        "impl": "Create the account, connect your calendar, set availability windows, pick a short URL, test with an incognito booking and immediate cancel.",
        "verify": "An incognito test booking succeeds end to end, then is cancelled cleanly.",
    },
    "005_C5_INTERVIEWS/02_run/01_interviews_1_to_10.md": {
        "obj": "Complete the first 10 interviews.",
        "reqs": [
            "10 interviews recorded (audio or transcript).",
            "Notes written within 24 hours of each.",
            "Notes filed in interviews/notes/01.md through 10.md.",
        ],
        "impl": "Book back to back via the scheduling link. Record with permission (Otter, Fathom, or phone). After each, spend 15 minutes writing the 3 things that surprised you.",
        "verify": "interviews/notes/ contains 10 files, each with a date, direct quotes, and a surprise list.",
    },
    "005_C5_INTERVIEWS/02_run/02_interviews_11_to_20.md": {
        "obj": "Complete interviews 11 through 20.",
        "reqs": [
            "10 more interviews recorded.",
            "Script revised if patterns emerged from the first 10.",
            "Notes filed as interviews/notes/11.md through 20.md.",
        ],
        "impl": "Book the next batch. Review the first 10 notes before you start, adjust the script if a question is not earning its keep. Record, transcribe, note.",
        "verify": "interviews/notes/ contains 20 files total.",
    },
    "005_C5_INTERVIEWS/02_run/03_interviews_21_to_30.md": {
        "obj": "Hit 30 interviews total.",
        "reqs": [
            "10 more interviews completed (30 total).",
            "Script stable by this point.",
            "All 30 notes exist in interviews/notes/.",
        ],
        "impl": "Same cadence as the prior batches. Stop scheduling once 30 interviews are booked.",
        "verify": "interviews/notes/ contains exactly 30 files.",
    },
    "005_C5_INTERVIEWS/03_synthesize/01_tag_themes.md": {
        "obj": "Tag every interview note with recurring themes to find patterns.",
        "reqs": [
            "interviews/themes.md lists all tags in use.",
            "Each interview file has 3 to 6 tags appended.",
            "At least one tag appears in 10+ interviews.",
        ],
        "impl": "Read all 30 notes in one sitting. Note recurring words and complaints. Define a tag vocabulary in themes.md. Go back and add a tags: line to each note file. Grep to count occurrences.",
        "verify": "themes.md exists, every note file has a tags line, one tag has 10+ hits.",
    },
    "005_C5_INTERVIEWS/03_synthesize/02_summary_report.md": {
        "obj": "Write a one page interview summary that could be shared externally.",
        "reqs": [
            "One markdown page (under 500 words).",
            "Top 3 recurring pains named explicitly.",
            "Top 3 surprise findings named explicitly.",
            "Direct quotes with interview number cited for each point.",
        ],
        "impl": "Write interviews/summary.md. Cite the interview number for every quote. Keep it tight. Ask Claude to compress further once you have a draft.",
        "verify": "interviews/summary.md reads cleanly on one screen and every quote is cited.",
    },

    # c6 waitlist
    "006_C6_WAITLIST/01_landing/01_landing_page.md": {
        "obj": "Ship a public landing page under the brand domain.",
        "reqs": [
            "Live at the domain bought in c2.",
            "Sections: hero, what it is, signup CTA, footer.",
            "Lighthouse performance score above 90.",
        ],
        "impl": "Reuse the waitlist landing style from inPACT-site as a starting point. Swap copy for canvas. Deploy to Vercel and point the custom domain at it.",
        "verify": "Visiting the domain in incognito loads the page with a working signup CTA.",
    },
    "006_C6_WAITLIST/01_landing/02_signup_form.md": {
        "obj": "Capture email signups into a store you own.",
        "reqs": [
            "Email input validates format client-side.",
            "Submissions stored in Supabase, Airtable, or a Google Sheet.",
            "Duplicate emails handled gracefully (no error, friendly message).",
            "Success state shown to the user after submission.",
        ],
        "impl": "Hook the form to a simple POST endpoint or a third party connector. Sanitize and dedupe on insert. Swap to a thank you state on success.",
        "verify": "A test submission appears in the store. A duplicate submission does not error out.",
    },
    "006_C6_WAITLIST/02_drive_signups/01_post_on_social.md": {
        "obj": "Drive your existing audience to the signup page.",
        "reqs": [
            "Live posts on at least 2 channels (X, LinkedIn, mailing list, Discord).",
            "Post includes what it is, who it is for, and the URL.",
            "Posts go up within the same 48 hour window.",
        ],
        "impl": "Write one core post. Adapt tone per channel. Pin the X post. Email the list with a similar message.",
        "verify": "Live posts on 2+ channels with the canvas domain link.",
    },
    "006_C6_WAITLIST/02_drive_signups/02_outreach_to_network.md": {
        "obj": "Personally ask 30 people who would care to sign up and share.",
        "reqs": [
            "30 individual DMs or emails sent (not broadcast).",
            "Each message says why them specifically.",
            "Sends tracked in outreach/log.csv.",
        ],
        "impl": "Use outreach_list.csv from c5 as the source. Keep messages to 3 sentences max. Ask for a signup and optionally a share. Log each send.",
        "verify": "outreach/log.csv has 30 rows with send date and response status.",
    },
    "006_C6_WAITLIST/02_drive_signups/03_track_conversion.md": {
        "obj": "Know how many visitors become signups and where they came from.",
        "reqs": [
            "Analytics installed (Plausible, Vercel, or GA).",
            "UTM parameters on each social and outreach link.",
            "A dashboard or report you can read at a glance.",
        ],
        "impl": "Add the analytics snippet to the landing page. Generate UTM links per channel. Check the dashboard daily for a week.",
        "verify": "Dashboard shows visits and signups grouped by source.",
    },

    # c7 decision
    "007_C7_DECISION/01_gather/01_review_metrics.md": {
        "obj": "Pull the real numbers from all 6 prior checkpoints.",
        "reqs": [
            "Interview count captured.",
            "Waitlist signup count captured.",
            "Time in app per active user captured (if any real users).",
            "All numbers written to decision/metrics.md.",
        ],
        "impl": "Open the analytics dashboard, the signup store, and the interviews folder. Count. Write concrete numbers, not ranges.",
        "verify": "decision/metrics.md contains a numbers-only table.",
    },
    "007_C7_DECISION/01_gather/02_interview_insights.md": {
        "obj": "Revisit the interview summary and extract the top 3 decision inputs.",
        "reqs": [
            "3 insights each written as a one liner.",
            "Each insight cites evidence (interview count plus a quote).",
            "Each insight tagged pro, con, or neutral to shipping.",
        ],
        "impl": "Reread interviews/summary.md. Pick the 3 most decision altering patterns. Write them into decision/insights.md with evidence and a pro/con/neutral tag.",
        "verify": "decision/insights.md lists exactly 3 tagged insights with cited evidence.",
    },
    "007_C7_DECISION/02_decide/01_written_decision.md": {
        "obj": "Write the green/yellow/red decision for the canvas product.",
        "reqs": [
            "One word verdict at the top: GREEN, YELLOW, or RED.",
            "200 to 500 words of reasoning.",
            "Lists what would flip the verdict to a different color.",
        ],
        "impl": "Open decision/decision.md. First line is the verdict. Then: what the metrics say, what the interviews say, what you feel, what would change the answer.",
        "verify": "decision/decision.md exists with a verdict on line one and reasoning below.",
    },
    "007_C7_DECISION/02_decide/02_commit_or_pivot.md": {
        "obj": "Translate the verdict into the next 30 day plan.",
        "reqs": [
            "GREEN path: next quarter commitments listed with dates.",
            "YELLOW path: one scoped experiment defined to flip to green or red.",
            "RED path: wind down plan and what transfers to the next thing.",
            "Plan saved to decision/next_30.md.",
        ],
        "impl": "Based on the verdict, write 3 concrete actions for the next 30 days. Each action has a date and an owner (you). No hypotheticals.",
        "verify": "decision/next_30.md exists with 3 dated concrete actions.",
    },
}


FRONTMATTER_RE = re.compile(r"^---\n(?:.*?\n)---\n", re.DOTALL)


def render_body(task_name: str, data: dict) -> str:
    reqs = "\n".join(f"- [ ] {r}" for r in data["reqs"])
    return (
        f"\n# Task: {task_name}\n\n"
        f"## Objective\n\n{data['obj']}\n\n"
        f"## Requirements\n\n{reqs}\n\n"
        f"## Implementation\n\n{data['impl']}\n\n"
        f"## Done When\n\n- [ ] All requirements met\n- [ ] {data['verify']}\n"
    )


def main() -> int:
    written = 0
    skipped = 0
    errors = 0
    for rel, data in TASKS.items():
        path = FEST_ROOT / rel
        if not path.exists():
            print(f"MISSING: {rel}")
            errors += 1
            continue
        original = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(original)
        if not m:
            print(f"NO FRONTMATTER: {rel}")
            errors += 1
            continue
        frontmatter = m.group(0)
        # Derive task name from existing `# Task: ...` line or file name.
        name_match = re.search(r"^# Task:\s*(.+)$", original, re.MULTILINE)
        task_name = name_match.group(1).strip() if name_match else path.stem
        new_content = frontmatter + render_body(task_name, data)
        if new_content == original:
            skipped += 1
            continue
        path.write_text(new_content, encoding="utf-8")
        written += 1
        print(f"FILLED: {rel}")
    print(f"\n--- {written} filled, {skipped} unchanged, {errors} errors ---")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
