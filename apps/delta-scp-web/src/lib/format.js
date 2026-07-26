// Small presentational helpers — pure, no React.

export function fmtInt(n) {
  return (n ?? 0).toLocaleString('en-US');
}

export function fmtTokens(n) {
  if (n == null) return '0';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function fmtBytes(n) {
  if (n == null) return '0 B';
  if (n >= 1_048_576) return `${(n / 1_048_576).toFixed(1)} MB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${n} B`;
}

// Group flat symbolic_nodes by their top-level directory for a readable tree.
export function groupByDir(nodes) {
  const groups = new Map();
  for (const node of nodes) {
    const slash = node.path.indexOf('/');
    const dir = slash === -1 ? '·' : node.path.slice(0, slash);
    if (!groups.has(dir)) groups.set(dir, []);
    groups.get(dir).push(node);
  }
  return [...groups.entries()]
    .map(([dir, files]) => ({
      dir,
      files: files.slice().sort((a, b) => a.path.localeCompare(b.path)),
      symbolCount: files.reduce((s, f) => s + (f.symbols?.length ?? 0), 0),
    }))
    .sort((a, b) => a.dir.localeCompare(b.dir));
}

// Common LLM context windows, for the "does it fit?" budget view.
export const MODEL_WINDOWS = [
  { name: 'GPT-4o · 8k', tokens: 8_000 },
  { name: 'Claude · 32k', tokens: 32_000 },
  { name: '128k', tokens: 128_000 },
  { name: 'Claude 200k', tokens: 200_000 },
  { name: '1M', tokens: 1_000_000 },
];

// Color tokens for languages (CSS var names defined in styles.css).
export function langColor(lang) {
  const map = {
    typescript: '#3178c6',
    javascript: '#f0db4f',
    python: '#4b8bbe',
    go: '#00add8',
    rust: '#dea584',
    java: '#b07219',
    ruby: '#cc342d',
    markdown: '#6a737d',
    json: '#cbcb41',
    yaml: '#cb171e',
    other: '#8a94a6',
  };
  return map[lang] || map.other;
}
