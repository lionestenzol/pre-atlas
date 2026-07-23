// inPACT AI Context Module
// Assembles a snapshot of inPACT's state + live governance so an AI can SEE
// your operating picture. Ported from CycleBoard's AIContext, kept safe: no LLM
// key lives here. You export context (clipboard) and paste it into Claude, or an
// agent reads it. Mutations go through AIActions; backend proposals via signals.js.

const AIContext = {
  /**
   * Pull live governance from delta-kernel (unified.derived). Best-effort.
   * @returns {Promise<object|null>} { mode, risk, openLoops, closurePct, streakDays, primaryOrder, buildAllowed } or null when offline.
   */
  async _governance() {
    try {
      if (typeof AtlasAPI === 'undefined' || !AtlasAPI.online) return null;
      const u = await AtlasAPI.getUnifiedState();
      const d = u && (u.derived || (u.data && u.data.derived));
      if (!d) return null;
      const raw = d.closure_ratio;
      return {
        mode: d.mode || null,
        risk: d.risk || d.risk_level || null,
        openLoops: d.open_loops != null ? d.open_loops : null,
        closurePct: raw == null ? null : Math.round(raw <= 1 ? raw * 100 : raw),
        streakDays: d.streak_days != null ? d.streak_days : null,
        primaryOrder: d.primary_order || null,
        buildAllowed: d.build_allowed
      };
    } catch (e) {
      return null;
    }
  },

  /** Today's ritual fields + day plan, normalized. */
  _today() {
    const today = stateManager.getTodayDate();
    const ritual = (state.Today && state.Today.daily && state.Today.daily[today]) || {};
    const plan = (typeof Helpers !== 'undefined' && Helpers.getDayPlan) ? Helpers.getDayPlan() : {};
    return {
      date: today,
      dayType: ritual.day_type || plan.day_type || 'A',
      winTarget: ritual.winTarget || '',
      lever: ritual.lever || '',
      priorities: [1, 2, 3]
        .map(n => ritual['p' + n])
        .filter(Boolean),
      timeBlocks: (plan.time_blocks || []).map(b => ({ time: b.time, title: b.title, completed: !!b.completed }))
    };
  },

  /** A-Z task rollup. */
  _tasks() {
    const az = state.AZTask || [];
    const by = s => az.filter(t => t.status === s);
    return {
      all: az.map(t => ({ letter: t.letter, task: t.task, status: t.status, notes: t.notes || '' })),
      total: az.length,
      notStarted: by('Not Started').length,
      inProgress: by('In Progress').length,
      completed: by('Completed').length
    };
  },

  /** Weekly focus: primary letter + counts-if + PIGPEN notes. */
  _week() {
    const wp = state.WeeklyPlan || {};
    let primaryLetter = '';
    if (wp.primaryLetter) {
      const t = (state.AZTask || []).find(x => x.id === wp.primaryLetter || x.letter === wp.primaryLetter);
      primaryLetter = t ? t.letter : '';
    }
    return {
      weekOf: wp.weekOf || '',
      primaryLetter,
      weekCountsIf: wp.weekCountsIf || '',
      pigpen: wp.pigpenFocus || {},
      closed: !!wp.closed
    };
  },

  /**
   * Full context snapshot for AI consumption.
   * @returns {Promise<object>}
   */
  async getContext() {
    const weekly = (typeof Helpers !== 'undefined' && Helpers.getWeeklyStats) ? Helpers.getWeeklyStats() : { completed: 0, total: 0, percentage: 0 };
    return {
      _meta: { generatedAt: new Date().toISOString(), version: state.version || '2.0', source: 'inPACT AI Context' },
      identity: { mission: (state.Today && state.Today.mission) || '', motto: (state.Today && state.Today.motto) || '' },
      governance: await this._governance(),
      today: this._today(),
      tasks: this._tasks(),
      week: this._week(),
      weeklyStats: weekly,
      focusAreas: (state.FocusArea || []).map(a => a.name),
      routines: Object.keys(state.Routine || {})
    };
  },

  /**
   * Human-readable markdown snapshot, optimized for pasting into a chat with Claude.
   * @returns {Promise<string>}
   */
  async getClipboardSnapshot() {
    const c = await this.getContext();
    const g = c.governance;
    const t = c.today;
    let md = `# inPACT Context Snapshot\n*Generated ${new Date().toLocaleString()}*\n\n`;

    if (c.identity.mission || c.identity.motto) {
      md += `## Why\n`;
      if (c.identity.mission) md += `- Mission: ${c.identity.mission}\n`;
      if (c.identity.motto) md += `- Motto: ${c.identity.motto}\n`;
      md += `\n`;
    }

    md += `## Governance (live from Atlas)\n`;
    if (g) {
      md += `- Mode: ${g.mode || '?'} . Risk: ${g.risk || '?'} . Open loops: ${g.openLoops != null ? g.openLoops : '?'} . Closure: ${g.closurePct != null ? g.closurePct + '%' : '?'} . Streak: ${g.streakDays != null ? g.streakDays + 'd' : '?'}\n`;
      if (g.primaryOrder) md += `- Atlas directive: ${g.primaryOrder}\n`;
      md += `- Build allowed: ${g.buildAllowed === false ? 'no (close loops first)' : 'yes'}\n`;
    } else {
      md += `- Offline (Atlas not connected)\n`;
    }

    md += `\n## Today (${t.date}, ${t.dayType}-day)\n`;
    md += `- Win target: ${t.winTarget || '(not set)'}\n`;
    if (t.lever) md += `- Lever: ${t.lever}\n`;
    if (t.priorities.length) md += `- Priorities: ${t.priorities.map((p, i) => `${i + 1}. ${p}`).join('  ')}\n`;
    if (t.timeBlocks.length) {
      md += `- Time blocks:\n`;
      t.timeBlocks.forEach(b => { md += `  - ${b.completed ? '[x]' : '[ ]'} ${b.time} ${b.title}\n`; });
    }

    md += `\n## A-Z Tasks (${c.tasks.completed}/${c.tasks.total} done)\n`;
    c.tasks.all.forEach(x => {
      const mark = x.status === 'Completed' ? '[x]' : (x.status === 'In Progress' ? '[~]' : '[ ]');
      md += `- ${mark} ${x.letter}: ${x.task}${x.notes ? ` (${x.notes})` : ''}\n`;
    });

    md += `\n## This Week\n`;
    if (c.week.primaryLetter) md += `- Primary letter: ${c.week.primaryLetter}\n`;
    if (c.week.weekCountsIf) md += `- Week counts if: ${c.week.weekCountsIf}\n`;
    const pig = Object.entries(c.week.pigpen).filter(([, v]) => v);
    if (pig.length) {
      md += `- PIGPEN focus:\n`;
      pig.forEach(([k, v]) => { md += `  - ${k}: ${v}\n`; });
    }
    md += `- Days met baseline this week: ${c.weeklyStats.completed}/${c.weeklyStats.total}\n`;

    md += `\n---\n*Paste this into Claude to get help grounded in your real state.*\n`;
    return md;
  },

  /**
   * System-prompt flavored export (tells the AI what inPACT is + what it can do).
   * @returns {Promise<string>}
   */
  async getSystemPrompt() {
    const snap = await this.getClipboardSnapshot();
    return `You are an assistant integrated with inPACT, a daily planning system built on the "8 Steps" methodology.\n` +
      `Day types: A (full energy), B (low energy, essentials), C (survival, one priority).\n` +
      `In CLOSURE mode, prioritize closing open loops over starting new work.\n` +
      `Keep suggestions to 1-3 at a time; respect the current day type and governance mode.\n\n` +
      snap;
  },

  /**
   * Copy a snapshot to the clipboard.
   * @param {'markdown'|'prompt'|'json'} format
   * @returns {Promise<boolean>}
   */
  async copyToClipboard(format = 'markdown') {
    let content;
    try {
      if (format === 'json') content = JSON.stringify(await this.getContext(), null, 2);
      else if (format === 'prompt') content = await this.getSystemPrompt();
      else content = await this.getClipboardSnapshot();
      await navigator.clipboard.writeText(content);
      if (typeof UI !== 'undefined') UI.showToast('Copied', 'State snapshot copied. Paste it into Claude.', 'success');
      return true;
    } catch (e) {
      if (typeof UI !== 'undefined') UI.showToast('Copy failed', 'Could not access clipboard', 'error');
      return false;
    }
  }
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIContext;
}
