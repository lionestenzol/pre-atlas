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
  // true when this call's callee was a member/attribute access (`obj.exec()`),
  // absent (falsy) for a bare identifier call (`exec()`). Lets a risk-target
  // denylist require receiver qualification for names that collide with common,
  // unrelated methods (RegExp.exec, better-sqlite3's Database.exec) once member
  // calls are in scope — see RISKY_QUALIFIED_TARGETS in modernize.ts.
  qualified?: boolean;
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
  // Property-assignment query (JS/TS only): captures `prop` on the assigned
  // property name, e.g. `el.innerHTML = x` -> prop.text === 'innerHTML'. Absent
  // for languages where this isn't a meaningful risk shape.
  assignQuery?: string;
  // Qualified-call query: captures the WHOLE receiver chain + property text,
  // e.g. `document.write(x)` -> 'document.write', `this.db.exec(x)` ->
  // 'this.db.exec' — not restricted to a bare-identifier receiver. Exists
  // because some sinks (document.write, child_process.exec) are only dangerous
  // for a SPECIFIC receiver — the bare property name ('write', 'exec') is far
  // too generic to safely denylist against every member call (fs.write,
  // res.write, a DB's .exec(), RegExp.exec are ordinary and common). callQuery's
  // bare-property capture stays generic (needed so in-repo method calls resolve
  // against declared symbol names in the call graph); this is a separate,
  // precision-scoped view used only for risk-target matching against qualified
  // names.
  qualifiedCallQuery?: string;
}

export interface AstAssignment {
  source: string | null; // enclosing function name, or null at file scope
  property: string; // assigned property name
  type: 'assigns';
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
      (call function: (identifier) @callee.bare)
      (call function: (attribute attribute: (identifier) @callee.member))
    `,
    funcNodeTypes: new Set(['function_definition']),
    // Captures the full attribute chain (`os.system` -> 'os.system',
    // `pickle.loads` -> 'pickle.loads') so exec/deserialization names that
    // collide with unrelated methods (json.loads vs pickle.loads) can require
    // receiver qualification — see RISKY_QUALIFIED_TARGETS in modernize.ts.
    qualifiedCallQuery: `(call function: (attribute) @qualified)`,
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
    // Two call shapes, captured under DIFFERENT names so callers can tell them
    // apart: bare identifier (eval(x)) vs member/method (document.write(x),
    // child_process.exec(x)) — the latter is how most real-world risky sinks are
    // actually called, and was invisible before this query existed. The
    // distinction matters because a member callee name alone (e.g. 'exec') can't
    // tell RegExp.exec() apart from child_process.exec() — see extractCallEdgesAst.
    callQuery: `
      (call_expression function: (identifier) @callee.bare)
      (call_expression function: (member_expression property: (property_identifier) @callee.member))
    `,
    funcNodeTypes: new Set([
      'function_declaration', 'method_definition', 'function_expression', 'arrow_function',
    ]),
    assignQuery: `(assignment_expression left: (member_expression property: (property_identifier) @prop))`,
    // Whole receiver chain, not just a bare-identifier object — `this.db.exec`
    // captures as 'this.db.exec', not just 'db.exec' or missed entirely.
    qualifiedCallQuery: `(call_expression function: (member_expression) @qualified)`,
  },
  javascript: {
    wasm: 'tree-sitter-javascript.wasm',
    symbolQuery: `
      (function_declaration name: (identifier) @sym.function)
      (class_declaration name: (identifier) @sym.class)
      (method_definition name: (property_identifier) @sym.method)
    `,
    callQuery: `
      (call_expression function: (identifier) @callee.bare)
      (call_expression function: (member_expression property: (property_identifier) @callee.member))
    `,
    funcNodeTypes: new Set([
      'function_declaration', 'method_definition', 'function_expression', 'arrow_function',
    ]),
    assignQuery: `(assignment_expression left: (member_expression property: (property_identifier) @prop))`,
    qualifiedCallQuery: `(call_expression function: (member_expression) @qualified)`,
  },
  cpp: {
    wasm: 'tree-sitter-cpp.wasm',
    symbolQuery: `
      (function_definition declarator: (function_declarator declarator: (identifier) @sym.function))
      (function_definition declarator: (function_declarator declarator: (field_identifier) @sym.method))
      (class_specifier name: (type_identifier) @sym.class)
      (struct_specifier name: (type_identifier) @sym.struct)
      (enum_specifier name: (type_identifier) @sym.enum)
      (namespace_definition name: (namespace_identifier) @sym.namespace)
    `,
    callQuery: `(call_expression function: (identifier) @callee)`,
    funcNodeTypes: new Set(['function_definition']),
  },
  csharp: {
    wasm: 'tree-sitter-c_sharp.wasm',
    symbolQuery: `
      (class_declaration name: (identifier) @sym.class)
      (interface_declaration name: (identifier) @sym.interface)
      (struct_declaration name: (identifier) @sym.struct)
      (enum_declaration name: (identifier) @sym.enum)
      (method_declaration name: (identifier) @sym.method)
    `,
    callQuery: `(invocation_expression function: (identifier) @callee)`,
    funcNodeTypes: new Set(['method_declaration', 'constructor_declaration', 'local_function_statement']),
  },
  java: {
    wasm: 'tree-sitter-java.wasm',
    symbolQuery: `
      (class_declaration name: (identifier) @sym.class)
      (interface_declaration name: (identifier) @sym.interface)
      (enum_declaration name: (identifier) @sym.enum)
      (method_declaration name: (identifier) @sym.method)
    `,
    callQuery: `(method_invocation name: (identifier) @callee)`,
    funcNodeTypes: new Set(['method_declaration', 'constructor_declaration']),
  },
  go: {
    wasm: 'tree-sitter-go.wasm',
    symbolQuery: `
      (function_declaration name: (identifier) @sym.func)
      (method_declaration name: (field_identifier) @sym.func)
      (type_declaration (type_spec name: (type_identifier) @sym.type))
    `,
    callQuery: `(call_expression function: (identifier) @callee)`,
    funcNodeTypes: new Set(['function_declaration', 'method_declaration']),
  },
  // HTML is special-cased: its own grammar has no functions/classes, so the two
  // queries below are unused (the `html` branch in extract*Ast handles it before
  // the generic path). The value in an HTML file is the INLINE <script> JS —
  // where a vibe-coded app's logic and bugs actually live. The branch parses
  // <script> bodies and delegates to the javascript extractor with a line offset,
  // so inline JS surfaces as real symbols + call edges. wasm is present so
  // loadGrammar(LANGS.html) resolves the html parser.
  html: {
    wasm: 'tree-sitter-html.wasm',
    symbolQuery: '',
    callQuery: '',
    funcNodeTypes: new Set<string>(),
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

// Inline <script> bodies from an HTML document, each tagged with the 0-based row
// where its text begins, so JS symbols/edges map back to real HTML line numbers
// (htmlLine = jsLocalLine + rowOffset). External scripts (<script src=...>) have
// empty bodies and are skipped. Deterministic: same HTML -> same scripts, in order.
async function inlineScripts(content: string): Promise<Array<{ code: string; rowOffset: number }>> {
  await ensureInit();
  const lang = await loadGrammar(LANGS.html) as any;
  const parser = new Parser();
  parser.setLanguage(lang);
  const tree = parser.parse(content);
  const query = lang.query('(script_element (raw_text) @js)');
  const out: Array<{ code: string; rowOffset: number }> = [];
  for (const cap of query.captures(tree.rootNode)) {
    const code = cap.node.text;
    if (!code.trim()) continue; // external or empty <script>
    out.push({ code, rowOffset: cap.node.startPosition.row });
  }
  return out;
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
  if (language === 'html') {
    // Parse inline <script> bodies as JavaScript, offsetting each symbol's line
    // back to its position in the HTML file.
    const out: SymbolEntry[] = [];
    const seen = new Set<string>();
    for (const s of await inlineScripts(content)) {
      for (const sym of await extractSymbolsAst(s.code, 'javascript')) {
        const line = sym.line + s.rowOffset;
        const key = `${sym.kind}:${sym.name}:${line}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ kind: sym.kind, name: sym.name, line });
      }
    }
    out.sort((a, b) => a.line - b.line || a.name.localeCompare(b.name));
    return out;
  }
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

// Like enclosingFunctionName, but does not stop at the first (possibly anonymous)
// enclosing function — it keeps walking outward until it finds a NAMED one. Used
// only for property-assignment risk attribution (not the call graph, whose fan-in/
// fan-out semantics other tests depend on and which stays on enclosingFunctionName
// unchanged). A sink buried in an anonymous forEach/map callback should still name
// the outer named function an operator can actually navigate to (e.g.
// "updateZoneLogsUI"), not the uninformative "(module scope)".
function nearestNamedFunctionName(node: any, spec: LangSpec): string | null {
  let n = node.parent;
  while (n) {
    if (spec.funcNodeTypes.has(n.type)) {
      const named = n.childForFieldName?.('name');
      if (named) return named.text;
      const decl = n.childForFieldName?.('declarator');
      if (decl) {
        const inner = decl.childForFieldName?.('declarator');
        if (inner) return inner.text;
        if (decl.type === 'identifier') return decl.text;
      }
      // anonymous — keep walking past it instead of stopping here
    }
    n = n.parent;
  }
  return null;
}

export async function extractCallEdgesAst(content: string, language: string): Promise<AstEdge[]> {
  if (language === 'html') {
    // Call edges from each inline <script>, deduped across scripts. Edges carry
    // no line number, so no offset is needed — only the caller/callee names.
    const edges: AstEdge[] = [];
    const seen = new Set<string>();
    for (const s of await inlineScripts(content)) {
      for (const e of await extractCallEdgesAst(s.code, 'javascript')) {
        const key = `${e.source}->${e.target}->${e.qualified ?? false}`;
        if (seen.has(key)) continue;
        seen.add(key);
        edges.push(e);
      }
    }
    edges.sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target));
    return edges;
  }
  const p = await parse(content, language);
  if (!p) return [];
  const query = p.lang.query(p.spec.callQuery);
  const edges: AstEdge[] = [];
  const seen = new Set<string>();
  for (const cap of query.captures(p.tree.rootNode)) {
    const callee = cap.node.text;
    const caller = enclosingFunctionName(cap.node, p.spec);
    if (!caller) continue;
    // Capture name is 'callee.member' for a member/attribute call (split query,
    // see LANGS.typescript/javascript/python), 'callee.bare' or plain 'callee'
    // (single-form languages) otherwise.
    const qualified = cap.name.endsWith('.member');
    const key = `${caller}->${callee}->${cap.name}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ source: caller, target: callee, type: 'calls', ...(qualified ? { qualified: true } : {}) });
  }
  edges.sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target));
  return edges;
}

// Qualified calls (`document.write(x)` -> target 'document.write'), for languages
// where qualifiedCallQuery is defined (JS/TS). See LangSpec.qualifiedCallQuery for
// why this exists as a separate view from extractCallEdgesAst's bare-property
// target: a sink like document.write is only dangerous for that specific
// receiver, and 'write' alone is too generic to denylist safely.
export async function extractQualifiedCallEdgesAst(content: string, language: string): Promise<AstEdge[]> {
  if (language === 'html') {
    const edges: AstEdge[] = [];
    const seen = new Set<string>();
    for (const s of await inlineScripts(content)) {
      for (const e of await extractQualifiedCallEdgesAst(s.code, 'javascript')) {
        const key = `${e.source}->${e.target}`;
        if (seen.has(key)) continue;
        seen.add(key);
        edges.push(e);
      }
    }
    return edges;
  }
  const p = await parse(content, language);
  if (!p || !p.spec.qualifiedCallQuery) return [];
  const query = p.lang.query(p.spec.qualifiedCallQuery);
  const edges: AstEdge[] = [];
  const seen = new Set<string>();
  for (const cap of query.captures(p.tree.rootNode)) {
    const target = cap.node.text; // "object.property"
    const caller = enclosingFunctionName(cap.node, p.spec);
    if (!caller) continue;
    const key = `${caller}->${target}`;
    if (seen.has(key)) continue;
    seen.add(key);
    edges.push({ source: caller, target, type: 'calls' });
  }
  return edges;
}

// Property assignments (`obj.prop = value`), for languages where assignQuery is
// defined (JS/TS). This is a DIFFERENT risk shape than a call: `el.innerHTML = x`
// is the dominant real-world JS/web XSS pattern and a call-only scan is
// structurally blind to it (verified: proof-run 2026-07-13 on URBANNOMAD — a repo
// with real innerHTML-assignment XSS reported "0 risky surfaces" because this
// shape was invisible). Risk-target filtering happens in modernize.ts, same
// separation as extractCallEdgesAst / RISKY_CALL_TARGETS.
export async function extractPropertyAssignmentsAst(content: string, language: string): Promise<AstAssignment[]> {
  if (language === 'html') {
    const out: AstAssignment[] = [];
    const seen = new Set<string>();
    for (const s of await inlineScripts(content)) {
      for (const a of await extractPropertyAssignmentsAst(s.code, 'javascript')) {
        const key = `${a.source}=${a.property}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(a);
      }
    }
    return out;
  }
  const p = await parse(content, language);
  if (!p || !p.spec.assignQuery) return [];
  const query = p.lang.query(p.spec.assignQuery);
  const out: AstAssignment[] = [];
  const seen = new Set<string>();
  for (const cap of query.captures(p.tree.rootNode)) {
    const property = cap.node.text;
    const source = nearestNamedFunctionName(cap.node, p.spec);
    const key = `${source}=${property}=${cap.node.startPosition.row}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ source, property, type: 'assigns' });
  }
  return out;
}
