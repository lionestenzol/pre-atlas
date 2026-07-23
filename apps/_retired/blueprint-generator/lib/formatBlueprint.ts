import { Blueprint } from './types';

export function formatBlueprint(blueprint: Blueprint): string {
  const { sections, v2ParkingLot } = blueprint;
  const lines: string[] = [];

  lines.push('# Execution Blueprint');
  lines.push('');
  lines.push('## Objective');
  lines.push(sections.objective);
  lines.push('');
  lines.push('## Target User');
  lines.push(sections.targetUser);
  lines.push('');
  lines.push('## Core Function');
  lines.push(sections.coreFunction);
  lines.push('');
  lines.push('## Constraints (V1 Only)');
  sections.constraintsV1Only.forEach((c) => lines.push(`- ${c}`));
  lines.push('');
  lines.push('## MVP Features (max 5)');
  sections.mvpFeatures.forEach((f, i) => lines.push(`${i + 1}. ${f}`));
  lines.push('');
  lines.push('## Build Steps');
  sections.buildSteps.forEach((s) => lines.push(s));
  lines.push('');
  lines.push('## Dependencies');
  sections.dependencies.forEach((d) => lines.push(`- ${d}`));
  lines.push('');
  lines.push('## Definition of Done');
  sections.definitionOfDone.forEach((d) => lines.push(`- [ ] ${d}`));

  if (v2ParkingLot.length > 0) {
    lines.push('');
    lines.push('## V2 Parking Lot');
    v2ParkingLot.forEach((f) => lines.push(`- ${f}`));
  }

  return lines.join('\n');
}
