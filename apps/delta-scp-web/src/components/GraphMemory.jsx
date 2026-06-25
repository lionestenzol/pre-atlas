import React from 'react';
import { fmtInt } from '../lib/format.js';

// The graph-memory layer — the differentiator. The compression (file tree +
// symbols) is commoditized; what sets Delta SCP apart is the AST graph: every
// file/symbol is a node, and resolved import edges connect them. This is the
// `ast_nodes`/`ast_edges` layer (migration 006) the production HTTP gateway does
// NOT expose — surfaced here straight from the engine's buildGraphRows().
export default function GraphMemory({ graph }) {
  if (!graph) return null;
  const types = Object.entries(graph.node_types || {}).sort((a, b) => b[1] - a[1]);
  const imports = graph.imports || [];

  // Rank files by import fan-in/out — the "hub" modules an LLM should read first.
  const degree = new Map();
  for (const e of imports) {
    degree.set(e.from, (degree.get(e.from) || 0) + 1);
    degree.set(e.to, (degree.get(e.to) || 0) + 1);
  }
  const hubs = [...degree.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);

  return (
    <section className="panel graph">
      <div className="graph-head">
        <h2 className="panel-title">
          Graph-memory layer <span className="badge">the differentiator</span>
        </h2>
        <div className="graph-counts">
          <span><strong>{fmtInt(graph.node_count)}</strong> nodes</span>
          <span><strong>{fmtInt(graph.edge_count)}</strong> import edges</span>
        </div>
      </div>

      <p className="graph-blurb">
        Not just a skeleton — a queryable AST graph. Files &amp; symbols are nodes;
        resolved <code>imports</code> edges wire them together, so an agent can pull a
        file <em>plus its one-hop neighbours</em> instead of guessing what to read.
      </p>

      <div className="graph-grid">
        <div className="graph-col">
          <h3 className="sub-title">Node types</h3>
          <ul className="type-list">
            {types.length === 0 && <li className="empty">no nodes</li>}
            {types.map(([t, n]) => (
              <li key={t}>
                <span className={`dot dot-${t}`} aria-hidden="true" />
                <span className="type-name">{t}</span>
                <span className="type-count">{fmtInt(n)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="graph-col">
          <h3 className="sub-title">Most-connected files (read these first)</h3>
          <ul className="hub-list">
            {hubs.length === 0 && <li className="empty">no import edges resolved within repo</li>}
            {hubs.map(([file, deg]) => (
              <li key={file}>
                <code className="hub-path">{file}</code>
                <span className="hub-deg">{deg}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {imports.length > 0 && (
        <details className="edge-details">
          <summary>{fmtInt(imports.length)} import edges</summary>
          <ul className="edge-list">
            {imports.slice(0, 200).map((e, i) => (
              <li key={i}>
                <code>{e.from}</code>
                <span className="arrow">→</span>
                <code>{e.to}</code>
              </li>
            ))}
            {imports.length > 200 && <li className="empty">…and {imports.length - 200} more</li>}
          </ul>
        </details>
      )}
    </section>
  );
}
