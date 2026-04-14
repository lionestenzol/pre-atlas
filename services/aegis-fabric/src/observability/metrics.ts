/**
 * Aegis Enterprise Fabric — Prometheus-Compatible Metrics
 *
 * In-memory counters, gauges, and histograms.
 * Exposed at /metrics in Prometheus text format.
 */

interface CounterEntry {
  labels: Record<string, string>;
  value: number;
}

interface GaugeEntry {
  value: number;
}

interface HistogramEntry {
  labels: Record<string, string>;
  sum: number;
  count: number;
  buckets: Map<number, number>;
}

const DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];

class MetricsRegistry {
  private counters: Map<string, CounterEntry[]> = new Map();
  private gauges: Map<string, GaugeEntry> = new Map();
  private histograms: Map<string, HistogramEntry[]> = new Map();

  // === COUNTERS ===

  increment(name: string, labels: Record<string, string> = {}, value: number = 1): void {
    if (!this.counters.has(name)) {
      this.counters.set(name, []);
    }
    const entries = this.counters.get(name)!;
    const key = JSON.stringify(labels);
    const existing = entries.find(e => JSON.stringify(e.labels) === key);
    if (existing) {
      existing.value += value;
    } else {
      entries.push({ labels, value });
    }
  }

  // === GAUGES ===

  setGauge(name: string, value: number): void {
    this.gauges.set(name, { value });
  }

  incrementGauge(name: string, delta: number = 1): void {
    const current = this.gauges.get(name)?.value || 0;
    this.gauges.set(name, { value: current + delta });
  }

  // === HISTOGRAMS ===

  observe(name: string, labels: Record<string, string>, value: number): void {
    if (!this.histograms.has(name)) {
      this.histograms.set(name, []);
    }
    const entries = this.histograms.get(name)!;
    const key = JSON.stringify(labels);
    let existing = entries.find(e => JSON.stringify(e.labels) === key);
    if (!existing) {
      existing = { labels, sum: 0, count: 0, buckets: new Map(DEFAULT_BUCKETS.map(b => [b, 0])) };
      entries.push(existing);
    }
    existing.sum += value;
    existing.count += 1;
    for (const bucket of DEFAULT_BUCKETS) {
      if (value <= bucket) {
        existing.buckets.set(bucket, (existing.buckets.get(bucket) || 0) + 1);
      }
    }
  }

  // === EXPORT ===

  toPrometheusText(): string {
    const lines: string[] = [];

    // Counters
    for (const [name, entries] of this.counters) {
      lines.push(`# TYPE ${name} counter`);
      for (const entry of entries) {
        const labelStr = this.formatLabels(entry.labels);
        lines.push(`${name}${labelStr} ${entry.value}`);
      }
    }

    // Gauges
    for (const [name, entry] of this.gauges) {
      lines.push(`# TYPE ${name} gauge`);
      lines.push(`${name} ${entry.value}`);
    }

    // Histograms
    for (const [name, entries] of this.histograms) {
      lines.push(`# TYPE ${name} histogram`);
      for (const entry of entries) {
        const labelStr = this.formatLabels(entry.labels);
        for (const [bucket, count] of entry.buckets) {
          const bucketLabels = this.formatLabels({ ...entry.labels, le: String(bucket) });
          lines.push(`${name}_bucket${bucketLabels} ${count}`);
        }
        const infLabels = this.formatLabels({ ...entry.labels, le: '+Inf' });
        lines.push(`${name}_bucket${infLabels} ${entry.count}`);
        lines.push(`${name}_sum${labelStr} ${entry.sum}`);
        lines.push(`${name}_count${labelStr} ${entry.count}`);
      }
    }

    return lines.join('\n') + '\n';
  }

  private formatLabels(labels: Record<string, string>): string {
    const entries = Object.entries(labels);
    if (entries.length === 0) return '';
    const parts = entries.map(([k, v]) => `${k}="${v}"`);
    return `{${parts.join(',')}}`;
  }
}

// Singleton
export const metrics = new MetricsRegistry();
