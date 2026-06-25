import React, { useEffect, useState } from 'react';
import { submitRepo, checkHealth } from './api.js';
import { copyText } from './lib/clipboard.js';
import ContextBudget from './components/ContextBudget.jsx';
import GraphMemory from './components/GraphMemory.jsx';
import FileTree from './components/FileTree.jsx';

const EXAMPLES = [
  'https://github.com/sindresorhus/yocto-queue.git',
  'https://github.com/sindresorhus/p-map.git',
  'https://github.com/expressjs/express.git',
];

export default function App() {
  const [url, setUrl] = useState('');
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [online, setOnline] = useState(null);
  const [copied, setCopied] = useState('');

  useEffect(() => {
    let alive = true;
    const ping = () => checkHealth().then((ok) => alive && setOnline(ok));
    ping();
    const t = setInterval(ping, 10000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  async function run(repoUrl) {
    const target = (repoUrl ?? url).trim();
    if (!target) return;
    setUrl(target);
    setLoading(true);
    setError('');
    setJob(null);
    try {
      const result = await submitRepo(target);
      setJob(result);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function copy(kind) {
    if (!job?.compressed_state) return;
    const text =
      kind === 'markdown'
        ? toMarkdown(job)
        : JSON.stringify(job.compressed_state, null, 2);
    const ok = await copyText(text);
    // Copy feedback is local to the buttons — never the compression error box.
    setCopied(ok ? kind : `${kind}:fail`);
    setTimeout(() => setCopied(''), ok ? 1800 : 2600);
  }

  const state = job?.compressed_state;

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-top">
          <div className="brand">
            <span className="logo" aria-hidden="true">◭</span>
            <span className="brand-name">Delta SCP</span>
          </div>
          <HealthBadge online={online} />
        </div>
        <h1>Paste a repo → get a token-cheap context skeleton</h1>
        <p className="tagline">
          A queryable <strong>graph-memory map</strong> of any codebase — files &amp;
          symbols as nodes, imports as edges — that collapses a huge repo into a few
          thousand tokens an LLM can actually hold.
        </p>

        <form
          className="submit-bar"
          onSubmit={(e) => {
            e.preventDefault();
            run();
          }}
        >
          <input
            type="url"
            inputMode="url"
            aria-label="Repository URL to compress"
            placeholder="https://github.com/owner/repo.git"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          <button type="submit" disabled={loading || !url.trim()}>
            {loading ? 'Compressing…' : 'Compress'}
          </button>
        </form>

        <div className="examples">
          <span id="examples-label">Try:</span>
          <div className="ex-chips" role="group" aria-labelledby="examples-label">
            {EXAMPLES.map((ex) => {
              const name = ex.replace('https://github.com/', '').replace('.git', '');
              return (
                <button
                  key={ex}
                  className="ex-chip"
                  disabled={loading}
                  onClick={() => run(ex)}
                  aria-label={`Compress example repository ${name}`}
                >
                  {name}
                </button>
              );
            })}
          </div>
        </div>
      </header>

      {loading && (
        <div className="loading" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <span>Cloning &amp; extracting symbols from <code>{url}</code>…</span>
        </div>
      )}

      {error && (
        <div className="error-box" role="alert">
          <strong>Compression failed.</strong>
          <pre>{error}</pre>
        </div>
      )}

      {state && !loading && (
        <main className="results" aria-label="Compression result">
          <div className="results-head">
            <div>
              <h2 className="repo-title">{state.repo.replace('https://github.com/', '')}</h2>
              <span className="proto">
                {state.protocol} v{state.version} · {state.stats.files_included} files ·{' '}
                {Object.keys(state.languages).length} languages
              </span>
            </div>
            <div className="copy-actions" aria-live="polite">
              <button
                className="copy-btn primary"
                onClick={() => copy('json')}
                aria-label="Copy the symbolic skeleton as JSON to the clipboard"
              >
                {copied === 'json' ? '✓ Copied' : copied === 'json:fail' ? 'Copy failed' : 'Copy skeleton JSON'}
              </button>
              <button
                className="copy-btn"
                onClick={() => copy('markdown')}
                aria-label="Copy the symbolic skeleton as Markdown to the clipboard"
              >
                {copied === 'markdown' ? '✓ Copied' : copied === 'markdown:fail' ? 'Copy failed' : 'Copy as Markdown'}
              </button>
            </div>
          </div>

          <ContextBudget stats={state.stats} />
          <GraphMemory graph={job.graph} />
          <FileTree nodes={state.symbolic_nodes} />
        </main>
      )}

      {!state && !loading && !error && (
        <div className="empty-state">
          <p>
            The skeleton ships the <em>shape</em> of a repo — every file plus its
            top-level functions, classes, and exports — instead of every byte. Drop a
            public Git URL above to see it live.
          </p>
        </div>
      )}

      <footer className="foot">
        <span>
          Live against the Delta SCP engine on <code>:3012</code> · symbolic compression
          + AST graph-memory
        </span>
      </footer>
    </div>
  );
}

function HealthBadge({ online }) {
  const label = online == null ? 'checking…' : online ? 'service online' : 'service offline';
  const cls = online == null ? 'dot-wait' : online ? 'dot-on' : 'dot-off';
  return (
    <div className="health" role="status" aria-live="polite" aria-label={`Delta SCP ${label} on port 3012`}>
      <span className={`health-dot ${cls}`} aria-hidden="true" />
      {label} · :3012
    </div>
  );
}

// Compact Markdown rendering of the skeleton — the flue/LLM-paste payload.
function toMarkdown(job) {
  const s = job.compressed_state;
  const lines = [
    `# ${s.repo}`,
    ``,
    `> Delta SCP ${s.protocol} v${s.version} — ${s.stats.files_included} files, `,
    `> ${s.stats.compressed_tokens_est} tokens (${s.stats.raw_tokens_est} raw, `,
    `> ${s.stats.token_yield} saved).`,
    ``,
  ];
  for (const node of s.symbolic_nodes) {
    if (!node.symbols?.length) continue;
    lines.push(`## ${node.path}`);
    for (const sym of node.symbols) {
      lines.push(`- \`${sym.kind}\` **${sym.name}** :${sym.line}`);
    }
    lines.push('');
  }
  if (job.graph?.imports?.length) {
    lines.push(`## imports`);
    for (const e of job.graph.imports) lines.push(`- ${e.from} → ${e.to}`);
  }
  return lines.join('\n');
}
