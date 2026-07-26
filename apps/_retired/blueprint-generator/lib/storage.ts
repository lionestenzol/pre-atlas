import { StoredState } from './types';

const STORAGE_KEY = 'blueprint-generator-state';

export function loadState(): StoredState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as StoredState;
  } catch {
    // Corrupted data, start fresh
  }
  return { blueprint: null, history: [] };
}

export function saveState(state: StoredState): void {
  try {
    const capped = {
      ...state,
      history: state.history.slice(-10),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(capped));
  } catch {
    // localStorage full or unavailable
  }
}
