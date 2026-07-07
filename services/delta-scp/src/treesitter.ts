// Delta SCP · tree-sitter AST extractor
//
// The regex extractor in compressor.ts is cheap and deterministic but structurally
// blind: it only sees top-level declarations that match a per-line pattern, it has
// NO patterns for several languages (C, C++, C#, ... return zero symbols today), and
// it cannot produce call/inherits/implements edges — only imports.
//
// This module is the real-AST upgrade named in graph.ts. It parses source with
// tree-sitter (web-tree-sitter WASM runtime + precompiled grammars from
// tree-sitter-wasms) and extracts:
//   - symbols (functions/classes/structs/...) with exact line numbers, for ALL
//     configured languages including the legacy ones regex misses; and
//   - intra-file call edges (caller -> callee), the edge type regex cannot see.
//
// Assemble-first: web-tree-sitter is the canonical portable (no node-gyp) parser;
// grammars are precompiled .wasm, so a customer runs this with zero build toolchain.
// It is ADDITIVE — the regex core stays as the fast/sync fallback; this async path
// is opt-in and raises fidelity without changing the CompressedState schema.

import { createRequire } from 'module';
import type { SymbolEntry } from './compressor.js';

// web-tree-sitter 0.22.x ships a CommonJS default export; grammars in
// tree-sitter-wasms are compiled at the matching ABI. Loaded via createRequire so
// this ESM module can resolve the runtime + the .wasm files.
const require = createRequire(import.meta.url);
// eslint-disable-next-line @typescript-eslint/no-var-requires
const Parser = require('web-tree-sitter');

export interface AstEdge {
  source: string; // caller symbol name
  target: string; // callee name
  type: 'calls';
}

interface LangSpec {
  wasm: string; // filename under tree-sitter-wasms/out
  // Symbol query: every capture is named `sym.<kind>` and anchored on the NAME node,
  // so kind = capture.name after the dot, symbol name = node.text, line = row+1.
  symbolQuery: string;
  // Call query: captures `callee` on the callee identifier node.
  callQuery: string;
  // Node types that count as an enclosing function/method for caller attribution.
  funcNodeTypes: Set<string>;
}

// delta-scp language name (compressor.EXT_LANGUAGE) -> tree-sitter spec.
// Legacy-first: C is the headline case (regex yields nothing). More languages are
// mechanical additions — a wasm name + two query strings + the func node types.
const LANGS: Record<string, LangSpec> = {
  c: {
    wasm: 'tree-sitter-c.wasm',
    symbolQuery: `
      (function_definition declarator: (function_declarator declarator: (identifier) @sym.function))
      (struct_specifier name: (type_identifier) @sym.struct)
      (enum_specifier name: (type_identifier) @sym.enum)
      (type_definition declarator: (type_identifier) @sym.type)
    `,
    callQuery: `(call_expression function: (identifier) @callee)`,
    funcNodeTypes: new Set(['function_definition']),
  },
  python: {
    wasm: 'tree-sitter-python.wasm',
    symbolQuery: `
      (function_definition name: (identifier) @sym.def)
      (class_definition name: (identifier) @sym.class)
    `,
    callQuery: `
      (call function: (identifier) @callee)
      (call function: (attribute attribute: (identifier) @callee))
    `,
    funcNodeTypes: new Set(['function_definition']),
  },
  typescript: {
    wasm: 'tree-sitter-typescript.wasm',
    symbolQuery: `
      (function_declaration name: (identifier) @sym.function)
      (class_declaration name: (type_identifier) @sym.class)
      (interface_declaration name: (type_identifier) @sym.interface)
      (enum_declaration name: (identifier) @sym.enum)
      (type_alias_declaration name: (type_identifier) @sym.type)
      (method_definition name: (property_identifier) @sym.method)
    `,
    callQuery: `(call_expression function: (identifier) @callee)`,
    funcNodeTypes: new Set([
      'function_declaration', 'method_definition', 'function_expression', 'arrow_function',
    ]),
  },
  javascript: {
    wasm: 'tree-sitter-javascript.wasm',
    symbolQuery: `
      (function_declaration name: (identifier) @sym.function)
      (class_declaration name: (identifier) @sym.class)
      (method_definition name: (property_identifier) @sym.method)
    `,
    callQuery: `(call_expression function: (identifier) @callee)`,
    funcNodeTypes: new Set([
      'function_declaration', 'method_definition', 'function_expression', 'arrow_function',
    ]),
  },
};

export function supportsAst(language: string): boolean {
  return language in LANGS;
}

export function astLanguages(): string[] {
  return Object.keys(LANGS);
}

let parserInit: Promise<void> | null = null;
const grammarCache = new Map<string, unknown>();

async function ensureInit(): Promise<void> {
  if (!parserInit) parserInit = Parser.init();
  await parserInit;
}

async function loadGrammar(spec: LangSpec): Promise<unknown> {
  const cached = grammarCache.get(spec.wasm);
  if (cached) return cached;
  const wasmPath = require.resolve(`tree-sitter-wasms/out/${spec.wasm}`);
  const lang = await Parser.Language.load(wasmPath);
  grammarCache.set(spec.wasm, lang);
  return lang;
}

// Deterministic: same (content, language) -> same symbols/edges, every run.
async function parse(content: string, language: string): Promise<{ tree: any; lang: any; spec: LangSpec } | null> {
  const spec = LANGS[language];
  if (!spec) return null;
  await ensureInit();
  const lang = await loadGrammar(spec);
  const parser = new Parser();
  parser.setLanguage(lang);
  const tree = parser.parse(content);
  return { tree, lang, spec };
}

export async function extractSymbolsAst(content: string, language: string): Promise<SymbolEntry[]> {
  const p = await parse(content, language);
  if (!p) return [];
  const query = p.lang.query(p.spec.symbolQuery);
  const out: SymbolEntry[] = [];
  const seen = new Set<string>();
  for (const cap of query.captures(p.tree.rootNode)) {
    const kind = cap.name.startsWith('sym.') ? cap.name.slice(4) : cap.name;
    const name = cap.node.text;
    const line = cap.node.startPosition.row + 1;
    const key = `${kind}:${name}:${line}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ kind, name, line });
  }
  out.sort((a, b) => a.line - b.line || a.name.localeCompare(b.name));
  return out;
}

// Walk up from a call node to the nearest enclosing function and read its name.
// Returns null for calls at file scope (skipped, to avoid noise edges).
function enclosingFunctionName(node: any, spec: LangSpec): string | null {
  let n = node.parent;
  while (n) {
    if (spec.funcNodeTypes.has(n.type)) {
      // C: declarator -> function_declarator -> identifier; others: `name` field.
      const named = n.childForFieldName?.('name');
      if (named) return named.text;
      const decl = n.childForFieldName?.('declarator');
      if (decl) {
        const inner = decl.childForFieldName?.('declarator');
        if (inner) return inner.text;
        if (decl.type === 'identifier') return decl.text;
      }
      return null; // anonymous function/arrow
    }
    n = n.parent;
  }
  return null;
}

export async function extractCallEdgesAst(content: string, language: string): Promise<AstEdge[]> {
  const p = await parse(content, language);
  if (!p) return [];
  const query = p.lang.query(p.spec.callQuery);
  const edges: AstEdge[] = [];
  const seen = new Set<string>();
  for (const cap of query.captures(p.tree.rootNode)) {
    const callee = cap.node.text;
    const caller = enclosingFunctionName(cap.node, p.spec);
    if (!caller) continue;
    const key = `${caller}->${callee}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ source: caller, target: callee, type: 'calls' });
  }
  edges.sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target));
  return edges;
}
