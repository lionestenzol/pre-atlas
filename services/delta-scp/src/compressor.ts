// Delta SCP · Symbolic Compression Protocol
//
// Turns a repository into a compact symbolic map: instead of shipping every
// byte of source to a downstream consumer (e.g. an LLM context window), we emit
// a structural skeleton — file tree plus the top-level symbols (functions,
// classes, exports) of each source file. That is the "compression": a large
// repo collapses to a small JSON map, and we report the estimated token yield.
//
// Symbol extraction is heuristic (lightweight per-language regexes, not a full
// AST). It is intentionally cheap and language-agnostic; it favours breadth and
// determinism over perfect parsing.

export interface SourceFile {
  path: string; // repo-relative, posix separators
  content: string;
}

export interface SymbolEntry {
  kind: string; // function | class | interface | type | const | def | struct | ...
  name: string;
  line: number; // 1-based
}

export interface SymbolicNode {
  path: string;
  language: string;
  bytes: number;
  tokens_est: number;
  symbols: SymbolEntry[];
}

export interface CompressionStats {
  files_scanned: number;
  files_included: number;
  bytes: number;
  raw_tokens_est: number; // tokens of the full source
  compressed_tokens_est: number; // tokens of this symbolic map
  token_yield: number; // tokens saved (raw - compressed)
  compression_ratio: number; // compressed / raw, rounded to 4dp
}

export interface CompressedState extends Record<string, unknown> {
  protocol: 'DELTA_SCP';
  version: string;
  status: 'compressed';
  repo: string;
  generated_at: string;
  stats: CompressionStats;
  languages: Record<string, number>; // language -> file count
  symbolic_nodes: SymbolicNode[];
}

export const PROTOCOL_VERSION = '1';

// Approximate tokenization: ~4 chars per token. Good enough for a yield estimate
// without pulling in a model-specific tokenizer.
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4);
}

const EXT_LANGUAGE: Record<string, string> = {
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  py: 'python',
  go: 'go',
  rs: 'rust',
  java: 'java',
  rb: 'ruby',
  php: 'php',
  c: 'c',
  h: 'c',
  cpp: 'cpp',
  hpp: 'cpp',
  cs: 'csharp',
  swift: 'swift',
  kt: 'kotlin',
  sql: 'sql',
  sh: 'shell',
  html: 'html',
  md: 'markdown',
  json: 'json',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'toml',
};

export function languageForPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  return EXT_LANGUAGE[ext] ?? 'other';
}

// Per-language symbol patterns. Each regex has a capture group for the name and
// is applied per line, so reported line numbers are exact.
const SYMBOL_PATTERNS: Record<string, Array<{ kind: string; re: RegExp }>> = {
  typescript: [
    { kind: 'class', re: /^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)/ },
    { kind: 'interface', re: /^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)/ },
    { kind: 'type', re: /^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)/ },
    { kind: 'function', re: /^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/ },
    { kind: 'const', re: /^\s*export\s+const\s+([A-Za-z_$][\w$]*)/ },
    { kind: 'enum', re: /^\s*(?:export\s+)?enum\s+([A-Za-z_$][\w$]*)/ },
  ],
  python: [
    { kind: 'class', re: /^\s*class\s+([A-Za-z_]\w*)/ },
    { kind: 'def', re: /^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)/ },
  ],
  go: [
    { kind: 'func', re: /^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)/ },
    { kind: 'type', re: /^\s*type\s+([A-Za-z_]\w*)/ },
  ],
  rust: [
    { kind: 'fn', re: /^\s*(?:pub\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)/ },
    { kind: 'struct', re: /^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)/ },
    { kind: 'enum', re: /^\s*(?:pub\s+)?enum\s+([A-Za-z_]\w*)/ },
    { kind: 'trait', re: /^\s*(?:pub\s+)?trait\s+([A-Za-z_]\w*)/ },
  ],
  ruby: [
    { kind: 'class', re: /^\s*class\s+([A-Za-z_]\w*)/ },
    { kind: 'def', re: /^\s*def\s+([A-Za-z_][\w?!]*)/ },
  ],
  java: [
    { kind: 'class', re: /^\s*(?:public\s+|private\s+|protected\s+|abstract\s+|final\s+)*class\s+([A-Za-z_]\w*)/ },
    { kind: 'interface', re: /^\s*(?:public\s+|private\s+)?interface\s+([A-Za-z_]\w*)/ },
  ],
};

// typescript patterns also serve javascript
SYMBOL_PATTERNS.javascript = SYMBOL_PATTERNS.typescript;

export function extractSymbols(content: string, language: string): SymbolEntry[] {
  const patterns = SYMBOL_PATTERNS[language];
  if (!patterns) return [];
  const symbols: SymbolEntry[] = [];
  const lines = content.split('\n');
  for (let i = 0; i < lines.length; i++) {
    for (const { kind, re } of patterns) {
      const m = re.exec(lines[i]);
      if (m) {
        symbols.push({ kind, name: m[1], line: i + 1 });
        break; // one symbol kind per line
      }
    }
  }
  return symbols;
}

export type Extractor = 'regex' | 'treesitter';

// Assemble the CompressedState from already-built symbolic nodes. Shared by the
// sync (regex) and async (tree-sitter) compressors so the stats/body contract is
// defined once. compressed_tokens_est is measured against the serialized map
// minus the stats block (which depends on this number), so the body is built first.
function assemble(
  repo: string,
  generatedAt: string,
  filesScanned: number,
  symbolicNodes: SymbolicNode[],
  languages: Record<string, number>,
  bytes: number,
  rawTokens: number,
): CompressedState {
  const body = {
    protocol: 'DELTA_SCP' as const,
    version: PROTOCOL_VERSION,
    status: 'compressed' as const,
    repo,
    generated_at: generatedAt,
    languages,
    symbolic_nodes: symbolicNodes,
  };
  const compressedTokens = estimateTokens(JSON.stringify(body));
  const rawTokensSafe = rawTokens;
  const ratio = rawTokensSafe > 0
    ? Math.round((compressedTokens / rawTokensSafe) * 10000) / 10000
    : 0;
  return {
    ...body,
    stats: {
      files_scanned: filesScanned,
      files_included: symbolicNodes.length,
      bytes,
      raw_tokens_est: rawTokensSafe,
      compressed_tokens_est: compressedTokens,
      token_yield: rawTokensSafe - compressedTokens,
      compression_ratio: ratio,
    },
  };
}

/**
 * Pure compression: given the source files of a repo, produce the symbolic map.
 * No I/O — fully deterministic and unit-testable. generatedAt is injected (not
 * read from the clock) so identical repo+files inputs always produce identical
 * output; the I/O boundary (compressRepository) supplies the real timestamp.
 *
 * This is the regex extractor — cheap, sync, and the fallback. For higher-fidelity
 * symbols on legacy languages the regex misses (C/C++/C#/...), see compressTreeAsync.
 */
export function compressTree(
  repo: string,
  files: SourceFile[],
  generatedAt = '1970-01-01T00:00:00.000Z',
): CompressedState {
  const symbolicNodes: SymbolicNode[] = [];
  const languages: Record<string, number> = {};
  let bytes = 0;
  let rawTokens = 0;

  // Stable ordering so the output is deterministic regardless of input order.
  const sorted = [...files].sort((a, b) => a.path.localeCompare(b.path));

  for (const file of sorted) {
    const language = languageForPath(file.path);
    const fileBytes = Buffer.byteLength(file.content, 'utf8');
    bytes += fileBytes;
    rawTokens += estimateTokens(file.content);
    languages[language] = (languages[language] ?? 0) + 1;
    symbolicNodes.push({
      path: file.path,
      language,
      bytes: fileBytes,
      tokens_est: estimateTokens(file.content),
      symbols: extractSymbols(file.content, language),
    });
  }

  return assemble(repo, generatedAt, files.length, symbolicNodes, languages, bytes, rawTokens);
}

/**
 * Same contract as compressTree, but with a selectable extractor. With
 * extractor='treesitter' it parses supported languages with a real AST
 * (tree-sitter) — extracting symbols the regex has no pattern for (C structs/
 * funcs, etc.) — and falls back to the regex extractor per-file on any parse
 * error or for unsupported languages. extractor='regex' delegates to compressTree
 * unchanged. Additive and opt-in (config.extractor / SCP_EXTRACTOR); the WASM
 * runtime is loaded lazily so the regex path never pays for it.
 */
export async function compressTreeAsync(
  repo: string,
  files: SourceFile[],
  generatedAt = '1970-01-01T00:00:00.000Z',
  extractor: Extractor = 'regex',
): Promise<CompressedState> {
  if (extractor !== 'treesitter') {
    return compressTree(repo, files, generatedAt);
  }
  const { extractSymbolsAst, supportsAst } = await import('./treesitter.js');

  const symbolicNodes: SymbolicNode[] = [];
  const languages: Record<string, number> = {};
  let bytes = 0;
  let rawTokens = 0;
  const sorted = [...files].sort((a, b) => a.path.localeCompare(b.path));

  for (const file of sorted) {
    const language = languageForPath(file.path);
    const fileBytes = Buffer.byteLength(file.content, 'utf8');
    bytes += fileBytes;
    rawTokens += estimateTokens(file.content);
    languages[language] = (languages[language] ?? 0) + 1;

    let symbols: SymbolEntry[];
    if (supportsAst(language)) {
      try {
        symbols = await extractSymbolsAst(file.content, language);
      } catch {
        symbols = extractSymbols(file.content, language); // fail-soft to regex
      }
    } else {
      symbols = extractSymbols(file.content, language);
    }

    symbolicNodes.push({
      path: file.path,
      language,
      bytes: fileBytes,
      tokens_est: estimateTokens(file.content),
      symbols,
    });
  }

  return assemble(repo, generatedAt, files.length, symbolicNodes, languages, bytes, rawTokens);
}
