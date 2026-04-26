/**
 * Vendored from firecrawl/open-lovable.
 * Do NOT modify vendored files in place · re-vendor instead.
 *
 * To upgrade:
 *   1. Bump VENDOR_SHA below to the new commit
 *   2. Re-port any changed sections from upstream into the lovable/ files
 *   3. Re-run Phase 1 verification (npm run dev · curl /health · curl /clone)
 */

export const VENDOR_REPO = 'firecrawl/open-lovable' as const;
export const VENDOR_SHA = '69bd93bae7a9c97ef989eb70aabe6797fb3dac89' as const;
export const VENDOR_DATE = '2025-11-19' as const;
export const VENDOR_LICENSE = 'MIT' as const;

export const VENDOR_FILES: ReadonlyArray<string> = [
  'app/api/generate-ai-code-stream/route.ts',
] as const;

export const VENDOR_URL = `https://github.com/${VENDOR_REPO}/tree/${VENDOR_SHA}` as const;

export interface VendorInfo {
  readonly repo: string;
  readonly sha: string;
  readonly date: string;
  readonly license: string;
  readonly files: ReadonlyArray<string>;
  readonly url: string;
}

export const VENDOR_INFO: VendorInfo = {
  repo: VENDOR_REPO,
  sha: VENDOR_SHA,
  date: VENDOR_DATE,
  license: VENDOR_LICENSE,
  files: VENDOR_FILES,
  url: VENDOR_URL,
};
