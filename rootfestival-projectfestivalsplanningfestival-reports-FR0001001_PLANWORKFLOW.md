# Planning Workflow

## Step 1: Report Schema
Define the REPORT.md structure:
- Header: festival name, dates, duration, task counts
- Accuracy: planned vs actual tasks, scope changes
- Bottlenecks: gate rejections, phases that took longest
- Retrospective: what worked, what didn't, what to change

## Step 2: Data Sources
Map where each metric comes from:
- fest.yaml: festival metadata, creation date
- Task files: completion status, timestamps
- GATES.md: gate pass/fail history
- fest progress output: completion percentages

## Step 3: Lessons Engine Design
Design how patterns are detected across multiple reports:
- Aggregation: averages, trends across festivals
- Pattern matching: recurring bottlenecks, consistent over/under-scoping
- Output format: concise bullet points for skill consumption

## Completion
Phase is done when all 3 designs are documented.
