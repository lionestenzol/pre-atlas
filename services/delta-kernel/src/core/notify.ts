/**
 * Phone push notifications via ntfy.sh.
 *
 * Reuses the exact topic/body shape already proven live in
 * services/uasc-executor/profiles/SEND_DRAFT_v1.json, but calls it
 * directly — no approval gate, no UASC round-trip — for informational
 * pushes triggered by real state changes (mode transitions, task completions).
 */

const NTFY_TOPIC = 'atlas-bruke';

export async function notifyPhone(title: string, message: string): Promise<void> {
  await fetch('https://ntfy.sh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic: NTFY_TOPIC,
      title: `Atlas: ${title}`,
      message,
      tags: ['robot', 'atlas'],
    }),
  });
}
