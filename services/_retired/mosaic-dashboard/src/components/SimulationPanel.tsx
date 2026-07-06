'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Panel from './Panel';
import { startSimulation, getSimulation, getSimulationReport, listSimulations } from '@/lib/api';
import type { SimulationSummary, SimulationTick } from '@/lib/types';
import * as d3 from 'd3';

const POLL_MS = 2000;

export default function SimulationPanel() {
  const [sims, setSims] = useState<SimulationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [topic, setTopic] = useState('');
  const [docText, setDocText] = useState('');
  const [agentCount, setAgentCount] = useState(5);
  const [tickCount, setTickCount] = useState(10);

  // Active simulation
  const [activeId, setActiveId] = useState<string | null>(null);
  const [ticks, setTicks] = useState<SimulationTick[]>([]);
  const [simStatus, setSimStatus] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const loadList = useCallback(async () => {
    try {
      const { simulations } = await listSimulations();
      setSims(simulations);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'MiroFish unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  // Polling
  useEffect(() => {
    if (!activeId || simStatus === 'completed' || simStatus === 'failed') return;

    const poll = async () => {
      try {
        const sim = await getSimulation(activeId, ticks.length);
        if (sim.ticks.length > 0) {
          setTicks(prev => [...prev, ...sim.ticks]);
        }
        setSimStatus(sim.status);
        if (sim.status === 'completed') {
          try {
            const r = await getSimulationReport(activeId);
            setReport(r.summary);
          } catch { /* report may not be ready yet */ }
        }
      } catch { /* ignore poll errors */ }
    };

    pollRef.current = setInterval(poll, POLL_MS);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [activeId, simStatus, ticks.length]);

  // D3 chart
  useEffect(() => {
    if (!svgRef.current || ticks.length === 0) return;
    const svg = d3.select(svgRef.current);
    const w = 400, h = 200, m = { top: 10, right: 10, bottom: 30, left: 40 };
    const iw = w - m.left - m.right, ih = h - m.top - m.bottom;

    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${w} ${h}`);

    const x = d3.scaleLinear().domain([0, Math.max(1, ticks.length - 1)]).range([0, iw]);
    const y = d3.scaleLinear().domain([0, 1]).range([ih, 0]);

    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    g.append('g').attr('transform', `translate(0,${ih})`).call(d3.axisBottom(x).ticks(5))
      .selectAll('text').attr('fill', '#71717a');
    g.append('g').call(d3.axisLeft(y).ticks(5))
      .selectAll('text').attr('fill', '#71717a');
    g.selectAll('.domain, .tick line').attr('stroke', '#3f3f46');

    const line = d3.line<SimulationTick>()
      .x((_, i) => x(i))
      .y(d => y(d.consensus));

    g.append('path')
      .datum(ticks)
      .attr('fill', 'none')
      .attr('stroke', '#22c55e')
      .attr('stroke-width', 2)
      .attr('d', line);
  }, [ticks]);

  const handleStart = async () => {
    if (!topic.trim()) return;
    setSubmitting(true);
    setTicks([]);
    setReport(null);
    setSimStatus(null);
    try {
      const sim = await startSimulation({
        topic: topic.trim(),
        document_text: docText.trim() || undefined,
        agent_count: agentCount,
        tick_count: tickCount,
      });
      setActiveId(sim.simulation_id);
      setSimStatus(sim.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start simulation');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel title="Swarm Simulation" loading={loading} error={error} onRetry={loadList} className="xl:col-span-2">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Form */}
        <div className="space-y-3">
          <input
            type="text"
            placeholder="Simulation topic..."
            value={topic}
            onChange={e => setTopic(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
          />
          <textarea
            placeholder="Optional document text..."
            value={docText}
            onChange={e => setDocText(e.target.value)}
            rows={3}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500 resize-none"
          />
          <div className="flex gap-3">
            <label className="text-xs text-zinc-500">
              Agents
              <input
                type="number"
                value={agentCount}
                onChange={e => setAgentCount(Number(e.target.value))}
                min={2}
                max={50}
                className="ml-2 w-16 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100"
              />
            </label>
            <label className="text-xs text-zinc-500">
              Ticks
              <input
                type="number"
                value={tickCount}
                onChange={e => setTickCount(Number(e.target.value))}
                min={1}
                max={100}
                className="ml-2 w-16 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-100"
              />
            </label>
          </div>
          <button
            onClick={handleStart}
            disabled={!topic.trim() || submitting}
            className="text-sm px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium disabled:opacity-50 transition-colors"
          >
            {submitting ? 'Starting...' : 'Run Simulation'}
          </button>

          {sims.length > 0 && (
            <div className="text-xs text-zinc-500 mt-2">
              {sims.length} previous simulation{sims.length !== 1 ? 's' : ''}
            </div>
          )}
        </div>

        {/* Right: Chart + Report */}
        <div className="space-y-3">
          {simStatus && (
            <div className="text-xs text-zinc-400">
              Status: <span className="font-mono text-zinc-200">{simStatus}</span>
              {ticks.length > 0 && ` · ${ticks.length} ticks`}
            </div>
          )}

          <svg ref={svgRef} className="w-full h-auto bg-zinc-800/50 rounded-lg" />

          {report && (
            <div className="bg-zinc-800/50 rounded-lg p-3">
              <div className="text-xs text-zinc-500 mb-1">Report</div>
              <p className="text-sm text-zinc-300">{report}</p>
            </div>
          )}

          {!simStatus && !report && (
            <div className="flex items-center justify-center h-32 text-sm text-zinc-600">
              Start a simulation to see results
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
