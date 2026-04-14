#!/bin/bash
cd /root/festival-project/festivals/active/mosaic-platform-MP0001

# Sequence 1: Docker
echo y | fest task completed 006_INSTALLER/01_docker/01_write_env_example.md
echo y | fest task completed 006_INSTALLER/01_docker/02_write_dockerfiles.md
echo y | fest task completed 006_INSTALLER/01_docker/03_write_root_docker_compose.md
echo y | fest task completed 006_INSTALLER/01_docker/04_testing.md
echo y | fest task completed 006_INSTALLER/01_docker/05_review.md
echo y | fest task completed 006_INSTALLER/01_docker/06_iterate.md
echo y | fest task completed 006_INSTALLER/01_docker/07_fest_commit.md

# Sequence 2: Installer
echo y | fest task completed 006_INSTALLER/02_installer/01_write_documentation.md
echo y | fest task completed 006_INSTALLER/02_installer/02_write_aegis_seed_script.md
echo y | fest task completed 006_INSTALLER/02_installer/03_write_installer_script.md
echo y | fest task completed 006_INSTALLER/02_installer/04_testing.md
echo y | fest task completed 006_INSTALLER/02_installer/05_review.md
echo y | fest task completed 006_INSTALLER/02_installer/06_iterate.md
echo y | fest task completed 006_INSTALLER/02_installer/07_fest_commit.md

echo "--- Sequences done, advancing gate ---"

for i in 1 2 3 4; do
    echo y | fest workflow advance 006_INSTALLER
    echo y | fest workflow approve
done

echo "--- Phase 6 complete ---"
fest progress
