import { ParsedIdea, Blueprint, BlueprintSections } from './types';

export function generateBlueprint(parsedIdea: ParsedIdea, rawInput: string): Blueprint {
  const { product, user, action } = parsedIdea;

  const sections: BlueprintSections = {
    objective: `Build a ${product} that enables ${user} to ${action}. Nothing more.`,

    targetUser: `${user} who currently cannot easily ${action}.`,

    coreFunction: `The single core function is: let ${user} ${action} using ${product}.`,

    constraintsV1Only: [
      'No user accounts or authentication',
      'No backend server or database',
      'No third-party integrations',
      'No mobile app — web only',
      'No analytics or tracking',
      'Ship in under 2 weeks',
    ],

    mvpFeatures: [
      `Core interface for ${user} to ${action}`,
      'Input validation and error handling',
      'Local data persistence (localStorage)',
      'Single-page responsive layout',
      'Clear empty/error/success states',
    ],

    buildSteps: [
      `1. Define data model for ${product}`,
      `2. Build core ${action} interface`,
      '3. Implement input validation',
      '4. Add localStorage persistence',
      '5. Style with minimal CSS (dark theme, responsive)',
      '6. Test all error states manually',
      '7. Deploy to Vercel',
    ],

    dependencies: [
      'Next.js (App Router) or Vite + React',
      'TypeScript (strict mode)',
      'No component library — vanilla CSS only',
      'No state management library — useState/useReducer only',
    ],

    definitionOfDone: [
      `${user} can ${action} end-to-end in one session`,
      'All inputs validated; no silent failures',
      'Works offline after first load (localStorage)',
      'Loads in under 2 seconds on 3G',
      'Zero runtime errors in console',
      'Deployed and accessible via public URL',
    ],
  };

  return {
    id: crypto.randomUUID(),
    createdAt: Date.now(),
    input: rawInput,
    parsedIdea,
    sections,
    mvpFeatures: [...sections.mvpFeatures],
    v2ParkingLot: [],
  };
}
