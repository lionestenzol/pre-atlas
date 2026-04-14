import { Blueprint, FeatureClassification } from './types';

const EXPANSION_KEYWORDS = [
  'slack',
  'community',
  'analytics',
  'integrations',
  'mobile app',
  'team',
  'certification',
];

export function classifyFeature(featureText: string): FeatureClassification {
  const lower = featureText.toLowerCase();

  for (const keyword of EXPANSION_KEYWORDS) {
    if (lower.includes(keyword)) {
      return {
        classification: 'v2ParkingLot',
        reason: `Contains expansion keyword "${keyword}". Deferred to V2.`,
        matchedKeyword: keyword,
      };
    }
  }

  return {
    classification: 'essential',
    reason: 'No expansion keywords detected. Can replace one MVP feature.',
  };
}

export function addFeatureToBlueprint(
  featureText: string,
  blueprint: Blueprint,
  replaceIndex?: number,
): Blueprint {
  const classification = classifyFeature(featureText);

  if (classification.classification === 'v2ParkingLot') {
    return {
      ...blueprint,
      v2ParkingLot: [...blueprint.v2ParkingLot, featureText],
    };
  }

  const newFeatures = [...blueprint.mvpFeatures];

  if (replaceIndex !== undefined && replaceIndex >= 0 && replaceIndex < newFeatures.length) {
    newFeatures[replaceIndex] = featureText;
  } else if (newFeatures.length < 5) {
    newFeatures.push(featureText);
  } else {
    return blueprint;
  }

  return {
    ...blueprint,
    mvpFeatures: newFeatures,
    sections: {
      ...blueprint.sections,
      mvpFeatures: newFeatures,
    },
  };
}
