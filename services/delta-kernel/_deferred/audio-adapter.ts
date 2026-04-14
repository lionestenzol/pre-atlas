/**
 * Delta-State Fabric v0 — Module 11: Audio Streaming Adapter
 *
 * Captures audio from microphone, extracts frequency band energy,
 * emits deltas when bands change. Enables voice over LoRa.
 *
 * Band layout (voice-optimized):
 *   Band 0: 80-300 Hz   (bass, fundamental)
 *   Band 1: 300-1000 Hz (low-mid, vowels)
 *   Band 2: 1000-3000 Hz (mid, consonants, clarity)
 *   Band 3: 3000-8000 Hz (high, sibilance, presence)
 *
 * Bandwidth: ~20-50 bytes/sec for voice (vs 64kbps raw audio)
 */

import { UUID, Timestamp, Delta, JsonPatch } from './types';
import { generateUUID, now, computeHash } from './delta';

// === TYPES ===

export type AudioSurfaceID = UUID;

export interface AudioBandState {
  band_index: number;
  energy: number;        // 0-255
  updated_at: Timestamp;
}

export interface AudioSurfaceState {
  surface_id: AudioSurfaceID;
  bands: number[];       // [band0, band1, band2, band3]
  is_speaking: boolean;
  last_updated: Timestamp;
}

export interface AudioDelta {
  surface_id: AudioSurfaceID;
  band_index: number;
  delta_value: number;   // Change from previous (-255 to +255)
  timestamp: Timestamp;
}

// === CONSTANTS ===

export const AUDIO_BANDS: [number, number][] = [
  [80, 300],      // Bass, fundamental frequency
  [300, 1000],    // Low-mid, vowel sounds
  [1000, 3000],   // Mid, consonants, speech clarity
  [3000, 8000],   // High, sibilance, presence
];

const DELTA_THRESHOLD = 2;      // Minimum change to emit delta
const SILENCE_THRESHOLD = 10;   // Below this = silence
const FFT_SIZE = 512;

// === AUDIO CAPTURE ===

export interface AudioCaptureHandle {
  stop: () => void;
  getSurfaceState: () => AudioSurfaceState;
  getMetrics: () => AudioMetrics;
}

export interface AudioMetrics {
  frames_processed: number;
  deltas_emitted: number;
  bytes_sent: number;
  avg_bands: number[];
  is_speaking: boolean;
  peak_energy: number;
}

export async function startAudioCapture(
  surfaceId: AudioSurfaceID,
  onDelta: (delta: Delta) => void,
  options?: {
    deviceId?: string;
    deltaThreshold?: number;
  }
): Promise<AudioCaptureHandle> {
  const threshold = options?.deltaThreshold ?? DELTA_THRESHOLD;

  // Get microphone stream
  const constraints: MediaStreamConstraints = {
    audio: options?.deviceId
      ? { deviceId: { exact: options.deviceId } }
      : true,
  };

  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  const audioCtx = new AudioContext();
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = FFT_SIZE;

  source.connect(analyser);

  const frequencyBuffer = new Uint8Array(analyser.frequencyBinCount);
  let lastBands: number[] = [0, 0, 0, 0];
  let running = true;

  // Metrics
  let framesProcessed = 0;
  let deltasEmitted = 0;
  let bytesSent = 0;
  let bandSums = [0, 0, 0, 0];
  let peakEnergy = 0;

  // Surface state
  const surfaceState: AudioSurfaceState = {
    surface_id: surfaceId,
    bands: [0, 0, 0, 0],
    is_speaking: false,
    last_updated: now(),
  };

  // Entity tracking for delta chain
  let currentHash = '0'.repeat(64);
  let version = 0;

  function processFrame() {
    if (!running) return;

    analyser.getByteFrequencyData(frequencyBuffer);
    framesProcessed++;

    // Extract band energies
    const bands = AUDIO_BANDS.map(([low, high]) => {
      const lowBin = Math.floor((low / audioCtx.sampleRate) * frequencyBuffer.length * 2);
      const highBin = Math.floor((high / audioCtx.sampleRate) * frequencyBuffer.length * 2);
      const clampedLow = Math.max(0, Math.min(lowBin, frequencyBuffer.length - 1));
      const clampedHigh = Math.max(0, Math.min(highBin, frequencyBuffer.length - 1));

      let sum = 0;
      let count = 0;
      for (let i = clampedLow; i <= clampedHigh; i++) {
        sum += frequencyBuffer[i];
        count++;
      }
      return count > 0 ? Math.floor(sum / count) : 0;
    });

    // Update metrics
    bands.forEach((v, i) => bandSums[i] += v);
    const totalEnergy = bands.reduce((a, b) => a + b, 0);
    if (totalEnergy > peakEnergy) peakEnergy = totalEnergy;

    // Detect speaking
    surfaceState.is_speaking = totalEnergy > SILENCE_THRESHOLD * AUDIO_BANDS.length;

    // Emit deltas for changed bands
    const patches: JsonPatch[] = [];

    bands.forEach((value, i) => {
      const delta = value - lastBands[i];
      if (Math.abs(delta) > threshold) {
        patches.push({
          op: 'replace',
          path: `/bands/${i}`,
          value: value,
        });
        surfaceState.bands[i] = value;
      }
    });

    // Emit speaking state change
    if (patches.length > 0) {
      patches.push({
        op: 'replace',
        path: '/is_speaking',
        value: surfaceState.is_speaking,
      });
      patches.push({
        op: 'replace',
        path: '/last_updated',
        value: now(),
      });

      // Create delta
      const prevHash = currentHash;
      currentHash = computeHash({ bands: surfaceState.bands, ts: now() });
      version++;

      const audioDelta: Delta = {
        delta_id: generateUUID(),
        entity_id: surfaceId,
        timestamp: now(),
        author: 'system',
        patch: patches,
        prev_hash: prevHash,
        new_hash: currentHash,
      };

      onDelta(audioDelta);
      deltasEmitted++;
      bytesSent += JSON.stringify(audioDelta).length;

      surfaceState.last_updated = now();
    }

    lastBands = [...bands];

    requestAnimationFrame(processFrame);
  }

  // Start processing
  processFrame();

  return {
    stop: () => {
      running = false;
      stream.getTracks().forEach(track => track.stop());
      audioCtx.close();
    },

    getSurfaceState: () => ({ ...surfaceState }),

    getMetrics: () => ({
      frames_processed: framesProcessed,
      deltas_emitted: deltasEmitted,
      bytes_sent: bytesSent,
      avg_bands: bandSums.map(s => framesProcessed > 0 ? s / framesProcessed : 0),
      is_speaking: surfaceState.is_speaking,
      peak_energy: peakEnergy,
    }),
  };
}

// === COMPACT AUDIO DELTA ===

export interface CompactAudioDelta {
  s: AudioSurfaceID;  // surface
  b: number[];        // band deltas (4 values, signed)
  t: number;          // timestamp offset
}

export function createCompactAudioDelta(
  surfaceId: AudioSurfaceID,
  bandDeltas: number[],
  baseTimestamp: Timestamp
): CompactAudioDelta {
  return {
    s: surfaceId.slice(0, 8),  // Truncate UUID
    b: bandDeltas,
    t: now() - baseTimestamp,
  };
}

// Compact format: ~20-30 bytes vs ~200 bytes full delta
export function serializeCompactAudio(delta: CompactAudioDelta): Uint8Array {
  // Format: [surfaceId(8)] [band0] [band1] [band2] [band3] [timestamp(2)]
  const buffer = new Uint8Array(14);

  // Surface ID (first 8 chars as bytes)
  for (let i = 0; i < 8; i++) {
    buffer[i] = delta.s.charCodeAt(i) || 0;
  }

  // Band deltas (signed bytes, clamped to -127 to +127)
  for (let i = 0; i < 4; i++) {
    buffer[8 + i] = Math.max(-127, Math.min(127, delta.b[i])) + 128;
  }

  // Timestamp offset (16-bit)
  buffer[12] = (delta.t >> 8) & 0xff;
  buffer[13] = delta.t & 0xff;

  return buffer;
}

export function deserializeCompactAudio(buffer: Uint8Array): CompactAudioDelta {
  const s = String.fromCharCode(...buffer.slice(0, 8));
  const b = [
    buffer[8] - 128,
    buffer[9] - 128,
    buffer[10] - 128,
    buffer[11] - 128,
  ];
  const t = (buffer[12] << 8) | buffer[13];

  return { s, b, t };
}

// === NODE.JS ADAPTER (for server-side audio) ===

/**
 * Process raw PCM audio samples into band energies.
 * For use with Node.js audio libraries or ffmpeg.
 */
export function processAudioSamples(
  samples: Float32Array,
  sampleRate: number
): number[] {
  // Simple DFT for band extraction (not FFT, but works for small buffers)
  const bands = AUDIO_BANDS.map(([low, high]) => {
    let energy = 0;

    for (let freq = low; freq <= high; freq += 50) {
      let real = 0;
      let imag = 0;
      const omega = (2 * Math.PI * freq) / sampleRate;

      for (let i = 0; i < samples.length; i++) {
        real += samples[i] * Math.cos(omega * i);
        imag += samples[i] * Math.sin(omega * i);
      }

      energy += Math.sqrt(real * real + imag * imag);
    }

    // Normalize to 0-255
    return Math.min(255, Math.floor(energy / samples.length * 1000));
  });

  return bands;
}
