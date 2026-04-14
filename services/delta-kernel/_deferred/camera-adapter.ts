/**
 * Delta-State Fabric v0 — Camera Adapter
 *
 * Bridge between real camera input and the delta streaming system.
 * Converts HTMLVideoElement frames into SimulatedFrame format.
 *
 * This is the ONLY file needed to make Module 9 work with real cameras.
 * Everything else (extraction, deltas, sync, replay) already exists.
 */

import { SimulatedFrame, TilePixels, DetectedBlob } from './camera-extractor';

// === BROWSER CAMERA CAPTURE ===

/**
 * Capture a single frame from an HTMLVideoElement and convert to SimulatedFrame.
 * Works with any video source: webcam, screen share, video file.
 */
export async function captureCameraFrame(
  video: HTMLVideoElement,
  gridW: number,
  gridH: number,
  tileSize: number
): Promise<SimulatedFrame> {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  canvas.width = gridW * tileSize;
  canvas.height = gridH * tileSize;

  // Draw video frame to canvas (scales to fit grid)
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const rgba = imageData.data;

  const tiles = new Map<string, TilePixels>();

  // Extract tiles as grayscale luminance values
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      const pixels: number[] = [];

      for (let ty = 0; ty < tileSize; ty++) {
        for (let tx = 0; tx < tileSize; tx++) {
          const pixelX = x * tileSize + tx;
          const pixelY = y * tileSize + ty;
          const idx = (pixelY * canvas.width + pixelX) * 4;

          // Convert RGB to grayscale luminance
          const r = rgba[idx];
          const g = rgba[idx + 1];
          const b = rgba[idx + 2];
          const luminance = Math.round(0.299 * r + 0.587 * g + 0.114 * b);

          pixels.push(luminance);
        }
      }

      tiles.set(`${x},${y}`, pixels);
    }
  }

  // Estimate global brightness from center tiles
  const centerBrightness = estimateGlobalBrightness(tiles, gridW, gridH);

  return {
    tiles,
    globalBrightness: centerBrightness,
    colorTemp: 5500, // Could be estimated from white balance
  };
}

/**
 * Estimate global brightness from center region of frame.
 * Returns value from -10 to +10 relative to neutral (128).
 */
function estimateGlobalBrightness(
  tiles: Map<string, TilePixels>,
  gridW: number,
  gridH: number
): number {
  const centerX = Math.floor(gridW / 2);
  const centerY = Math.floor(gridH / 2);

  let totalLuminance = 0;
  let pixelCount = 0;

  // Sample center 2x2 tiles
  for (let dy = -1; dy <= 0; dy++) {
    for (let dx = -1; dx <= 0; dx++) {
      const key = `${centerX + dx},${centerY + dy}`;
      const pixels = tiles.get(key);
      if (pixels) {
        for (const p of pixels) {
          totalLuminance += p;
          pixelCount++;
        }
      }
    }
  }

  if (pixelCount === 0) return 0;

  const avgLuminance = totalLuminance / pixelCount;
  // Map 0-255 to -10 to +10, with 128 as neutral
  return ((avgLuminance - 128) / 128) * 10;
}

// === SIMPLE BLOB DETECTION ===

/**
 * Simple motion/blob detection by comparing current frame to baseline.
 * Returns detected blobs (moving objects) as tile regions.
 */
export function detectBlobs(
  currentFrame: SimulatedFrame,
  baselineFrame: SimulatedFrame,
  threshold: number = 30
): DetectedBlob[] {
  const changedTiles: string[] = [];

  // Find tiles that differ significantly from baseline
  for (const [key, currentPixels] of currentFrame.tiles) {
    const baselinePixels = baselineFrame.tiles.get(key);
    if (!baselinePixels) continue;

    // Calculate mean absolute difference
    let diff = 0;
    for (let i = 0; i < currentPixels.length; i++) {
      diff += Math.abs(currentPixels[i] - baselinePixels[i]);
    }
    const meanDiff = diff / currentPixels.length;

    if (meanDiff > threshold) {
      changedTiles.push(key);
    }
  }

  if (changedTiles.length === 0) return [];

  // Group adjacent changed tiles into blobs
  return clusterTilesIntoBlobs(changedTiles, currentFrame);
}

/**
 * Cluster adjacent tiles into blob regions.
 */
function clusterTilesIntoBlobs(
  changedTiles: string[],
  frame: SimulatedFrame
): DetectedBlob[] {
  const blobs: DetectedBlob[] = [];
  const visited = new Set<string>();

  for (const tile of changedTiles) {
    if (visited.has(tile)) continue;

    // BFS to find connected region
    const cluster: string[] = [];
    const queue = [tile];

    while (queue.length > 0) {
      const current = queue.shift()!;
      if (visited.has(current)) continue;
      visited.add(current);
      cluster.push(current);

      // Check 4-connected neighbors
      const [x, y] = current.split(',').map(Number);
      const neighbors = [
        `${x - 1},${y}`,
        `${x + 1},${y}`,
        `${x},${y - 1}`,
        `${x},${y + 1}`,
      ];

      for (const neighbor of neighbors) {
        if (changedTiles.includes(neighbor) && !visited.has(neighbor)) {
          queue.push(neighbor);
        }
      }
    }

    if (cluster.length > 0) {
      // Calculate blob center and brightness
      const coords = cluster.map((t) => t.split(',').map(Number));
      const avgX = coords.reduce((s, c) => s + c[0], 0) / coords.length;
      const avgY = coords.reduce((s, c) => s + c[1], 0) / coords.length;

      // Estimate brightness relative to baseline
      let brightnessSum = 0;
      for (const key of cluster) {
        const pixels = frame.tiles.get(key);
        if (pixels) {
          brightnessSum += pixels.reduce((a, b) => a + b, 0) / pixels.length;
        }
      }
      const avgBrightness = brightnessSum / cluster.length;
      const relativeBrightness = ((avgBrightness - 128) / 128) * 10;

      blobs.push({
        id: `blob-${blobs.length}`,
        x: Math.floor(avgX),
        y: Math.floor(avgY),
        tiles: cluster,
        brightness: relativeBrightness,
      });
    }
  }

  return blobs;
}

// === WEBCAM INITIALIZATION ===

/**
 * Initialize webcam and return video element ready for capture.
 */
export async function initWebcam(
  constraints?: MediaStreamConstraints
): Promise<HTMLVideoElement> {
  const video = document.createElement('video');
  video.autoplay = true;
  video.playsInline = true;

  const stream = await navigator.mediaDevices.getUserMedia(
    constraints || {
      video: {
        width: { ideal: 320 },
        height: { ideal: 240 },
        frameRate: { ideal: 10 },
      },
      audio: false,
    }
  );

  video.srcObject = stream;

  // Wait for video to be ready
  await new Promise<void>((resolve) => {
    video.onloadedmetadata = () => {
      video.play();
      resolve();
    };
  });

  return video;
}

/**
 * Stop webcam stream.
 */
export function stopWebcam(video: HTMLVideoElement): void {
  const stream = video.srcObject as MediaStream | null;
  if (stream) {
    for (const track of stream.getTracks()) {
      track.stop();
    }
  }
  video.srcObject = null;
}

// === CONTINUOUS CAPTURE LOOP ===

export interface CaptureLoopOptions {
  video: HTMLVideoElement;
  gridW: number;
  gridH: number;
  tileSize: number;
  fps: number;
  onFrame: (frame: SimulatedFrame, blobs: DetectedBlob[]) => void;
}

/**
 * Start continuous capture loop.
 * Returns stop function.
 */
export function startCaptureLoop(options: CaptureLoopOptions): () => void {
  const { video, gridW, gridH, tileSize, fps, onFrame } = options;

  let baselineFrame: SimulatedFrame | null = null;
  let running = true;
  const intervalMs = 1000 / fps;

  const loop = async () => {
    if (!running) return;

    const frame = await captureCameraFrame(video, gridW, gridH, tileSize);

    // First frame becomes baseline
    if (!baselineFrame) {
      baselineFrame = frame;
      onFrame(frame, []);
    } else {
      const blobs = detectBlobs(frame, baselineFrame);
      onFrame(frame, blobs);
    }

    setTimeout(loop, intervalMs);
  };

  loop();

  return () => {
    running = false;
  };
}

// === NODE.JS ADAPTER (for server-side or headless) ===

/**
 * Convert raw RGBA buffer to SimulatedFrame.
 * For use with Node.js camera libraries or ffmpeg.
 */
export function rgbaBufferToFrame(
  rgba: Uint8Array | Buffer,
  width: number,
  height: number,
  gridW: number,
  gridH: number,
  tileSize: number
): SimulatedFrame {
  const tiles = new Map<string, TilePixels>();

  // Calculate scaling factors
  const scaleX = width / (gridW * tileSize);
  const scaleY = height / (gridH * tileSize);

  for (let gy = 0; gy < gridH; gy++) {
    for (let gx = 0; gx < gridW; gx++) {
      const pixels: number[] = [];

      for (let ty = 0; ty < tileSize; ty++) {
        for (let tx = 0; tx < tileSize; tx++) {
          // Map grid position to source image position
          const srcX = Math.floor((gx * tileSize + tx) * scaleX);
          const srcY = Math.floor((gy * tileSize + ty) * scaleY);
          const idx = (srcY * width + srcX) * 4;

          // Convert RGB to grayscale
          const r = rgba[idx] || 0;
          const g = rgba[idx + 1] || 0;
          const b = rgba[idx + 2] || 0;
          const luminance = Math.round(0.299 * r + 0.587 * g + 0.114 * b);

          pixels.push(luminance);
        }
      }

      tiles.set(`${gx},${gy}`, pixels);
    }
  }

  return {
    tiles,
    globalBrightness: 0,
    colorTemp: 5500,
  };
}
