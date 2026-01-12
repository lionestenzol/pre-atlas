# MODULE 11 — AUDIO STREAMING

**Status:** COMPLETE
**Version:** 1.0.0

---

## Mission

Voice communication over LoRa. Two modes:
1. **Band-energy** — 30 bytes/sec, presence detection only
2. **LPC/Codec2** — 88-650 bytes/sec, intelligible speech

> Real voice over radio. Not VoIP. Not video call. Radio voice.

---

## Laws

1. **All audio is deltas** — No raw PCM over the wire
2. **Silence = zero bandwidth** — Only transmit when speaking
3. **Deterministic reconstruction** — Same frames → same audio
4. **Graceful degradation** — Falls back to band-energy if codec unavailable

---

## Two Modes

### Mode A: Band-Energy (Presence Detection)

```typescript
AUDIO_BANDS = [
  [80, 300],      // Bass, fundamental
  [300, 1000],    // Low-mid, vowels
  [1000, 3000],   // Mid, consonants
  [3000, 8000],   // High, sibilance
];
```

| Metric | Value |
|--------|-------|
| Bandwidth | ~30 bytes/sec |
| Latency | 50ms |
| Quality | "Someone is speaking loudly" |
| Use case | Trigger automation, presence |

### Mode B: LPC/Codec2 (Intelligible Speech)

| Codec | Bits/sec | Bytes/sec | Quality |
|-------|----------|-----------|---------|
| Codec2 3200 | 3200 | 400 | Good |
| Codec2 1300 | 1300 | 163 | Acceptable |
| Codec2 700C | 700 | 88 | Minimum intelligible |
| LPC-14 fallback | ~7200 | 900 | Good clarity (JS-only) |

---

## Audio Specifications

```typescript
SAMPLE_RATE = 8000;      // Hz
FRAME_SIZE = 160;        // samples (20ms)
FRAME_DURATION = 20;     // ms
CHANNELS = 1;            // mono
BIT_DEPTH = 16;          // signed int
```

---

## Entity Types

### AudioSurface (band-energy mode)
```typescript
interface AudioSurfaceState {
  surface_id: UUID;
  bands: number[];       // [band0, band1, band2, band3]
  is_speaking: boolean;
  last_updated: Timestamp;
}
```

### VoiceSurface (codec mode)
```typescript
interface VoiceSurfaceState {
  surface_id: UUID;
  mode: Codec2Mode;
  is_speaking: boolean;
  frame_count: number;
  last_frame_id: number;
  last_updated: Timestamp;
}
```

---

## LPC Codec (Pure JS Fallback)

When Codec2 WASM isn't available, uses improved LPC-14 codec:

```typescript
// Encode 160 samples → 18 bytes
// Format: [energy:1][pitch:1][voiced_conf:1][gain:1][lpc_coeffs:14]

class SimpleLPCCodec {
  encode(samples: Int16Array): Uint8Array;   // → 18 bytes
  decode(encoded: Uint8Array): Int16Array;   // → 160 samples
}
```

**Algorithm:**
1. Apply pre-emphasis filter (0.95 coefficient) for consonant clarity
2. Compute frame energy with μ-law compression
3. Estimate pitch via normalized autocorrelation with parabolic interpolation
4. Compute 14 LPC coefficients via Levinson-Durbin (was 10)
5. Compute excitation gain from residual energy
6. Pack into 18 bytes using μ-law quantization
7. Decode: interpolate LPC coefficients across frame, mixed excitation (voiced+noise)
8. Apply de-emphasis filter to restore frequency balance

---

## Compact Wire Format

### Band-Energy Delta
```typescript
// 14 bytes per update
interface CompactAudioDelta {
  s: string;      // surface ID (8 chars)
  b: number[];    // band deltas (4 signed bytes)
  t: number;      // timestamp offset (2 bytes)
}
```

### Voice Frame
```typescript
// 6 + N bytes per frame
interface CompactVoiceFrame {
  s: string;      // surface ID (4 chars)
  f: number;      // frame number (2 bytes)
  d: number[];    // encoded data (N bytes)
}
```

---

## Capture API

### Band-Energy Mode
```typescript
async function startAudioCapture(
  surfaceId: UUID,
  onDelta: (delta: Delta) => void,
  options?: { deltaThreshold?: number }
): Promise<AudioCaptureHandle>
```

### Codec Mode
```typescript
async function startVoiceCapture(
  surfaceId: UUID,
  onDelta: (delta: Delta) => void,
  options?: { mode?: Codec2Mode; silenceThreshold?: number }
): Promise<VoiceCaptureHandle>
```

---

## Playback API

### Band-Energy Synthesis
```typescript
function renderAudioOnce(state: AudioSurfaceState): void
function createAudioRenderer(store, surfaceId): AudioRendererHandle
```

### Codec Playback
```typescript
function createVoicePlayback(surfaceId: UUID): VoicePlaybackHandle
```

---

## Files

| File | Purpose |
|------|---------|
| `audio-adapter.ts` | Band-energy capture + synthesis |
| `audio-renderer.ts` | Band-energy playback + replay |
| `codec2-adapter.ts` | LPC fallback + Codec2 WASM interface |
| `audio-live-test.html` | Band-energy browser test |
| `voice-live-test.html` | LPC codec browser test |

---

## Bandwidth vs LoRa

LoRa practical limit: ~300 bytes/sec

| Mode | Bytes/sec | Fits LoRa? |
|------|-----------|------------|
| Band-energy | 30 | ✓ Easy |
| Codec2 700C | 88 | ✓ Easy |
| Codec2 1300 | 163 | ✓ Yes |
| Codec2 3200 | 400 | Tight |
| LPC-14 fallback | 900 | ✗ Over limit |

**Recommendation:** Use Codec2 700C or 1300 for LoRa voice. LPC-14 for local/WiFi.

---

## Voice Activity Detection

```typescript
interface VADResult {
  is_speaking: boolean;
  energy: number;
  duration_ms: number;
}

function detectVoiceActivity(
  state: AudioSurfaceState,
  history: AudioSurfaceState[],
  options?: { energyThreshold?: number; minDurationMs?: number }
): VADResult
```

---

## Integration with Delta Fabric

Audio deltas flow through the same sync protocol as all other entities:

```
Microphone → Encode → Delta → Sync → Receive → Decode → Speaker
                        ↓
                   Hash Chain
                        ↓
                   Replay OK
```

**Sync Priority:** 5 (same as camera)

---

## Use Cases

1. **Gate intercom** — Visitor speaks, owner hears over LoRa
2. **Field radio** — Voice messages between off-grid nodes
3. **Alert narration** — System speaks status updates
4. **Voice trigger** — "Open gate" triggers actuation

---

## What Module 11 Enables

- Real voice over LoRa at 88-400 bytes/sec
- Presence detection at 30 bytes/sec
- Replayable audio history
- Integration with actuation (voice commands)
- Offline-safe voice messages

---

## Next Steps

**Module 12: Swarm Scheduling** — Decentralized task claims for device meshes.

Command: **Start Module 12 — Swarm Work Claims.**
