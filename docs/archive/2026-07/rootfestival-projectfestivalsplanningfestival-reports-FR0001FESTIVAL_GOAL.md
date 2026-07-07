---
fest_type: festival
fest_id: FR0001
fest_name: festival-reports
fest_status: planning
fest_created: 2026-03-25T20:00:00-05:00
fest_tracking: true
---

# festival-reports

**Status:** Planned | **Created:** 2026-03-25

## Festival Objective

**Primary Goal:** Build a post-festival report system that captures lessons learned and feeds them back into future festival planning.

**Vision:** Every completed festival generates a structured REPORT.md capturing accuracy metrics, bottlenecks, waste, and retrospective insights. A `fest lessons` command surfaces patterns from past reports to improve future festival planning. The /fest skill uses these lessons to give smarter suggestions when creating new festivals.

## Success Criteria

### Functional Success

- [ ] `fest report` generates REPORT.md from completed festival data
- [ ] Report captures: task accuracy, gate rejection rate, phase timing, scope changes
- [ ] `fest lessons` reads past reports and surfaces actionable patterns
- [ ] /fest skill references lessons when creating new festivals
- [ ] Reports stored in dungeon alongside archived festivals

### Quality Success

- [ ] Report generation is automatic (triggered on festival completion)
- [ ] Lessons are concise and actionable, not just raw data
- [ ] System works with zero past reports (graceful cold start)

## Progress Tracking

### Phase Completion

- [ ] 001_PLAN: Design report schema and lessons engine
- [ ] 002_REPORT_GENERATOR: Build report generation from festival metadata
- [ ] 003_LESSONS_ENGINE: Build cross-festival pattern detection
- [ ] 004_SKILL_UPDATE: Wire lessons into /fest skill creation flow

## Complete When

- [ ] fest report works on cycleboard-wiring-CW0001
- [ ] fest lessons returns insights from at least 1 report
- [ ] /fest create references lessons in its output
