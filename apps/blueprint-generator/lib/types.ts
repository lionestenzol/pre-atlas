export interface ParsedIdea {
  product: string;
  user: string;
  action: string;
}

export interface ParseSuccess {
  ok: true;
  data: ParsedIdea;
}

export interface ParseError {
  ok: false;
  error: string;
}

export type ParseResult = ParseSuccess | ParseError;

export interface BlueprintSections {
  objective: string;
  targetUser: string;
  coreFunction: string;
  constraintsV1Only: string[];
  mvpFeatures: string[];
  buildSteps: string[];
  dependencies: string[];
  definitionOfDone: string[];
}

export interface Blueprint {
  id: string;
  createdAt: number;
  input: string;
  parsedIdea: ParsedIdea;
  sections: BlueprintSections;
  mvpFeatures: string[];
  v2ParkingLot: string[];
}

export type FeatureClassification =
  | { classification: 'essential'; reason: string }
  | { classification: 'v2ParkingLot'; reason: string; matchedKeyword: string };

export interface StoredState {
  blueprint: Blueprint | null;
  history: Blueprint[];
}
