'use client';

import { useState, useEffect, useCallback } from 'react';
import { generateBlueprint } from '@/lib/generateBlueprint';
import { classifyFeature, addFeatureToBlueprint } from '@/lib/scopeLock';
import { formatBlueprint } from '@/lib/formatBlueprint';
import { loadState, saveState } from '@/lib/storage';
import type { Blueprint } from '@/lib/types';

const VAGUE_WORDS = ['platform', 'solution', 'system', 'optimize', 'improve', 'ai-powered', 'ai powered'];

function validateField(label: string, value: string): string | null {
  if (!value.trim()) return `"${label}" is required.`;
  if (value.trim().split(/\s+/).length < 2) return `"${label}" must be at least 2 words.`;
  for (const w of VAGUE_WORDS) {
    if (value.toLowerCase().includes(w)) return `"${label}" is too vague — avoid words like "${w}".`;
  }
  return null;
}

type ViewState = 'input' | 'output';

export default function Home() {
  const [view, setView] = useState<ViewState>('input');
  const [product, setProduct] = useState('');
  const [user, setUser] = useState('');
  const [action, setAction] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [blueprint, setBlueprint] = useState<Blueprint | null>(null);
  const [newFeature, setNewFeature] = useState('');
  const [featureMessage, setFeatureMessage] = useState<{ text: string; type: 'deferred' | 'essential' | 'blocked' } | null>(null);
  const [pendingFeature, setPendingFeature] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const state = loadState();
    if (state.blueprint) {
      setBlueprint(state.blueprint);
      setProduct(state.blueprint.parsedIdea.product);
      setUser(state.blueprint.parsedIdea.user);
      setAction(state.blueprint.parsedIdea.action);
      setView('output');
    }
  }, []);

  const persist = useCallback((bp: Blueprint) => {
    setBlueprint(bp);
    const state = loadState();
    saveState({
      blueprint: bp,
      history: [...state.history.filter((h) => h.id !== bp.id), bp],
    });
  }, []);

  function handleGenerate() {
    setError(null);
    const productErr = validateField('What are you building', product);
    const userErr = validateField('Who is it for', user);
    const actionErr = validateField('What will they do', action);
    if (productErr || userErr || actionErr) {
      setError(productErr ?? userErr ?? actionErr ?? '');
      return;
    }
    const parsedIdea = { product: product.trim(), user: user.trim(), action: action.trim() };
    const rawInput = `I am building a ${parsedIdea.product} that helps ${parsedIdea.user} do ${parsedIdea.action}`;
    const bp = generateBlueprint(parsedIdea, rawInput);
    persist(bp);
    setView('output');
  }

  function handleCopy() {
    if (!blueprint) return;
    const md = formatBlueprint(blueprint);
    navigator.clipboard.writeText(md).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function handleAddFeature() {
    if (!blueprint || !newFeature.trim()) return;

    const classification = classifyFeature(newFeature.trim());

    if (classification.classification === 'v2ParkingLot') {
      const updated = addFeatureToBlueprint(newFeature.trim(), blueprint);
      persist(updated);
      setFeatureMessage({ text: classification.reason, type: 'deferred' });
      setNewFeature('');
      setPendingFeature(null);
      return;
    }

    if (blueprint.mvpFeatures.length >= 5) {
      setPendingFeature(newFeature.trim());
      setFeatureMessage({ text: 'MVP is full (5/5). Choose a feature to replace.', type: 'blocked' });
      return;
    }

    const updated = addFeatureToBlueprint(newFeature.trim(), blueprint);
    persist(updated);
    setFeatureMessage({ text: 'Feature added to MVP.', type: 'essential' });
    setNewFeature('');
    setPendingFeature(null);
  }

  function handleReplace(index: number) {
    if (!blueprint || !pendingFeature) return;
    const updated = addFeatureToBlueprint(pendingFeature, blueprint, index);
    persist(updated);
    setFeatureMessage({ text: `Replaced feature #${index + 1}.`, type: 'essential' });
    setNewFeature('');
    setPendingFeature(null);
  }

  function handleStartOver() {
    setView('input');
    setProduct('');
    setUser('');
    setAction('');
    setBlueprint(null);
    setError(null);
    setFeatureMessage(null);
    setPendingFeature(null);
    setCopied(false);
    saveState({ blueprint: null, history: loadState().history });
  }

  return (
    <div className="app">
      <div className="header">
        <h1>Blueprint</h1>
        <p>Constraint-based execution blueprint generator</p>
      </div>

      {view === 'input' && (
        <div className="input-view">
          <div className="field-group">
            <label>What are you building?</label>
            <input
              type="text"
              value={product}
              onChange={(e) => { setProduct(e.target.value); setError(null); }}
              placeholder="daily goal tracker"
              onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate(); }}
            />
          </div>
          <div className="field-group">
            <label>Who is it for?</label>
            <input
              type="text"
              value={user}
              onChange={(e) => { setUser(e.target.value); setError(null); }}
              placeholder="high school students"
              onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate(); }}
            />
          </div>
          <div className="field-group">
            <label>What will they do with it?</label>
            <input
              type="text"
              value={action}
              onChange={(e) => { setAction(e.target.value); setError(null); }}
              placeholder="set and track daily goals"
              onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate(); }}
            />
          </div>
          {error && <div className="error-message">{error}</div>}
          <button
            className="primary generate-btn"
            onClick={handleGenerate}
            disabled={!product.trim() || !user.trim() || !action.trim()}
          >
            Generate Blueprint
          </button>
        </div>
      )}

      {view === 'output' && blueprint && (
        <div className="output-view">
          <div className="output-actions">
            <button className="primary" onClick={handleCopy}>
              Copy Blueprint
            </button>
            <button onClick={handleStartOver}>Start Over</button>
            {copied && <span className="copied-indicator">Copied</span>}
          </div>

          <div className="blueprint-section">
            <h3>1. Objective</h3>
            <p>{blueprint.sections.objective}</p>
          </div>

          <div className="blueprint-section">
            <h3>2. Target User</h3>
            <p>{blueprint.sections.targetUser}</p>
          </div>

          <div className="blueprint-section">
            <h3>3. Core Function</h3>
            <p>{blueprint.sections.coreFunction}</p>
          </div>

          <div className="blueprint-section">
            <h3>4. Constraints (V1 Only)</h3>
            <ul>
              {blueprint.sections.constraintsV1Only.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>

          <div className="blueprint-section">
            <h3>5. MVP Features ({blueprint.mvpFeatures.length}/5)</h3>
            <ol>
              {blueprint.mvpFeatures.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ol>
          </div>

          <div className="blueprint-section">
            <h3>6. Build Steps</h3>
            <ol>
              {blueprint.sections.buildSteps.map((s, i) => (
                <li key={i}>{s.replace(/^\d+\.\s*/, '')}</li>
              ))}
            </ol>
          </div>

          <div className="blueprint-section">
            <h3>7. Dependencies</h3>
            <ul>
              {blueprint.sections.dependencies.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </div>

          <div className="blueprint-section">
            <h3>8. Definition of Done</h3>
            <ul>
              {blueprint.sections.definitionOfDone.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          </div>

          {blueprint.v2ParkingLot.length > 0 && (
            <div className="parking-lot">
              <h3>V2 Parking Lot</h3>
              <ul>
                {blueprint.v2ParkingLot.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="add-feature">
            <h3>Add Feature</h3>
            <div className="add-feature-form">
              <input
                type="text"
                value={newFeature}
                onChange={(e) => {
                  setNewFeature(e.target.value);
                  setFeatureMessage(null);
                  setPendingFeature(null);
                }}
                placeholder="Describe a feature..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAddFeature();
                }}
              />
              <button onClick={handleAddFeature} disabled={!newFeature.trim()}>
                Add
              </button>
            </div>

            {featureMessage && (
              <div className={`feature-message ${featureMessage.type}`}>
                {featureMessage.text}
              </div>
            )}

            {pendingFeature && (
              <div className="replace-prompt">
                <p>Select a feature to replace:</p>
                <div className="replace-options">
                  {blueprint.mvpFeatures.map((f, i) => (
                    <div key={i} className="replace-option">
                      <span>{i + 1}. {f}</span>
                      <button onClick={() => handleReplace(i)}>Replace</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
