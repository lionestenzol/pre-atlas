// Robust copy-to-clipboard: prefer the async Clipboard API, fall back to a
// hidden-textarea + execCommand('copy') for browsers/contexts where the async
// API is unavailable or permission-denied (older Safari, non-focused windows,
// some embedded webviews). Returns true on success.
export async function copyText(text) {
  // Path 1: the modern async Clipboard API (needs a secure context + permission).
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to the legacy path
    }
  }
  // Path 2: legacy execCommand fallback. Works without the Clipboard permission
  // as long as the document has focus and the copy runs in a user gesture.
  // See ~/.claude/rules/common/code-as-furniture.md — fallback, not a TODO.
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
