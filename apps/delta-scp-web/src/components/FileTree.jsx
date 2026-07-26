import React, { useState } from 'react';
import { fmtTokens, fmtBytes, groupByDir, langColor } from '../lib/format.js';

// The symbolic skeleton, rendered readably: files grouped by top-level directory,
// each file expandable to its top-level symbols (kind · name · line).
export default function FileTree({ nodes }) {
  const groups = groupByDir(nodes);
  return (
    <section className="panel tree">
      <h2 className="panel-title">
        Symbolic skeleton <span className="muted-count">{nodes.length} files</span>
      </h2>
      <div className="tree-body">
        {groups.map((g) => (
          <DirGroup key={g.dir} group={g} />
        ))}
      </div>
    </section>
  );
}

function DirGroup({ group }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="dir-group">
      <button
        className="dir-head"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`Directory ${group.dir}, ${group.files.length} files, ${group.symbolCount} symbols`}
      >
        <span className={`caret ${open ? 'caret-open' : ''}`} aria-hidden="true">▸</span>
        <span className="dir-name">{group.dir}</span>
        <span className="dir-meta">
          {group.files.length} files · {group.symbolCount} symbols
        </span>
      </button>
      {open && (
        <div className="dir-files">
          {group.files.map((f) => (
            <FileRow key={f.path} file={f} />
          ))}
        </div>
      )}
    </div>
  );
}

function FileRow({ file }) {
  const hasSymbols = (file.symbols?.length ?? 0) > 0;
  const [open, setOpen] = useState(false);
  const name = file.path.split('/').pop();
  return (
    <div className="file-row">
      <button
        className={`file-head ${hasSymbols ? '' : 'file-head-flat'}`}
        onClick={() => hasSymbols && setOpen((o) => !o)}
        aria-expanded={hasSymbols ? open : undefined}
        disabled={!hasSymbols}
        aria-label={`${name}, ${file.language}, ${file.symbols?.length ?? 0} symbols`}
      >
        <span
          className="lang-pill"
          style={{ background: langColor(file.language) }}
          aria-hidden="true"
        />
        <span className="file-name">{name}</span>
        {hasSymbols && <span className="sym-badge">{file.symbols.length}</span>}
        <span className="file-meta">
          {fmtTokens(file.tokens_est)} tok · {fmtBytes(file.bytes)}
        </span>
      </button>
      {open && hasSymbols && (
        <ul className="symbol-list">
          {file.symbols.map((s, i) => (
            <li key={i}>
              <span className={`kind kind-${s.kind}`}>{s.kind}</span>
              <span className="sym-name">{s.name}</span>
              <span className="sym-line">:{s.line}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
