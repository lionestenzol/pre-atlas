"""
Injects cognitive directive banner into CycleBoard HTML.
"""

from pathlib import Path

# Base directory is the same folder as this script
BASE = Path(__file__).parent.resolve()

# Source and output are repo-local
SOURCE = BASE / "cycleboard_app3.html"
OUTPUT = BASE / "cycleboard" / "cycleboard_cognitive.html"

# Read the original file
html = SOURCE.read_text(encoding="utf-8")

# The directive banner HTML
directive_banner = '''
  <!-- COGNITIVE DIRECTIVE BANNER -->
  <div id="cognitive-directive" class="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg" style="position: sticky; top: 0; z-index: 50;">
    <div class="max-w-7xl mx-auto p-4">
      <div class="flex items-center justify-between">
        <div class="flex-1">
          <div class="text-xs uppercase tracking-wider opacity-75 mb-1">Cognitive Routing System</div>
          <div class="flex items-center gap-4">
            <div>
              <div class="text-xs opacity-75">MODE</div>
              <div id="directive-mode" class="text-xl font-bold">Loading...</div>
            </div>
            <div class="flex-1">
              <div class="text-xs opacity-75">ACTION</div>
              <div id="directive-action" class="text-sm">Analyzing cognitive state...</div>
            </div>
          </div>
        </div>
        <button onclick="document.getElementById('cognitive-directive').style.display='none'" class="p-2 hover:bg-white/20 rounded-lg transition">
          <i class="fas fa-times"></i>
        </button>
      </div>
    </div>
  </div>
'''

# Directive loader script
directive_script = '''
  <script>
    // Load cognitive directive on page load
    (function loadCognitiveDirective() {
      fetch('brain/daily_directive.txt')
        .then(r => r.text())
        .then(text => {
          const modeMatch = text.match(/MODE: (\\w+)/);
          const actionMatch = text.match(/ACTION: (.+?)(?=\\n|$)/);

          const modeEl = document.getElementById('directive-mode');
          const actionEl = document.getElementById('directive-action');

          if (modeMatch && modeEl) {
            modeEl.textContent = modeMatch[1];
            // Color code by mode
            const banner = document.getElementById('cognitive-directive');
            if (modeMatch[1] === 'CLOSURE') {
              banner.className = banner.className.replace('from-purple-600 to-indigo-600', 'from-red-600 to-orange-600');
            } else if (modeMatch[1] === 'BUILD') {
              banner.className = banner.className.replace('from-purple-600 to-indigo-600', 'from-green-600 to-emerald-600');
            } else if (modeMatch[1] === 'MAINTENANCE') {
              banner.className = banner.className.replace('from-purple-600 to-indigo-600', 'from-yellow-600 to-amber-600');
            }
          }
          if (actionMatch && actionEl) {
            actionEl.textContent = actionMatch[1];
          }
        })
        .catch(() => {
          const modeEl = document.getElementById('directive-mode');
          const actionEl = document.getElementById('directive-action');
          if (modeEl) modeEl.textContent = 'OFFLINE';
          if (actionEl) actionEl.textContent = 'Run: python refresh.py to activate cognitive system';
        });
    })();
  </script>
'''

# Insert banner right after opening <body> tag
body_insert_point = html.find('<body class="bg-slate-50">')
if body_insert_point != -1:
    # Find the end of the body tag
    body_end = html.find('>', body_insert_point) + 1
    # Insert the directive banner
    html = html[:body_end] + directive_banner + html[body_end:]
    print("[OK] Inserted directive banner")
else:
    print("[FAIL] Could not find <body> tag")
    exit(1)

# Insert script before closing </body> tag
body_close = html.rfind('</body>')
if body_close != -1:
    html = html[:body_close] + directive_script + html[body_close:]
    print("[OK] Inserted directive loader script")
else:
    print("[FAIL] Could not find </body> tag")
    exit(1)

# Write output
OUTPUT.parent.mkdir(exist_ok=True)
OUTPUT.write_text(html, encoding="utf-8")
print(f"[OK] Created cognitive-aware CycleBoard at:")
print(f"     {OUTPUT}")
print("\nOpen this file in your browser to see your cognitive directive banner.")
