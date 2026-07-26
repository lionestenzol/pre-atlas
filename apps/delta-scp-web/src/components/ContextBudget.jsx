import React, { useState } from 'react';
import { fmtTokens, fmtInt, MODEL_WINDOWS } from '../lib/format.js';

// "Context budget" view: how the symbolic skeleton compares to raw source, plus
// an interactive budget slider that answers "does this fit in my context window?"
export default function ContextBudget({ stats }) {
  const raw = stats.raw_tokens_est || 0;
  const compressed = stats.compressed_tokens_est || 0;
  const yieldTok = stats.token_yield || 0;
  const reductionPct = raw > 0 ? Math.round((yieldTok / raw) * 1000) / 10 : 0;

  const [budget, setBudget] = useState(128_000);
  const fits = compressed <= budget;
  const headroom = budget - compressed;
  const fillPct = Math.min(100, budget > 0 ? (compressed / budget) * 100 : 0);

  return (
    <section className="panel budget">
      <h2 className="panel-title">Context budget</h2>

      <div className="stat-row">
        <Stat label="Raw source" value={fmtTokens(raw)} sub="tokens" tone="muted" />
        <Stat label="Skeleton" value={fmtTokens(compressed)} sub="tokens" tone="accent" />
        <Stat label="Saved" value={fmtTokens(yieldTok)} sub="tokens" tone="good" />
        <Stat label="Reduction" value={`${reductionPct}%`} sub="vs raw" tone="good" />
      </div>

      {/* Raw vs skeleton bar */}
      <div className="compare-bar" title={`skeleton is ${reductionPct}% smaller than raw`}>
        <div className="compare-fill" style={{ width: `${Math.max(2, 100 - reductionPct)}%` }}>
          <span>skeleton {fmtTokens(compressed)}</span>
        </div>
        <span className="compare-raw-label">raw {fmtTokens(raw)}</span>
      </div>

      {/* Interactive budget slider */}
      <div className="slider-wrap">
        <div className="slider-head">
          <label htmlFor="budget">Your context budget</label>
          <strong>{fmtInt(budget)} tokens</strong>
        </div>
        <input
          id="budget"
          type="range"
          min={2000}
          max={1_000_000}
          step={2000}
          value={budget}
          onChange={(e) => setBudget(Number(e.target.value))}
          aria-label="Context budget in tokens"
          aria-valuetext={`${fmtInt(budget)} tokens`}
        />
        <div className="quick-windows" role="group" aria-label="Preset context windows">
          {MODEL_WINDOWS.map((w) => (
            <button
              key={w.tokens}
              className={budget === w.tokens ? 'chip chip-on' : 'chip'}
              onClick={() => setBudget(w.tokens)}
              aria-pressed={budget === w.tokens}
            >
              {w.name}
            </button>
          ))}
        </div>
        <div
          className={fits ? 'verdict verdict-fit' : 'verdict verdict-over'}
          role="status"
          aria-live="polite"
        >
          <div className="verdict-meter" aria-hidden="true">
            <div
              className="verdict-meter-fill"
              style={{ width: `${fillPct}%`, background: fits ? 'var(--good)' : 'var(--bad)' }}
            />
          </div>
          {fits ? (
            <span>✓ Fits — {fmtTokens(headroom)} tokens of headroom ({Math.round(fillPct)}% used)</span>
          ) : (
            <span>✗ Over budget by {fmtTokens(-headroom)} tokens</span>
          )}
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, sub, tone }) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  );
}
