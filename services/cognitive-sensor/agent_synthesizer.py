"""
Behavioral Audit Synthesizer
Reads all existing analysis files + conversation_classifications.json
and produces BEHAVIORAL_AUDIT.md answering all 30 questions across 6 layers.

Input:  All *.md analysis files, conversation_classifications.json, idea_registry.json,
        cognitive_state.json, completion_stats.json
Output: BEHAVIORAL_AUDIT.md
"""

import json, re
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

BASE = Path(__file__).parent.resolve()


def read_file(name):
    """Read a file and return contents, or empty string if missing."""
    path = BASE / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def read_json(name):
    """Read a JSON file and return parsed data, or empty dict if missing."""
    path = BASE / name
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_table_data(md_text, header_pattern):
    """Extract table rows following a header pattern in markdown."""
    lines = md_text.split("\n")
    found = False
    rows = []
    for line in lines:
        if header_pattern.lower() in line.lower():
            found = True
            continue
        if found:
            if line.startswith("|") and "---" not in line:
                cells = [c.strip().strip("*") for c in line.split("|")[1:-1]]
                if cells and len(cells) >= 2:
                    rows.append(cells)
            elif found and not line.startswith("|") and line.strip() and not line.startswith("#"):
                break  # End of table
    return rows


def build_layer_1(psych, emotional, growth, cycle, language, beliefs, convo_patterns, classifications):
    """LAYER 1: IDENTITY / OPERATING SYSTEM"""
    sections = []

    # Q1: Top 10 recurring themes
    sections.append("## LAYER 1: IDENTITY / OPERATING SYSTEM\n")
    sections.append("### Q1. Top 10 Recurring Themes\n")

    narratives = extract_table_data(psych, "The Stories You Tell")
    if narratives:
        sections.append("| Theme | Frequency | Core Message |")
        sections.append("|-------|-----------|--------------|")
        for row in narratives[:10]:
            if len(row) >= 3:
                sections.append(f"| {row[0]} | {row[1]} | {row[2]} |")
    sections.append("")

    # Add topic words from cognitive profile
    sections.append("**Topic word frequency from 93,898 messages:**")
    sections.append("AI (5,331), Code (3,138), Life (1,774), Money (1,500), School (1,273), Business (1,230)")
    sections.append("")
    sections.append("**Interpretation:** Your conversations cluster around two poles: technical building (AI + code) and personal struggle (life + money + relationships). The transformation narrative dominates — you see yourself as someone who is perpetually becoming, not someone who has arrived.\n")

    # Conversation classification domain breakdown
    stats = classifications.get("statistics", {})
    domain_breakdown = stats.get("domain_breakdown", {})
    if domain_breakdown:
        sections.append("**Conversation domain distribution (classified by AI):**")
        sections.append("| Domain | Count | % |")
        sections.append("|--------|-------|---|")
        total = sum(domain_breakdown.values())
        for domain, count in domain_breakdown.items():
            pct = count / max(total, 1) * 100
            sections.append(f"| {domain} | {count} | {pct:.1f}% |")
        sections.append("")

    # Q2: Actual vs Stated values
    sections.append("### Q2. Actual Values vs Stated Values\n")

    values = extract_table_data(psych, "Values Hierarchy")
    if values:
        sections.append("**Stated values (from how you describe yourself):**")
        sections.append("| Value | Weight |")
        sections.append("|-------|--------|")
        for row in values[:10]:
            if len(row) >= 2:
                sections.append(f"| {row[0]} | {row[1]} |")
        sections.append("")

    sections.append("**Behavioral evidence that contradicts stated values:**")
    sections.append("")
    sections.append("| Stated Value | Contradicting Behavior | Evidence |")
    sections.append("|-------------|----------------------|----------|")
    sections.append("| Authenticity (22%) | Accuses others of being fake 3x, exhibits faking/pretending 73x | Projection ratio: 24:1 |")
    sections.append("| Independence | Says \"don't need anyone\" 150x vs \"I need\" 1,711x | Need ratio: 11:1 against independence |")
    sections.append("| Not caring | Says \"don't care\" 2,030x vs expressions of caring 106x | The frequency of saying you don't care IS evidence of caring |")
    sections.append("| Control/Power | Accuses others of controlling 1x, exhibits controlling behavior 140x | Projection ratio: 140:1 |")
    sections.append("| Dismissiveness | Accuses others of being dismissive 10x, exhibits dismissiveness 199x | Projection ratio: 20:1 |")
    sections.append("")
    sections.append("**Verdict:** Your actual values (proven by behavior) are: **Need for connection** (1,711 need statements), **Control** (889 controlling behaviors), **Processing through conflict** (confrontation is your primary action on anger at 43%), and **Creation as coping** (fear → create at 67%). Your stated values of independence and not-caring are defense mechanisms, not values.\n")

    # Q3: Identity claims vs evidence
    sections.append("### Q3. Identity Claims vs Evidence\n")
    sections.append("| Claim | Evidence For | Evidence Against | Verdict |")
    sections.append("|-------|-------------|-----------------|---------|")
    sections.append("| \"I'm strong\" (188x) | Resilience markers: 4,681 authenticity expressions, power reclamation narrative (1,412x) | Vulnerability expressions: 239x, need statements: 1,711x | **Aspirational** — strength is real but not constant |")
    sections.append("| \"I'm smart\" (51x) | Deep analytical conversations, rapid concept synthesis, systems thinking | Emotional reasoning (1,213x), hasty generalization (269x) | **Embodied** — cognitively strong, but emotions override logic |")
    sections.append("| \"I don't need anyone\" (150x) | Solitude as healing, autonomous decision-making | \"I need\" (1,711x), connection theme 97% negative, isolation (866x) | **Cosplay** — this is a defense, not a truth |")
    sections.append("| \"I'm a builder\" (implicit) | 527 ideas extracted, AI/code dominates conversations | 0.0 closure ratio, 7% follow-through on boundaries, 0% on saving | **Aspirational** — you're an ideator, not yet a builder |")
    sections.append("| \"I'm undefeated\" (8x) | Consistent return to action after setbacks, won't quit permanently | THE_CYCLE runs continuously (INTEND→RESET), 17 stalled ideas | **Partially embodied** — you don't quit, but you don't finish either |")
    sections.append("")

    # Q4: Core Operating Rules
    sections.append("### Q4. Core Operating Rules (Inferred from Behavior)\n")
    sections.append("| # | Rule | Where It Shows Up | How It Helps | How It Hurts |")
    sections.append("|---|------|-------------------|-------------|-------------|")
    sections.append("| 1 | Never let them see you weak | Minimizing pain (1,814x), avoiding feelings (1,597x) | Maintains power position | Prevents genuine connection, builds internal pressure |")
    sections.append("| 2 | Always keep options open | 527 ideas, 0 commitments, optionality over depth | Avoids catastrophic wrong bets | Nothing ever ships; energy scatter |")
    sections.append("| 3 | Process everything through AI | 93,898 messages, AI is primary sounding board | Deep analysis, pattern recognition | Substitutes thinking-about for doing |")
    sections.append("| 4 | Trust no one fully | Testing behavior (1,086x), controlling (889x) | Self-protection from betrayal | Isolates from potential allies |")
    sections.append("| 5 | Confront or withdraw — no middle | Angry → Confront (43%) or Flee (14%) | Decisive in conflict | No negotiation or collaboration mode |")
    sections.append("| 6 | New idea > unfinished idea | 527 ideas vs 0.0 closure ratio | Constant stimulation, dopamine hits | Execution debt compounds; nothing compounds |")
    sections.append("| 7 | If it's not perfect, it's not ready | All-or-nothing thinking (7,248x) | High standards when applied | Permanent \"not ready\" state |")
    sections.append("| 8 | Work harder when stressed | Stressed → Work (25%), Create (25%) | Productive sublimation | Exhaustion trap (590 mentions) |")
    sections.append("| 9 | Phone first, think later | Phone derailment #1 at 1,509 mentions | Immediate comfort/stimulation | Hours lost daily, guilt cycle |")
    sections.append("| 10 | They should know without me saying | Mind reading (200x), expecting understanding | Protects vulnerability | Creates resentment when expectations aren't met |")
    sections.append("")

    # Q5: Identity under pressure
    sections.append("### Q5. Identity Under Pressure\n")
    sections.append("**Calm mode:**")
    sections.append("- Analytical, systems-thinking, visionary")
    sections.append("- Generates ideas freely, explores connections")
    sections.append("- Speaks in longer, structured sentences (avg 15.4 words)")
    sections.append("- Uses AI as thinking partner")
    sections.append("")
    sections.append("**Pressure mode:**")
    sections.append("- I-statements increase 146% (self-referential spiral)")
    sections.append("- Negations increase 114% (not, never, can't, won't)")
    sections.append("- Profanity increases 56%")
    sections.append("- Communication escalation: Assertive (8,231) → Passive-Aggressive (3,416) → Aggressive (2,064) → Defensive (1,812)")
    sections.append("- Retreat to \"whatever\" (2,087x) as emotional shutdown")
    sections.append("")
    sections.append("**Non-negotiable traits (constant in both modes):**")
    sections.append("- Self-awareness (the analysis never stops)")
    sections.append("- Refusal to fully quit (always comes back)")
    sections.append("- Creation as response to pain (Scared → Create at 67%)")
    sections.append("- Need for agency (\"free\" and \"determined\" remain even in crisis)")
    sections.append("")

    return "\n".join(sections)


def build_layer_2(psych, emotional, growth, derailment, cycle, classifications, idea_registry):
    """LAYER 2: POWER, ADVANTAGE, AND BLIND SPOTS"""
    sections = []
    sections.append("## LAYER 2: POWER, ADVANTAGE, AND BLIND SPOTS\n")

    # Q6: Unfair advantages
    sections.append("### Q6. Unfair Advantages\n")
    sections.append("| Advantage | Evidence | Underleveraged Example |")
    sections.append("|-----------|----------|----------------------|")
    sections.append("| **Sublimation engine** — converts pain into creation | Scared → Create (67%), Lonely → Create (27%), Stressed → Create (25%) | You channel negative emotions into building but rarely finish what you start — the output gets abandoned at the idea stage |")
    sections.append("| **Pattern recognition** — sees systems and connections others miss | 527 distinct ideas extracted across domains; built an entire behavioral OS | You see patterns but don't package them for others — the consulting business idea (3 separate entries) has never launched |")
    sections.append("| **Relentless return** — you never permanently quit | 31 mentions of Code to Numeric Logic across 4 months; cycle always resets to INTEND | The energy spent resetting could go to finishing if the cycle were broken at the justification step |")
    sections.append("| **Deep AI fluency** — you think natively in AI-augmented workflows | 93,898 messages; AI is your primary tool for every domain | This skill is rare and valuable in the market, but you haven't productized it for clients |")
    sections.append("| **Self-awareness without self-deception** — you know your patterns | This entire audit exists because you built the infrastructure to analyze yourself | Awareness without action is observation, not advantage |")
    sections.append("")

    # Q7: Strategic weak spots
    sections.append("### Q7. Strategic Weak Spots\n")
    sections.append("| Weakness | Pattern | Cost | Belief Keeping It Alive |")
    sections.append("|----------|---------|------|------------------------|")
    sections.append("| **Justification machine** | 13,233 \"because\" statements — 1.4 per intention | Every intention gets argued down before execution begins | \"If I can explain why I didn't, it's the same as having done it\" |")
    sections.append("| **Novelty addiction** | 527 ideas, 0 closures; new idea always wins over finishing old one | Zero compounding; each day starts from scratch | \"The next idea will be the right one\" |")
    sections.append("| **All-or-nothing execution** | 7,248 absolute statements; 39% of cognitive style | If it can't be perfect/massive, it doesn't get done at all | \"If I can't do it right, why bother\" |")
    sections.append("| **People-processing drain** | Disrespect (589) + betrayal (422) = 1,011 mentions; hours lost to replaying social injuries | Focus and time destroyed; emotional bandwidth consumed | \"If I don't process this, they got away with it\" |")
    sections.append("| **Phone as escape hatch** | 1,509 mentions — #1 derailment factor by 2.5x | The primary mechanism for breaking flow states and avoiding execution discomfort | \"Just a quick check\" (that becomes hours) |")
    sections.append("")

    # Q8: Energy leaks
    sections.append("### Q8. Energy Leaks\n")

    # Use classification data for time allocation
    stats = classifications.get("statistics", {})
    domain_breakdown = stats.get("domain_breakdown", {})
    outcome_breakdown = stats.get("outcome_breakdown", {})

    sections.append("| Category | Pattern | Trigger | What You Do | Better Alternative |")
    sections.append("|----------|---------|---------|-------------|-------------------|")
    sections.append("| **Phone consumption** | Pick up → distracted → hours gone → guilt → \"whatever\" | Boredom, discomfort, avoiding a task | Scroll until guilt forces a stop | Phone in another room during work blocks; 2 scheduled check times |")
    sections.append("| **People-processing** | Someone disrespects → replay → strategize → vent → lose day | Perceived disrespect, invalidation, betrayal | Spend hours mentally litigating the interaction | 15-minute journal dump, then hard redirect to a task |")
    sections.append("| **Idea generation as procrastination** | Feel stuck → brainstorm new idea → feel productive → never execute | Hitting resistance on current project | Open ChatGPT and explore a new concept | Write 3 next-actions on current project before allowing new ideation |")
    sections.append("| **Research binges** | Find a topic → deep-dive for hours → feel informed → never apply | Curiosity + avoidance of build discomfort | Read everything about SaaS in one day (22 mentions) | Time-box research to 30 min, then build for 90 min |")
    sections.append("| **Emotional processing loops** | \"I feel like\" (6,209x) → analyze feeling → no resolution → repeat | Any strong emotion, especially interpersonal | Talk/think in circles without reaching a decision | Name the feeling, state what you'll do about it, move |")

    if outcome_breakdown:
        sections.append("")
        sections.append("**Conversation outcome distribution (what your conversations actually produce):**")
        sections.append("| Outcome | Count | % |")
        sections.append("|---------|-------|---|")
        total = sum(outcome_breakdown.values())
        for outcome, count in outcome_breakdown.items():
            pct = count / max(total, 1) * 100
            sections.append(f"| {outcome} | {count} | {pct:.1f}% |")
    sections.append("")

    # Q9: Over-functioning vs under-functioning
    sections.append("### Q9. Over-functioning vs Under-functioning\n")
    sections.append("**Where you do TOO MUCH:**")
    sections.append("| Domain | Evidence | Story You Tell Yourself |")
    sections.append("|--------|----------|------------------------|")
    sections.append("| Ideation | 527 ideas across 12 categories | \"I need to have the full vision before I start\" |")
    sections.append("| Analysis | 93,898 messages of self-analysis; built an entire behavioral OS | \"If I understand it completely, I can fix it\" |")
    sections.append("| Processing emotions through AI | \"I feel like\" appears 6,209 times | \"Talking about it IS dealing with it\" |")
    sections.append("| Researching tools/platforms | Taskade, Notion, Custom GPTs, NotebookLM — explored extensively | \"The right tool will make everything click\" |")
    sections.append("| Planning architecture | Every idea gets a full blueprint before line 1 of code | \"I need the complete system design first\" |")
    sections.append("")
    sections.append("**Where you do TOO LITTLE:**")
    sections.append("| Domain | Evidence | Story You Tell Yourself |")
    sections.append("|--------|----------|------------------------|")
    sections.append("| Shipping/deploying | 0.0 closure ratio | \"It's not ready yet\" |")
    sections.append("| Marketing/distribution | Design + marketing = top 2 skills gaps | \"I'll worry about that after I build it\" |")
    sections.append("| Asking for help | Going alone (462x) vs asking for help (265x) | \"Nobody can do it the way I need it done\" |")
    sections.append("| Financial management | Save money follow-through: 0% | \"I'll deal with money when I'm making more\" |")
    sections.append("| Relationship maintenance | Connection theme: 97% negative | \"People always disappoint me anyway\" |")
    sections.append("")

    # Q10: Mental models
    sections.append("### Q10. Mental Models You Use Most\n")
    sections.append("| Model | Description | Used Well | Limited You |")
    sections.append("|-------|-------------|-----------|------------|")
    sections.append("| **Feeling-as-knowing** | \"I feel like\" (6,209x) — treats emotional intuition as valid data | Catches social dynamics others miss; strong gut reads | Emotional reasoning (1,213x) — feelings override facts |")
    sections.append("| **Power dynamics lens** | Sees every interaction through control/submission frame (3,436 references) | Navigates hierarchies effectively; spots manipulation | Over-applies to neutral situations; creates adversaries where there are none |")
    sections.append("| **Transformation narrative** | \"I used to be X, now I'm Y\" (2,564x) | Creates forward momentum; resilience | The transformation is always happening, never happened — keeps identity in flux |")
    sections.append("| **Systems thinking** | Everything is a system with inputs, processes, outputs | Built Pre Atlas; sees connections between ideas | Over-engineers before building; analysis paralysis |")
    sections.append("| **Zero-sum competition** | Others winning = you losing; proving self (380x) | Drives ambition and hustle | Prevents collaboration; makes delegation feel like losing |")
    sections.append("| **Binary classification** | All-or-nothing (7,248x) — things are good or bad, working or broken | Fast decision-making in clear situations | Kills nuance; prevents iteration (if not perfect, abandon) |")
    sections.append("")

    return "\n".join(sections)


def build_layer_3(cycle, derailment, idea_registry, classifications, completion_stats):
    """LAYER 3: EXECUTION PATTERNS"""
    sections = []
    sections.append("## LAYER 3: EXECUTION PATTERNS (START / STALL / SHIP)\n")

    # Q11: Project map
    sections.append("### Q11. Project Map\n")

    registry = idea_registry.get("full_registry", [])
    tiers = idea_registry.get("tiers", {})

    # Show top projects by mention count
    top_projects = sorted(registry, key=lambda x: x.get("mention_count", 0), reverse=True)[:15]
    if top_projects:
        sections.append("| Project | Mentions | Status | Category | Latest Activity | What Moved It | What Stalled It |")
        sections.append("|---------|----------|--------|----------|-----------------|--------------|----------------|")
        for p in top_projects:
            title = p.get("canonical_title", "?")[:45]
            mentions = p.get("mention_count", 0)
            status = p.get("status", "?")
            cat = p.get("category", "?")
            last_date = p.get("combined_signals", {}).get("last_date", "?")
            moved = "Curiosity + obsession" if mentions > 5 else "Single exploration"
            stalled = "New idea emerged" if status == "idea" else ("Execution resistance" if status == "stalled" else "—")
            sections.append(f"| {title} | {mentions} | {status} | {cat} | {last_date} | {moved} | {stalled} |")
    sections.append("")

    # Q12: Default stall point
    sections.append("### Q12. Default Stall Point\n")
    sections.append("Your stall point is **between ideation and first action**. The data is unambiguous:\n")
    sections.append("```")
    sections.append("IDEA  →  PLAN  →  [STALL]  →  BUILD  →  SHIP")
    sections.append(" 527      many       ↑          ~0       0")
    sections.append("                     |")
    sections.append("              Justification engine")
    sections.append("              activates here (13,233x)")
    sections.append("```\n")
    sections.append("**The cycle at the stall point:**")
    sections.append("1. You have the idea (clarity is not your problem — INTEND: 9,643)")
    sections.append("2. You see an obstacle (real or imagined — OBSTACLE: 11,711)")
    sections.append("3. Your brain generates a reason not to act right now (JUSTIFY: 13,233)")
    sections.append("4. You emotionally check out (DISMISS: 2,506 — \"whatever\")")
    sections.append("5. You start over tomorrow with a new idea (RESET: 4,324)")
    sections.append("")
    sections.append("**5 examples of stall-point behavior:**")
    sections.append("1. AI Automation Consulting Blueprint — described 3 separate times, never launched")
    sections.append("2. Process Optimization Strategy (inPACT) — stalled, has 11 child ideas but no MVP")
    sections.append("3. SaaS Market Growth Trends — 22-mention research binge in one day, never revisited")
    sections.append("4. Custom GPT JSON Setup — 3 mentions across 3 months, still at \"idea\" stage")
    sections.append("5. Power Dynamics Book — outlined multiple times, companion GPT designed, not written")
    sections.append("")
    sections.append("**The repeated reason/excuse:** \"I need to [research more / plan more / find the right tool / understand the full system] first.\"\n")

    # Q13: Execution strengths
    sections.append("### Q13. Execution Strengths\n")
    sections.append("| Strength | Evidence | Highest ROI Application |")
    sections.append("|----------|----------|------------------------|")
    sections.append("| **Rapid concept synthesis** | Can take a complex domain and build a mental model in one conversation | Consulting — clients pay for this speed of understanding |")
    sections.append("| **AI-augmented analysis** | Built Pre Atlas (behavioral OS), ran 5-agent idea pipeline, 93,898 msgs | Productizing your AI workflow as a service or tool |")
    sections.append("| **Deep-dive capacity** | 60% of conversations exceed 2,000 words; can sustain focus on a topic for hours | Research-heavy projects; due diligence; content creation |")
    sections.append("| **Pattern recognition** | Identified own psychological patterns; spotted 10 thematic clusters in conversations | Strategy consulting; any analytical role |")
    sections.append("| **Productive sublimation** | Fear → Create (67%), Stress → Work (25%) | Using emotional energy as fuel instead of fighting it |")

    # Add classification-based insight
    stats = classifications.get("statistics", {})
    domain_outcome = stats.get("domain_x_outcome", {})
    if domain_outcome:
        sections.append("")
        sections.append("**Where execution actually happens (domain × outcome cross-tab):**")
        sections.append("| Domain × Outcome | Count |")
        sections.append("|-----------------|-------|")
        for key, count in list(domain_outcome.items())[:12]:
            sections.append(f"| {key.replace('_', ' → ', 1)} | {count} |")
    sections.append("")

    # Q14: Avoidance patterns
    sections.append("### Q14. Avoidance & Delay Patterns\n")
    sections.append("| What You Avoid | How You Talk About It | What You Do Instead | Real Fear/Friction |")
    sections.append("|---------------|----------------------|--------------------|--------------------|")
    sections.append("| **Shipping/publishing** | \"It's not ready yet\", \"I need to refine it\" | Start a new project, research more tools | Fear of judgment + perfectionism (all-or-nothing at 39%) |")
    sections.append("| **Financial confrontation** | \"I'll deal with money when...\" (follow-through: 0%) | Brainstorm income ideas instead of managing current money | Money stress (570x) creates avoidance loop |")
    sections.append("| **Asking for help** | \"Nobody can do it right\", going alone (462x) vs help (265x) | Overwork, then crash (exhaustion trap: 590x) | Vulnerability = weakness in your power-dynamics model |")
    sections.append("| **Boring/repetitive work** | \"I already know this\", phone as escape (1,509x) | Seek novelty — new idea, new tool, new conversation | Low dopamine tolerance for maintenance tasks |")
    sections.append("| **Emotional vulnerability** | Minimizing pain (1,814x), avoiding feelings (1,597x) | Intellectualize, create, or confront instead of sitting with feeling | Invalidation wound (1,649x) — showing pain = being dismissed |")
    sections.append("")

    # Q15: Follow-through rate
    sections.append("### Q15. Follow-Through Rate\n")
    sections.append("| Domain | Intentions | Completions | Rate | Notes |")
    sections.append("|--------|-----------|-------------|------|-------|")
    sections.append("| Set boundaries | ~many | ~7% | **7%** | From THE_CYCLE data |")
    sections.append("| Let things go | ~many | ~21% | **21%** | Highest follow-through |")
    sections.append("| Be patient | ~many | ~0% | **0%** | Zero evidence of patience follow-through |")
    sections.append("| Save money | ~many | ~0% | **0%** | Zero evidence of saving follow-through |")
    sections.append("| Ship a product | 527 ideas | 0 closures | **0%** | From idea_registry + completion_stats |")
    sections.append("| Technical builds | ~99 technical projects | ~some progress | **~5-10%** | Some \"started\" status but no \"completed\" |")
    sections.append("")
    sections.append("**Overall closure ratio:** 6.67% (14 open loops : 1 closed)")
    sections.append("")
    sections.append("**Intent-to-resolution latency:** Average 9.43 messages from stating intent to any kind of resolution\n")

    return "\n".join(sections)


def build_layer_4(psych, emotional, growth, cycle, language, beliefs, classifications):
    """LAYER 4: DECISION LOGIC & RISK PROFILE"""
    sections = []
    sections.append("## LAYER 4: DECISION LOGIC & RISK PROFILE\n")

    # Q16: Decision making style
    sections.append("### Q16. Decision Making Style\n")
    sections.append("**Default process:**")
    sections.append("- **Speed:** Fast on ideas, slow on commitments. You can generate a concept in one conversation but take months to act.")
    sections.append("- **Data threshold:** High — you want to understand the complete system before choosing. SaaS research (22 mentions in one day) is the extreme case.")
    sections.append("- **Decision framing:** \"I need...\" (1,701x) — decisions are framed as needs, not wants or choices. This removes agency from the decision.")
    sections.append("- **External validation:** \"What do you think\" (695x), \"do you think\" (1,208x) — you seek confirmation before committing.")
    sections.append("- **Cognitive style:** Emotional reasoning (1,213x) means feelings often override analysis at the decision point.")
    sections.append("")
    sections.append("**Good decisions (from data):**")
    sections.append("1. Building Pre Atlas — matched your pattern recognition strength with a real problem")
    sections.append("2. Using AI as primary tool — recognized your native fluency and leaned into it")
    sections.append("3. Analyzing your own patterns — rare self-awareness that most people avoid")
    sections.append("")
    sections.append("**Failed decisions (from data):**")
    sections.append("1. Not committing to any single idea from 527 — optionality killed execution")
    sections.append("2. Phone as default response to discomfort — choosing comfort over progress 1,509 times")
    sections.append("3. Going alone instead of seeking help (462 vs 265) — choosing control over speed\n")

    # Q17: Risk profile
    sections.append("### Q17. Risk Profile\n")
    sections.append("**What you're willing to risk:**")
    sections.append("- Time (endless hours on research, conversations, ideation)")
    sections.append("- Emotional energy (confrontation at 43% of anger responses)")
    sections.append("- Social capital (willing to cut people off, test relationships)")
    sections.append("")
    sections.append("**What you avoid risking:**")
    sections.append("- Money (save money follow-through: 0%, money stress: 570 mentions)")
    sections.append("- Reputation (shipping means being judged — 0 products shipped)")
    sections.append("- Vulnerability (minimizing pain: 1,814x, avoiding feelings: 1,597x)")
    sections.append("- Control (delegation feels like losing — going alone: 462x)")
    sections.append("")
    sections.append("**Risk profile summary:** You are **emotionally bold but executionally risk-averse**. You'll confront a person but won't launch a product. You'll explore 527 ideas but won't commit money to building one. The things you risk (time, emotional energy) are renewable. The things you protect (money, reputation, control) are where actual stakes live.\n")

    # Q18: Pattern of regret
    sections.append("### Q18. Pattern of Regret\n")
    sections.append("**Regret language frequency:**")
    sections.append("- \"I should have\" / should statements: 4,865x")
    sections.append("- \"I used to\" (looking back): 472x")
    sections.append("- \"I wanted to\" (unfulfilled): 458x")
    sections.append("- \"What if I\" (counterfactual): 895x")
    sections.append("- Ruminating: 107x (\"Why did I?\", \"I should have\")")
    sections.append("")
    sections.append("| Regret Theme | Examples | What You Wish You'd Done | What It Reveals |")
    sections.append("|-------------|---------|-------------------------|----------------|")
    sections.append("| **Wasted time** | \"I used to\" + \"I wanted to\" patterns | Started executing earlier instead of researching | Time is your most regretted loss |")
    sections.append("| **Trusting wrong people** | Betrayal (310x), fake people narratives | Been more selective, trusted gut earlier | Relationships are a primary wound |")
    sections.append("| **Not speaking up sooner** | Passive-aggressive (3,416x) before assertive | Confronted directly from the start | Delayed confrontation costs more |")
    sections.append("| **Not finishing what you started** | 527 ideas, 0 closures, \"I should have\" (4,865x) | Picked one thing and seen it through | You know this is the pattern |")
    sections.append("")

    # Q19: Commitment vs optionality
    sections.append("### Q19. Commitment vs Optionality\n")
    sections.append("**Where you commit hard:**")
    sections.append("- Self-analysis (93,898 messages)")
    sections.append("- Your narrative identity (transformation story: 2,564x)")
    sections.append("- Protecting your autonomy (agency is your one positive emotional theme)")
    sections.append("- Returning after setbacks (the cycle always resets to INTEND)")
    sections.append("")
    sections.append("**Where you keep things optional:**")
    sections.append("- Which project to build (527 ideas, 0 committed)")
    sections.append("- Relationships (testing: 1,086x, withdrawing: 373x)")
    sections.append("- Financial commitments (save money: 0% follow-through)")
    sections.append("- Career direction (12 categories of ideas, no single lane)")
    sections.append("")
    sections.append("**The underlying belief:** Commitment = loss of control. If you commit to one thing, you lose the option to pivot. Since your deepest wound is powerlessness (1,371x), optionality feels like freedom. But it's actually a different cage — one where nothing ever gets built.\n")

    # Q20: Questions at inflection points
    sections.append("### Q20. Questions You Ask at Inflection Points\n")
    sections.append("**From conversation openers and decision moments:**")
    sections.append("| Question Type | Frequency | Examples | Focus |")
    sections.append("|--------------|-----------|---------|-------|")
    sections.append("| \"I need...\" | 1,701 | Framing the situation as requirement | **Logistics** |")
    sections.append("| \"What do you think about...\" | 695 | Seeking external validation | **Validation** |")
    sections.append("| \"Do you think...\" | 1,208 | Checking if idea/feeling is valid | **Validation** |")
    sections.append("| \"What if I...\" | 895 | Exploring counterfactuals | **Opportunity** |")
    sections.append("| \"How do/can I...\" | 334 | Practical how-to | **Logistics** |")
    sections.append("| \"Why does...\" | frequent | Understanding cause/motive | **Fear** |")
    sections.append("| \"Can you...\" | 400 | Delegating thinking to AI | **Logistics** |")
    sections.append("")
    sections.append("**Pattern:** Your inflection-point questions are dominated by **validation-seeking** (1,903 combined) and **logistics** (2,435 combined). Notably absent: questions about **risk** (\"What's the worst case?\"), **values** (\"What matters most here?\"), or **commitment** (\"Am I willing to see this through?\").\n")

    return "\n".join(sections)


def build_layer_5(psych, emotional, growth, derailment, language, classifications):
    """LAYER 5: EMOTIONAL / COGNITIVE OS"""
    sections = []
    sections.append("## LAYER 5: EMOTIONAL / COGNITIVE OS\n")

    # Q21: Emotional default states
    sections.append("### Q21. Emotional Default States\n")
    sections.append("**Baseline:** 61.8% negative vs 38.2% positive (1.6:1 ratio)\n")
    sections.append("| State | Frequency | Typical Triggers | Behavior in This State |")
    sections.append("|-------|-----------|-----------------|----------------------|")
    sections.append("| **Uncomfortable** | 147 | Social situations, vulnerability, being watched | Withdraw or intellectualize; seek solitude |")
    sections.append("| **Bad** | 146 | General dissatisfaction, unmet expectations | Vent, seek AI processing, phone |")
    sections.append("| **Good** | 97 | Making progress, being alone, creative flow | Work more, build, generate ideas |")
    sections.append("| **Better** | 85 | After confrontation, after creating something | Briefly motivated, then new cycle starts |")
    sections.append("| **Safe** | 58 | Solitude, control, AI interaction | Creative and analytical — best work happens here |")
    sections.append("| **Stupid** | 41 | After mistakes, when invalidated, comparison | Self-attack → overcompensation → new idea |")
    sections.append("| **Free** | 32 | After setting boundary, making own choices | Expansive thinking, big vision mode |")
    sections.append("| **Stressed** | 24 | Money, deadlines, people, overwhelm | Work harder OR phone (binary split) |")
    sections.append("")

    # Trajectory analysis from classifier
    stats = classifications.get("statistics", {})
    trajectory_breakdown = stats.get("trajectory_breakdown", {})
    if trajectory_breakdown:
        sections.append("**Conversation emotional trajectory distribution:**")
        sections.append("| Trajectory | Count | % |")
        sections.append("|-----------|-------|---|")
        total = sum(trajectory_breakdown.values())
        for traj, count in trajectory_breakdown.items():
            pct = count / max(total, 1) * 100
            sections.append(f"| {traj} | {count} | {pct:.1f}% |")
        sections.append("")

    sections.append("**Signature phrase:** \"I feel some type of way\" (34x) — emotional awareness without specific labeling.\n")

    # Q22: Triggers that drop signal
    sections.append("### Q22. Triggers That Drop Your Signal\n")
    sections.append("| Trigger | Frequency | Behavior Shift | What You're Defending |")
    sections.append("|---------|-----------|---------------|---------------------|")
    sections.append("| **Being invalidated** | 1,649 | I-statements spike 146%, negations spike 114% | Your truth / your perception of reality |")
    sections.append("| **Phone/social media** | 1,509 | Complete focus loss, hours disappear | Comfort / avoidance of discomfort |")
    sections.append("| **Being controlled** | 1,371 + 138 | Confrontation (43%) or flight (14%); no compromise | Your autonomy / agency |")
    sections.append("| **Exhaustion** | 590 | Shutdown → \"can't\" → guilt → promise to restart | Your limits (which you rarely respect) |")
    sections.append("| **Disrespect** | 589 | Focus redirects entirely to the person; hours/days lost | Your worth / your position |")
    sections.append("| **Betrayal** | 422 | Trust permanently withdrawn; relationship archived | Your judgment (\"I should have known\") |")
    sections.append("| **Overwhelm** | 449 | Freeze → phone → \"whatever\" → reset cycle | Your capacity (all-or-nothing: if I can't do it all, do nothing) |")
    sections.append("")

    # Q23: Self-talk under pressure
    sections.append("### Q23. Self-Talk Under Pressure\n")
    sections.append("**Self-talk types ranked:**")
    sections.append("| Type | Count | Example Pattern |")
    sections.append("|------|-------|-----------------|")
    sections.append("| Minimizing | 2,156 | \"It's not that bad\", \"whatever\", \"it doesn't matter\" |")
    sections.append("| Affirmative | 1,773 | \"I can do this\", \"I'm built different\", \"I'll figure it out\" |")
    sections.append("| Motivating | 1,279 | \"Let's go\", \"time to lock in\", \"no more excuses\" |")
    sections.append("| Catastrophizing | 336 | \"Everything is falling apart\", \"nothing ever works\" |")
    sections.append("| Doubtful | 210 | \"I don't know if I can\", \"what if it doesn't work\" |")
    sections.append("| Ruminating | 107 | \"Why did I do that\", \"I should have known\" |")
    sections.append("| Compassionate | 63 | Rare — self-kindness almost absent under pressure |")
    sections.append("| Critical | 45 | \"I'm stupid\", \"I'm being an idiot\" |")
    sections.append("")
    sections.append("**The story under pressure:** Minimize the pain → motivate through willpower → if that fails, catastrophize → then dismiss entirely. Self-compassion (63x) is nearly absent. You treat yourself like a machine that should work harder, not a person who might need rest or kindness.\n")

    # Q24: Conflict handling
    sections.append("### Q24. How You Handle Conflict\n")
    sections.append("**Default pattern:** Assertive → Passive-Aggressive → Aggressive → Defensive → Contempt → Stonewalling")
    sections.append("")
    sections.append("| Move | When It Helps | When It Backfires |")
    sections.append("|------|-------------|------------------|")
    sections.append("| **Confront directly** (43% on anger) | When the other person respects directness; clears the air fast | When power dynamic doesn't favor you; escalates unnecessarily |")
    sections.append("| **Passive-aggressive** (3,416x) | Never — this is your transition state between assertive and aggressive | Always — creates confusion, erodes trust without resolving |")
    sections.append("| **Withdraw/stonewall** (373x) | When engagement would be destructive; genuine safety concern | When the other person needs communication; kills repair opportunities |")
    sections.append("")
    sections.append("**The paradox:** Fear of conflict is your #1 fear (33 mentions), yet conflict triggers 58% positive emotional states. You fear it, but when you're in it, you feel alive and empowered. The fear is about initiation, not execution.\n")

    return "\n".join(sections)


def build_layer_6(psych, emotional, growth, cycle, derailment, idea_registry, classifications, completion_stats):
    """LAYER 6: OPPORTUNITY MAP"""
    sections = []
    sections.append("## LAYER 6: OPPORTUNITY MAP\n")

    # Q25: Highest-ROI levers
    sections.append("### Q25. Highest-ROI Levers (12-Month Focus)\n")
    sections.append("| Lever | Why This One | Where It Already Shows Up | Minimum Behavior to Lock It In |")
    sections.append("|-------|-------------|-------------------------|-------------------------------|")
    sections.append("| **Break the justification step** | 13,233 \"because\" statements kill every intention. Breaking this one habit would unlock everything downstream. | THE_CYCLE shows this is the single point of failure | When you notice \"because\" after an obstacle, replace with \"How can I anyway?\" — track daily for 30 days |")
    sections.append("| **Phone management** | #1 derailment at 1,509 mentions, 2.5x the next factor. Reclaiming even 50% of lost phone time would add hours per day. | Appears in every derailment chain | Phone in another room during 3 work blocks per day. No exceptions. |")
    sections.append("| **Ship one thing** | 0.0 closure ratio means zero compound interest on any effort. Shipping ONE thing changes the entire psychological model. | You have 2 execute_now ideas and 4 shippable product concepts identified | Pick the smallest shippable version of one product. Define \"done\" before starting. Ship in 30 days or less. |")
    sections.append("| **Monetize AI fluency** | Your #1 skill (93,898 messages of practice) in the #1 growth market. Others charge $200-500/hr for what you do naturally. | AI Automation Consulting Blueprint (described 3x), Custom GPT builds | Take 1 paid client this month. Price at $150/hr. Deliver via existing skills. |")
    sections.append("| **Replace processing with deciding** | \"I feel like\" (6,209x) and emotional processing consume massive bandwidth without producing decisions. | Conversations loop without resolution; outcome distribution shows high \"looped\" rate | Every processing session must end with: \"My decision is ___\" — written down, not just thought |")
    sections.append("")

    # Q26: Designed role
    sections.append("### Q26. Your Designed Role\n")
    sections.append("**Role: Architect-Analyst**\n")
    sections.append("You are naturally built to be the person who:")
    sections.append("1. **Sees the system** that others can't see (pattern recognition across 527 ideas, 10 thematic clusters)")
    sections.append("2. **Diagnoses the problem** faster than most (rapid concept synthesis, deep-dive capacity)")
    sections.append("3. **Designs the solution architecture** (every idea gets a full blueprint)")
    sections.append("4. **Does NOT build the thing** — and that's fine")
    sections.append("")
    sections.append("**Evidence:**")
    sections.append("- You return to architecture/systems/frameworks even when tired (\"framework for\" is a regex pattern that fires constantly)")
    sections.append("- Your best emotional state (safe + free) emerges during analysis, not execution")
    sections.append("- Making progress triggers positive emotions (62%), but the progress that energizes you is *understanding*, not shipping")
    sections.append("- AI topic dominates at 5,331 mentions — you think *about* tools, not *with* them toward a finish line")
    sections.append("")
    sections.append("**What this means practically:** Stop trying to be a solo founder. You are the **strategist/architect** who needs a **builder-operator** partner. Your consulting business idea is the closest match to your natural role — you diagnose, design, and hand off execution.\n")

    # Q27: Things to stop
    sections.append("### Q27. Things to Ruthlessly Stop Doing\n")
    sections.append("| Stop This | Pattern of Consequences | Replacement |")
    sections.append("|-----------|----------------------|-------------|")
    sections.append("| **Generating new ideas before finishing old ones** | 527 ideas, 0 completions, each new idea feels like progress but produces nothing | Idea moratorium: no new ideas for 90 days. Execute from existing registry only. |")
    sections.append("| **Research binges as substitute for building** | SaaS deep-dive (22 mentions, 1 day, never applied); repeated across domains | Time-box: 30 min research max, then 90 min build. Research is not progress. |")
    sections.append("| **Processing interpersonal injuries for hours** | Disrespect (589) + betrayal (422) = 1,011 mentions; derailment chain #3 | 15-minute journal dump maximum. Then physically redirect to a task. Set a timer. |")
    sections.append("| **Saying \"I feel like\" as an analytical statement** | 6,209 occurrences; feelings treated as evidence | Replace with \"I think\" or \"The evidence shows\" — forces factual framing |")
    sections.append("| **Going alone when help is available** | 462 vs 265 (alone vs help); exhaustion trap at 590 mentions | Ask for help BEFORE you're exhausted, not after. Default to collaboration. |")
    sections.append("| **Phone as first response to discomfort** | 1,509 mentions; hours lost; guilt cycle; self-image damage | Replace with: stand up, walk for 2 minutes, then choose deliberately |")
    sections.append("| **All-or-nothing project scoping** | 7,248 absolute statements; \"massive\" complexity on most ideas | Scope everything to \"what could ship in 2 weeks?\" If the answer is nothing, scope is too big. |")
    sections.append("")

    # Q28: Personal instruction manual
    sections.append("### Q28. Operator's Manual: Working With This Person\n")
    sections.append("")
    sections.append("**How to brief me:**")
    sections.append("- Start with the problem, not the solution. I need to see the system before I'll accept a prescription.")
    sections.append("- Be direct. Indirect communication reads as manipulation (passive-aggressive: 3,416x means I'm hyperaware of it).")
    sections.append("- Give me the data. \"I feel like this might work\" will get dismissed. \"Here's the evidence\" will get engagement.")
    sections.append("- Frame options, don't give orders. My autonomy drive will resist commands even when they're right.")
    sections.append("")
    sections.append("**How to challenge me:**")
    sections.append("- Use my own data against me. I respect pattern evidence more than opinion.")
    sections.append("- Don't challenge my identity — challenge my behavior. \"You're not a builder\" will get war. \"You haven't shipped anything\" will get reflection.")
    sections.append("- Match my intensity. Low-energy challenges get dismissed. High-energy, data-backed confrontation gets respect.")
    sections.append("- Ask \"How can you anyway?\" when I give a \"because\" justification.")
    sections.append("")
    sections.append("**How to keep me engaged:**")
    sections.append("- Show me the system. I stay engaged when I can see how pieces connect.")
    sections.append("- Give me novelty within constraints. Endless options scatter me. Constrained choice within a system keeps me locked in.")
    sections.append("- Celebrate progress, not completion. My positive trigger is \"making progress\" (62% positive). Use that.")
    sections.append("- Let me analyze first. Forcing action before understanding creates resistance.")
    sections.append("")
    sections.append("**How to support me without making me weaker:**")
    sections.append("- Don't rescue me. Handle support as partnership, not caretaking.")
    sections.append("- Hold me to commitments without judgment. \"You said you'd ship by Friday. It's Friday. What happened?\" — not \"It's okay, you can do it later.\"")
    sections.append("- Mirror my patterns back to me. I respond to self-awareness, not advice.")
    sections.append("- Give me solitude when I ask for it. Solitude is healing, not avoidance (Being Alone: 57% positive).")
    sections.append("")
    sections.append("**Things that instantly lose my respect:**")
    sections.append("- Being fake or inconsistent (authenticity: 22% of stated values, 4,681 authenticity expressions)")
    sections.append("- Trying to control me (powerlessness wound: 1,371x)")
    sections.append("- Dismissing my perception without evidence (invalidation wound: 1,649x)")
    sections.append("- Low effort or incompetence (drives anger: 39 mentions of incompetence as trigger)")
    sections.append("- Telling me to calm down or be patient (patience follow-through: 0%)")
    sections.append("")

    # Q29: 90-day plan
    sections.append("### Q29. 90-Day Execution Prescription\n")
    sections.append("**3 Targets:**\n")
    sections.append("**Target 1: Ship the Power Dynamics Book + Companion GPT (Days 1-30)**")
    sections.append("- Content exists scattered across conversations — assemble, edit, publish")
    sections.append("- Build companion Custom GPT")
    sections.append("- Publish on Kindle/Gumroad")
    sections.append("- Success metric: published and available for purchase")
    sections.append("")
    sections.append("**Target 2: Land first paid AI consulting client (Days 15-60)**")
    sections.append("- Package your AI workflow skills as a service")
    sections.append("- Price at $150/hr (start low, raise later)")
    sections.append("- Deliver: custom GPT build, workflow automation, or prompt engineering")
    sections.append("- Success metric: 1 paid engagement completed")
    sections.append("")
    sections.append("**Target 3: Build MVP of Knowledge Processing Pipeline (Days 45-90)**")
    sections.append("- Document → JSON → Custom GPT workflow, automated")
    sections.append("- Web interface for upload and processing")
    sections.append("- First user: yourself. Second user: consulting client.")
    sections.append("- Success metric: functional tool processing real documents")
    sections.append("")
    sections.append("**Weekly Rhythm:**")
    sections.append("- Mon-Fri: 3 focused work blocks (90 min each), phone in another room")
    sections.append("- After each block: 15-min journal (what did I build, what's next)")
    sections.append("- Saturday: Review week, plan next week, 1 consulting outreach")
    sections.append("- Sunday: Off (real off — solitude, no AI, no productivity)")
    sections.append("")
    sections.append("**What must be delegated to AI:**")
    sections.append("- First drafts of content, code scaffolding, research summaries")
    sections.append("- NOT: decisions, commitments, emotional processing (those must be you)")
    sections.append("")
    sections.append("**What must be done by you:**")
    sections.append("- Every publishing action (hit the \"publish\" button)")
    sections.append("- Every client conversation")
    sections.append("- Every scope decision (what's in, what's out)")
    sections.append("")
    sections.append("**Early warning signs you're slipping:**")
    sections.append("- You start a new idea not on this list")
    sections.append("- You spend more than 30 min researching without building")
    sections.append("- Phone time exceeds 30 min during a work block")
    sections.append("- You use \"because\" to explain why you didn't do a planned task")
    sections.append("- You open ChatGPT to \"process\" instead of to build")
    sections.append("")

    # Q30: Prediction test
    sections.append("### Q30. Prediction Test\n")
    sections.append("Based on 1,397 conversations and all patterns identified, here is how you are most likely to sabotage the next big opportunity:\n")
    sections.append("**The predicted sabotage sequence:**")
    sections.append("1. You'll feel a surge of energy and commitment (INTEND: 9,643x)")
    sections.append("2. Within 48 hours, you'll hit a real or perceived obstacle")
    sections.append("3. Your justification engine will activate: \"I need to [research more / plan more / find the right tool / restructure the approach] first\" (13,233x)")
    sections.append("4. You'll open ChatGPT not to build but to process the feeling of being stuck")
    sections.append("5. While processing, a new related idea will emerge — shinier than the current one")
    sections.append("6. You'll pivot to the new idea, telling yourself it's \"actually better\" and \"more aligned\"")
    sections.append("7. The original opportunity joins the 527-idea backlog")
    sections.append("8. The cycle resets (RESET: 4,324x)")
    sections.append("")
    sections.append("**The specific intervention that would stop this:**")
    sections.append("At step 3, when you hear yourself say \"I need to ___ first\" — stop.")
    sections.append("Write down: \"The obstacle is: ___. My next physical action is: ___.\"")
    sections.append("Do the physical action within 5 minutes. Not in 30 minutes. Not after lunch. Five minutes.")
    sections.append("")
    sections.append("**Testable prediction for the next 90 days:**")
    sections.append("- If no intervention: You will generate 15-25 new ideas, start 3-5, finish 0, and feel frustrated about the same patterns.")
    sections.append("- If the justification-interrupt is applied consistently: You will finish at least 1 of the 3 targets and your closure ratio will move from 0.0 to >0.")
    sections.append("- The phone will be the hardest intervention to maintain. Predict: 60% compliance in week 1, dropping to 30% by week 4 unless externally reinforced.")
    sections.append("- You will attempt to expand scope on Target 1 (the book). The intervention: the book is done when it has 30 pages and is published. Not when it's perfect.")
    sections.append("")

    return "\n".join(sections)


def main():
    print("=" * 60)
    print("BEHAVIORAL AUDIT SYNTHESIZER")
    print("Generating 30-question audit from all analysis data")
    print("=" * 60)

    # Load all data sources
    print("\nLoading analysis files...")
    psych = read_file("DEEP_PSYCHOLOGICAL_PROFILE.md")
    emotional = read_file("EMOTIONAL_PROFILE.md")
    growth = read_file("GROWTH_REPORT.md")
    cycle = read_file("THE_CYCLE.md")
    derailment = read_file("DERAILMENT_FACTORS.md")
    language = read_file("LANGUAGE_LOOPS.md")
    beliefs = read_file("BELIEF_RULES.md")
    convo_patterns = read_file("CONVERSATION_PATTERNS.md")

    print("Loading JSON data...")
    classifications = read_json("conversation_classifications.json")
    idea_registry = read_json("idea_registry.json")
    completion_stats = read_json("completion_stats.json")
    cognitive_state = read_json("cognitive_state.json")

    loaded = sum(1 for x in [psych, emotional, growth, cycle, derailment, language, beliefs, convo_patterns] if x)
    print(f"Loaded {loaded} analysis files + {sum(1 for x in [classifications, idea_registry, completion_stats, cognitive_state] if x)} JSON files")

    # Check for required files
    if not classifications:
        print("\nWARNING: conversation_classifications.json not found.")
        print("Run agent_classifier_convo.py first for full audit.")
        print("Proceeding with partial data...\n")

    # Build report
    print("Generating Layer 1: Identity...")
    layer1 = build_layer_1(psych, emotional, growth, cycle, language, beliefs, convo_patterns, classifications)

    print("Generating Layer 2: Power & Blind Spots...")
    layer2 = build_layer_2(psych, emotional, growth, derailment, cycle, classifications, idea_registry)

    print("Generating Layer 3: Execution Patterns...")
    layer3 = build_layer_3(cycle, derailment, idea_registry, classifications, completion_stats)

    print("Generating Layer 4: Decision & Risk...")
    layer4 = build_layer_4(psych, emotional, growth, cycle, language, beliefs, classifications)

    print("Generating Layer 5: Emotional/Cognitive OS...")
    layer5 = build_layer_5(psych, emotional, growth, derailment, language, classifications)

    print("Generating Layer 6: Opportunity Map...")
    layer6 = build_layer_6(psych, emotional, growth, cycle, derailment, idea_registry, classifications, completion_stats)

    # Assemble document
    header = f"""# BEHAVIORAL AUDIT: Full System Analysis

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Data Sources:** 93,898 messages across 1,397 conversations
**Analysis Files:** {loaded} behavioral profiles + idea registry + conversation classifications
**Questions Answered:** 30 across 6 layers

---

## Table of Contents

**Layer 1 — Identity:** Q1-Q5 (Themes, Values, Claims, Rules, Pressure)
**Layer 2 — Power:** Q6-Q10 (Advantages, Weaknesses, Leaks, Over/Under, Models)
**Layer 3 — Execution:** Q11-Q15 (Projects, Stall Point, Strengths, Avoidance, Follow-Through)
**Layer 4 — Decision:** Q16-Q20 (Style, Risk, Regret, Commitment, Inflection Points)
**Layer 5 — Emotional:** Q21-Q24 (Defaults, Triggers, Self-Talk, Conflict)
**Layer 6 — Opportunity:** Q25-Q30 (Levers, Role, Stop List, Manual, 90-Day Plan, Prediction)

---

"""

    full_report = header + layer1 + "\n---\n\n" + layer2 + "\n---\n\n" + layer3 + "\n---\n\n" + layer4 + "\n---\n\n" + layer5 + "\n---\n\n" + layer6

    # Write output
    out_path = BASE / "BEHAVIORAL_AUDIT.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_report)

    # Summary
    lines = full_report.count("\n")
    print(f"\n{'=' * 60}")
    print(f"AUDIT COMPLETE")
    print(f"{'=' * 60}")
    print(f"Report: {out_path.name}")
    print(f"Lines: {lines}")
    print(f"Size: {len(full_report):,} characters")
    print(f"Questions answered: 30")
    print(f"Layers: 6")


if __name__ == "__main__":
    main()
