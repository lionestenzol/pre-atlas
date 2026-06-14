// canvas-engine · vision backend selector
//
// The image (vision) clone + edit paths can run their Claude completion two ways:
//   - cli: shell out to the local `claude` binary (subscription auth, no key)
//   - sdk: call the Anthropic API with ANTHROPIC_API_KEY
//
// CANVAS_ENGINE_VISION_BACKEND picks the strategy:
//   - 'auto' (default): try the CLI first, fall back to the SDK only if the CLI
//      fails AND a key is configured. Best for a normal terminal where `claude`
//      is logged in (zero marginal cost).
//   - 'sdk': use the SDK directly (requires a key). Use this when you have a key
//      and the CLI can't authenticate — e.g. a host-managed Claude session where
//      a spawned `claude` 401s (CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1).
//   - 'cli': use the CLI only, never fall back to the SDK.

export type VisionBackend = 'auto' | 'cli' | 'sdk';

export function resolveVisionBackend(): VisionBackend {
  const raw = (process.env.CANVAS_ENGINE_VISION_BACKEND ?? 'auto')
    .trim()
    .toLowerCase();
  if (raw === 'cli' || raw === 'sdk') {
    return raw;
  }
  return 'auto';
}
