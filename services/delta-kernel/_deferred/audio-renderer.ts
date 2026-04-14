/**
 * Delta-State Fabric v0 — Module 11: Audio Renderer
 *
 * Reconstructs audio from band deltas received over the network.
 * Synthesizes voice-like audio from 4-band energy representation.
 *
 * This is NOT high-fidelity audio. It's intelligible voice over LoRa.
 */

import { UUID, Delta } from './types';
import { AudioSurfaceState, AUDIO_BANDS, CompactAudioDelta } from './audio-adapter';

// === AUDIO SURFACE STORE ===

export class AudioSurfaceStore {
  private surfaces: Map<UUID, AudioSurfaceState> = new Map();

  register(surfaceId: UUID): void {
    this.surfaces.set(surfaceId, {
      surface_id: surfaceId,
      bands: [0, 0, 0, 0],
      is_speaking: false,
      last_updated: Date.now(),
    });
  }

  applyDelta(delta: Delta): boolean {
    const state = this.surfaces.get(delta.entity_id);
    if (!state) return false;

    for (const patch of delta.patch) {
      if (patch.path.startsWith('/bands/')) {
        const bandIndex = parseInt(patch.path.split('/')[2]);
        if (bandIndex >= 0 && bandIndex < 4) {
          state.bands[bandIndex] = patch.value as number;
        }
      } else if (patch.path === '/is_speaking') {
        state.is_speaking = patch.value as boolean;
      } else if (patch.path === '/last_updated') {
        state.last_updated = patch.value as number;
      }
    }

    return true;
  }

  getState(surfaceId: UUID): AudioSurfaceState | null {
    return this.surfaces.get(surfaceId) || null;
  }

  getAllSurfaces(): AudioSurfaceState[] {
    return Array.from(this.surfaces.values());
  }
}

// === AUDIO RENDERER ===

export interface AudioRendererHandle {
  stop: () => void;
  setVolume: (volume: number) => void;
  getState: () => AudioSurfaceState | null;
}

/**
 * Render audio surface state to speakers.
 * Uses oscillator synthesis to approximate voice.
 */
export function createAudioRenderer(
  store: AudioSurfaceStore,
  surfaceId: UUID,
  options?: {
    volume?: number;
    renderInterval?: number;
  }
): AudioRendererHandle {
  const audioCtx = new AudioContext();
  const masterGain = audioCtx.createGain();
  masterGain.gain.value = options?.volume ?? 0.3;
  masterGain.connect(audioCtx.destination);

  const renderInterval = options?.renderInterval ?? 50; // ms
  let running = true;

  // Band center frequencies for synthesis
  const bandFrequencies = [200, 600, 1800, 5000];

  function render() {
    if (!running) return;

    const state = store.getState(surfaceId);
    if (!state || !state.is_speaking) {
      setTimeout(render, renderInterval);
      return;
    }

    // Create oscillators for each band
    state.bands.forEach((energy, i) => {
      if (energy < 10) return; // Skip quiet bands

      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      // Use different waveforms for different bands
      osc.type = i < 2 ? 'sawtooth' : 'sine';
      osc.frequency.value = bandFrequencies[i];

      // Energy to gain (logarithmic for more natural sound)
      const gainValue = Math.log1p(energy) / Math.log1p(255) * 0.25;
      gain.gain.value = gainValue;

      osc.connect(gain);
      gain.connect(masterGain);

      osc.start();
      osc.stop(audioCtx.currentTime + renderInterval / 1000);
    });

    setTimeout(render, renderInterval);
  }

  render();

  return {
    stop: () => {
      running = false;
      audioCtx.close();
    },

    setVolume: (volume: number) => {
      masterGain.gain.value = Math.max(0, Math.min(1, volume));
    },

    getState: () => store.getState(surfaceId),
  };
}

// === SIMPLE VOICE RENDERER ===

/**
 * One-shot render of current audio state.
 * Use for immediate playback of received deltas.
 */
export function renderAudioOnce(state: AudioSurfaceState): void {
  if (!state.is_speaking) return;

  const ctx = new AudioContext();
  const masterGain = ctx.createGain();
  masterGain.gain.value = 0.3;
  masterGain.connect(ctx.destination);

  const frequencies = [200, 600, 1800, 5000];

  state.bands.forEach((energy, i) => {
    if (energy < 10) return;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = i < 2 ? 'sawtooth' : 'sine';
    osc.frequency.value = frequencies[i];

    const gainValue = Math.log1p(energy) / Math.log1p(255) * 0.25;
    gain.gain.value = gainValue;

    // Fade out envelope
    gain.gain.setValueAtTime(gainValue, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);

    osc.connect(gain);
    gain.connect(masterGain);

    osc.start();
    osc.stop(ctx.currentTime + 0.1);
  });
}

// === REPLAY FROM DELTAS ===

export interface AudioReplayHandle {
  play: () => void;
  pause: () => void;
  stop: () => void;
  seek: (timestamp: number) => void;
  isPlaying: () => boolean;
}

/**
 * Replay audio from delta ledger.
 * Reconstructs voice timeline from stored deltas.
 */
export function createAudioReplay(
  deltas: Delta[],
  surfaceId: UUID
): AudioReplayHandle {
  const store = new AudioSurfaceStore();
  store.register(surfaceId);

  // Sort deltas by timestamp
  const sortedDeltas = [...deltas]
    .filter(d => d.entity_id === surfaceId)
    .sort((a, b) => a.timestamp - b.timestamp);

  if (sortedDeltas.length === 0) {
    return {
      play: () => {},
      pause: () => {},
      stop: () => {},
      seek: () => {},
      isPlaying: () => false,
    };
  }

  const baseTimestamp = sortedDeltas[0].timestamp;
  let currentIndex = 0;
  let playing = false;
  let startTime = 0;
  let pausedAt = 0;
  let renderer: AudioRendererHandle | null = null;
  let timeoutId: number | null = null;

  function scheduleNext() {
    if (!playing || currentIndex >= sortedDeltas.length) {
      playing = false;
      return;
    }

    const delta = sortedDeltas[currentIndex];
    const deltaTime = delta.timestamp - baseTimestamp;
    const elapsed = Date.now() - startTime;
    const delay = deltaTime - elapsed;

    if (delay <= 0) {
      // Apply immediately
      store.applyDelta(delta);
      currentIndex++;
      scheduleNext();
    } else {
      timeoutId = window.setTimeout(() => {
        store.applyDelta(delta);
        currentIndex++;
        scheduleNext();
      }, delay);
    }
  }

  return {
    play: () => {
      if (playing) return;
      playing = true;
      startTime = Date.now() - pausedAt;

      if (!renderer) {
        renderer = createAudioRenderer(store, surfaceId);
      }

      scheduleNext();
    },

    pause: () => {
      playing = false;
      pausedAt = Date.now() - startTime;
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    },

    stop: () => {
      playing = false;
      pausedAt = 0;
      currentIndex = 0;
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      if (renderer) {
        renderer.stop();
        renderer = null;
      }
      store.register(surfaceId); // Reset state
    },

    seek: (timestamp: number) => {
      const wasPlaying = playing;
      if (wasPlaying) {
        if (timeoutId) clearTimeout(timeoutId);
      }

      // Find delta at timestamp
      currentIndex = sortedDeltas.findIndex(
        d => d.timestamp - baseTimestamp >= timestamp
      );
      if (currentIndex < 0) currentIndex = sortedDeltas.length;

      // Reset and replay up to this point
      store.register(surfaceId);
      for (let i = 0; i < currentIndex; i++) {
        store.applyDelta(sortedDeltas[i]);
      }

      pausedAt = timestamp;

      if (wasPlaying) {
        playing = true;
        startTime = Date.now() - pausedAt;
        scheduleNext();
      }
    },

    isPlaying: () => playing,
  };
}

// === VOICE ACTIVITY DETECTION ===

export interface VADResult {
  is_speaking: boolean;
  energy: number;
  duration_ms: number;
}

/**
 * Detect voice activity from audio surface state.
 */
export function detectVoiceActivity(
  state: AudioSurfaceState,
  history: AudioSurfaceState[],
  options?: {
    energyThreshold?: number;
    minDurationMs?: number;
  }
): VADResult {
  const threshold = options?.energyThreshold ?? 40;
  const minDuration = options?.minDurationMs ?? 100;

  const totalEnergy = state.bands.reduce((a, b) => a + b, 0);
  const isSpeaking = totalEnergy > threshold;

  // Calculate speaking duration from history
  let durationMs = 0;
  if (isSpeaking && history.length > 0) {
    for (let i = history.length - 1; i >= 0; i--) {
      const histEnergy = history[i].bands.reduce((a, b) => a + b, 0);
      if (histEnergy > threshold) {
        durationMs = state.last_updated - history[i].last_updated;
      } else {
        break;
      }
    }
  }

  return {
    is_speaking: isSpeaking && durationMs >= minDuration,
    energy: totalEnergy,
    duration_ms: durationMs,
  };
}
