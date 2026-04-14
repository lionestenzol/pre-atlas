#!/bin/bash
# Advance Phase 5 tasks and gates
cd /root/festival-project/festivals/active/mosaic-platform-MP0001

# Sequence 1: Workflows
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/01_build_daily_automation_loop.md
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/02_build_stall_detector.md
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/03_build_idea_to_simulation_workflow.md
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/04_testing.md
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/05_review.md
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/06_iterate.md
echo y | fest task completed 005_WORKFLOWS_METERING/01_workflows/07_fest_commit.md

# Sequence 2: Metering
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/01_add_metering_schemas.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/02_build_metering_endpoints.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/03_wire_metering_into_adapters.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/04_build_metering_module.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/05_testing.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/06_review.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/07_iterate.md
echo y | fest task completed 005_WORKFLOWS_METERING/02_metering/08_fest_commit.md

echo "--- Sequences done, advancing gate ---"

# Phase gate (4 steps)
for i in 1 2 3 4; do
    echo y | fest workflow advance 005_WORKFLOWS_METERING
    echo y | fest workflow approve
done

echo "--- Phase 5 complete ---"
fest progress
