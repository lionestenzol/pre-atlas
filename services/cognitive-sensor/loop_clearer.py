#!/usr/bin/env python3
"""
loop_clearer.py -- ugly, steerable UI to clear open loops one at a time.

Borrows the DropList "one runs at a time" interaction + dark terminal
aesthetic, tuned SPECIFICALLY for draining the cognitive-sensor open-loop
backlog (the same loops that pin Atlas in CLOSURE mode).

It does NOT reimplement closing. It wraps the real, proven close path:
  close_loop.get_open_loops()      -- source of truth (loops_latest.json - DB decisions)
  close_loop.record_decision()     -- writes loop_decisions (SQLite) + notifies delta-kernel
  close_loop.refresh_pipeline()    -- recomputes cognitive_state.json + Atlas mode
See ~/.claude/rules/common/assemble-first.md and code-as-furniture.md.

Run:  python loop_clearer.py    ->  http://127.0.0.1:3077
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import close_loop as cl

PORT = 3077
HOST = "127.0.0.1"

# Refresh runs the heavy 5-script pipeline; keep its state so the UI can poll.
_refresh = {"running": False, "done": False, "error": None}


def topics_for(convo_id):
    """Top topic tags for a loop -- cheap memory-jog. Best-effort."""
    try:
        con = cl.get_db()
        rows = con.execute(
            "SELECT topic FROM topics WHERE convo_id=? ORDER BY weight DESC LIMIT 5",
            (convo_id,),
        ).fetchall()
        con.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def open_loops_payload():
    loops = cl.get_open_loops()
    enriched = []
    for l in loops:
        enriched.append({
            "convo_id": l["convo_id"],
            "title": l.get("title", "(untitled)"),
            "score": l.get("score", 0),
            "topics": topics_for(l["convo_id"]),
        })
    # Highest score first = stickiest loops first.
    enriched.sort(key=lambda x: x["score"], reverse=True)
    return {"count": len(enriched), "loops": enriched}


def atlas_open_count():
    """What Atlas actually sees (cognitive_state.json). Updates only after refresh."""
    try:
        p = cl.BASE / "cognitive_state.json"
        if p.exists():
            st = json.loads(p.read_text(encoding="utf-8"))
            return st.get("closure", {}).get("open")
    except Exception:
        pass
    return None


def context_for(convo_id):
    """Per-loop decision context: classification, recommendation, and the
    actual first/last things you said. Reuses close_loop's own functions
    (compute_recommendation + get_conversation_text). Best-effort."""
    cls = {}
    try:
        cls = cl.load_classifications().get(str(convo_id), {}) or {}
    except Exception:
        pass
    domain = cls.get("domain", "unknown")
    outcome = cls.get("outcome", "unknown")
    traj = cls.get("emotional_trajectory", "unknown")
    intensity = cls.get("intensity", "unknown")

    topics = []
    try:
        topics = cl.get_topics(convo_id)
    except Exception:
        pass
    try:
        rec, reason = cl.compute_recommendation(outcome, traj, intensity, 0, topics)
    except Exception:
        rec, reason = "ARCHIVE", "No signal."

    started, ended = [], []
    try:
        first_msgs, last_msgs = cl.get_conversation_text(convo_id)
        started = [cl.truncate(m.get("text", ""), 240) for m in (first_msgs or [])]
        ended = [cl.truncate(m.get("text", ""), 240) for m in (last_msgs or [])]
    except Exception:
        pass

    return {
        "domain": domain, "outcome": outcome,
        "trajectory": traj, "intensity": intensity,
        "recommendation": rec, "reason": reason,
        "started": [s for s in started if s], "ended": [e for e in ended if e],
    }


def run_refresh():
    _refresh.update(running=True, done=False, error=None)
    try:
        cl.refresh_pipeline()
        _refresh.update(running=False, done=True)
    except Exception as e:  # noqa: BLE001 - surface to UI
        _refresh.update(running=False, done=True, error=str(e))


PAGE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LOOP CLEARER</title>
<style>
:root{
  --bg:#0c0e0d; --panel:#161b19; --panel2:#1c2220; --line:#2a322f; --line2:#39433f;
  --text:#e9e7e0; --muted:#8b918c; --faint:#7a807c;
  --signal:#ffaa33; --done:#5fd97a; --kill:#ff5d5d; --skip:#8a8f8c; --carry:#69b4ff;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--text);font-family:ui-monospace,'IBM Plex Mono',Consolas,monospace;
  font-size:15px;line-height:1.5;
  background-image:linear-gradient(rgba(255,255,255,.012) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.012) 1px,transparent 1px);
  background-size:34px 34px,34px 34px;}
#app{max-width:620px;margin:0 auto;padding:18px 16px 60px}
header{display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:16px}
.brand{font-weight:700;letter-spacing:.16em;font-size:16px}
.brand b{color:var(--signal)}
.muted{color:var(--muted)} .faint{color:var(--faint)}
.bar{height:8px;border:1px solid var(--line2);border-radius:6px;background:var(--panel);overflow:hidden;margin:4px 0 2px}
.bar i{display:block;height:100%;background:var(--done);width:0;transition:width .35s}
.counts{display:flex;gap:16px;font-size:12px;letter-spacing:.04em;margin-bottom:18px}
.counts b{font-size:20px;font-weight:700}
.counts .c-rem b{color:var(--signal)} .counts .c-done b{color:var(--done)} .counts .c-atlas b{color:var(--carry)}

.card{border:1px solid var(--line2);border-radius:16px;background:linear-gradient(180deg,var(--panel2),var(--panel));
  padding:22px 20px;box-shadow:0 18px 50px -18px rgba(0,0,0,.85);position:relative;overflow:hidden}
.card::before{content:"";position:absolute;inset:0;border-radius:16px;padding:1px;
  background:linear-gradient(140deg,rgba(255,170,51,.35),transparent 42%);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);
  -webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.pos{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint);margin-bottom:10px}
.title{font-size:26px;font-weight:700;line-height:1.18;letter-spacing:.01em;margin-bottom:10px;word-break:break-word}
.meta{font-size:12px;color:var(--muted);margin-bottom:12px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.tag{font-size:10.5px;letter-spacing:.06em;padding:4px 9px;border:1px solid var(--line2);border-radius:20px;color:var(--muted)}
.tag.none{border-style:dashed;color:var(--faint)}

.acts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px}
.btn{font-family:inherit;font-weight:700;letter-spacing:.08em;font-size:15px;border:1px solid var(--line2);
  background:var(--panel2);color:var(--text);padding:16px 12px;border-radius:13px;cursor:pointer;text-transform:uppercase;
  transition:transform .07s,background .15s,border-color .15s}
.btn:active{transform:scale(.97)}
.btn.close{grid-column:1/-1;background:var(--done);border-color:var(--done);color:#08110a;font-size:17px;letter-spacing:.12em}
.btn.archive{color:var(--signal);border-color:#5a4423}
.btn.archive:active{background:rgba(255,170,51,.12)}
.btn.skip{color:var(--skip)}
.kbd{font-size:10.5px;color:var(--faint);margin-top:12px;text-align:center;letter-spacing:.05em}
.kbd b{color:var(--muted)}
.btn.reco{outline:2px solid var(--signal);outline-offset:2px}

.ctx{margin-top:16px;border-top:1px dashed var(--line);padding-top:13px}
.ctx.loading-ctx{color:var(--faint);font-style:italic;font-size:12.5px}
.rec{font-size:13.5px;line-height:1.5}
.rec b{letter-spacing:.06em}
.rec.rec-close b{color:var(--done)} .rec.rec-arch b{color:var(--signal)}
.rec span{color:var(--muted)}
.cls-meta{font-size:11px;color:var(--faint);margin-top:7px;letter-spacing:.04em}
.exwrap{margin-top:11px}
.exwrap summary{cursor:pointer;color:var(--carry);font-size:12px;letter-spacing:.04em;list-style:none}
.exwrap summary::-webkit-details-marker{display:none}
.exwrap summary::before{content:"▸ ";color:var(--carry)}
.exwrap[open] summary::before{content:"▾ "}
.ex-h{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint);margin:11px 0 4px}
.ex{font-size:12.5px;color:#cfccc4;background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:8px 10px;margin-bottom:6px;white-space:pre-wrap;word-break:break-word}

.queue{margin-top:24px}
.seg{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:var(--faint);margin:0 0 8px;display:flex;align-items:center;gap:10px}
.seg::after{content:"";flex:1;height:1px;background:var(--line)}
.qrow{display:flex;align-items:center;gap:10px;border:1px solid var(--line);background:var(--panel);border-radius:11px;padding:10px 12px;margin-bottom:7px}
.qrow .qn{font-weight:700;color:var(--faint);width:26px;flex:0 0 auto}
.qrow .qt{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13.5px}
.qrow .qs{font-size:10.5px;color:var(--faint);flex:0 0 auto}

.empty{text-align:center;padding:54px 16px}
.empty .big{font-size:30px;font-weight:700;margin-bottom:8px}
.empty .sub{color:var(--muted)}
.refresh{margin-top:22px;width:100%;font-family:inherit;font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:13px;
  border:1px solid var(--carry);background:rgba(105,180,255,.08);color:var(--carry);padding:14px;border-radius:12px;cursor:pointer}
.refresh:disabled{opacity:.55;cursor:default}
.note{font-size:11.5px;color:var(--faint);text-align:center;margin-top:10px;line-height:1.5}
.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--panel2);border:1px solid var(--line2);
  border-radius:12px;padding:11px 16px;font-size:13px;box-shadow:0 18px 50px -18px #000;opacity:0;transition:opacity .2s;pointer-events:none}
.toast.show{opacity:1}
.toast.done{border-color:var(--done)} .toast.archive{border-color:var(--signal)} .toast.err{border-color:var(--kill);color:var(--kill)}
.loading{text-align:center;padding:60px;color:var(--faint);letter-spacing:.2em}
</style></head>
<body>
<div id="app"><div class="loading">LOADING&hellip;</div></div>
<div id="toast" class="toast"></div>
<script>
let LOOPS=[], DONE=0, ATLAS=null, BUSY=false, CTX={};

async function api(path, opts){ const r=await fetch(path,opts); return r.json(); }

async function ensureCtx(id){
  if(CTX[id]) return;                 // cached or in-flight
  CTX[id]='loading';
  try{ CTX[id]=await api('/api/context?id='+encodeURIComponent(id)); }
  catch(e){ CTX[id]={error:true}; }
  render();
}

async function load(){
  const d=await api('/api/loops'); LOOPS=d.loops; ATLAS=d.atlas_open;
  render();
}

function toast(msg,cls){ const t=document.getElementById('toast'); t.className='toast show '+(cls||''); t.textContent=msg;
  clearTimeout(window._tt); window._tt=setTimeout(()=>{t.className='toast';},1600); }

async function decide(decision){
  if(BUSY||!LOOPS.length) return; BUSY=true;
  const cur=LOOPS[0];
  try{
    const r=await api('/api/decide',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({convo_id:cur.convo_id,decision})});
    if(r.ok){ DONE++; LOOPS=r.loops; ATLAS=r.atlas_open;
      toast((decision==='CLOSE'?'✓ Closed: ':'↳ Archived: ')+cur.title, decision==='CLOSE'?'done':'archive'); }
    else toast(r.error||'failed','err');
  }catch(e){ toast('network error','err'); }
  BUSY=false; render();
}
function skip(){ if(!LOOPS.length) return; LOOPS.push(LOOPS.shift()); render(); toast('→ skipped (back of line)'); }

async function refresh(){
  const btn=document.getElementById('refbtn'); if(btn){btn.disabled=true;btn.textContent='RECOMPUTING… (up to ~1 min)';}
  await api('/api/refresh',{method:'POST'});
  poll();
}
async function poll(){
  const s=await api('/api/refresh/status');
  const btn=document.getElementById('refbtn');
  if(s.running){ if(btn){btn.disabled=true;btn.textContent='RECOMPUTING…';} setTimeout(poll,1500); return; }
  if(s.error) toast('refresh error: '+s.error,'err');
  else if(s.done) toast('Atlas mode recomputed','carry');
  await load();
}

function render(){
  const app=document.getElementById('app');
  const total=DONE+LOOPS.length;
  const pct= total? Math.round(DONE/total*100):0;
  const head=`<header>
      <div class="brand">LOOP<b>CLEARER</b></div>
      <div class="faint" style="font-size:11px;letter-spacing:.1em">borrowed from DropList · tuned for closure</div>
    </header>
    <div class="bar"><i style="width:${pct}%"></i></div>
    <div class="counts">
      <span class="c-rem">remaining <b>${LOOPS.length}</b></span>
      <span class="c-done">cleared <b>${DONE}</b></span>
      <span class="c-atlas">atlas sees <b>${ATLAS==null?'?':ATLAS}</b></span>
    </div>`;

  if(!LOOPS.length){
    app.innerHTML=head+`<div class="empty">
        <div class="big">${DONE? 'Queue drained.':'Nothing open.'}</div>
        <div class="sub">${DONE? DONE+' loop'+(DONE>1?'s':'')+' decided this session.':"You're already clean."}</div>
        <button class="refresh" id="refbtn" onclick="refresh()">Recompute Atlas mode → leave CLOSURE</button>
        <div class="note">Closing a loop is saved instantly. Atlas only re-routes out of CLOSURE after this recompute<br>(reruns loops → stats → state → mode). Drop open loops to ≤3 to clear the global override.</div>
      </div>`;
    return;
  }

  const cur=LOOPS[0];
  ensureCtx(cur.convo_id);            // lazy-load decision context; re-renders when ready
  const tags = cur.topics&&cur.topics.length
    ? cur.topics.map(t=>`<span class="tag">${esc(t)}</span>`).join('')
    : `<span class="tag none">no topic tags</span>`;

  const cx=CTX[cur.convo_id];
  let ctxHTML, recClose='', recArch='';
  if(!cx || cx==='loading'){
    ctxHTML=`<div class="ctx loading-ctx">reading the conversation&hellip;</div>`;
  } else if(cx.error){
    ctxHTML=`<div class="ctx loading-ctx">no context stored for this one</div>`;
  } else {
    if(cx.recommendation==='CLOSE') recClose=' reco'; else recArch=' reco';
    const exc = arr => arr.map(t=>`<div class="ex">${esc(t)}</div>`).join('');
    const started = cx.started&&cx.started.length? `<div class="ex-h">you opened with</div>`+exc(cx.started):'';
    const ended = cx.ended&&cx.ended.length? `<div class="ex-h">it trailed off at</div>`+exc(cx.ended):'';
    const body = (started||ended)? started+ended : `<div class="ex" style="color:var(--faint)">no excerpt stored</div>`;
    ctxHTML=`<div class="ctx">
      <div class="rec ${cx.recommendation==='CLOSE'?'rec-close':'rec-arch'}">suggests <b>${cx.recommendation}</b> &mdash; <span>${esc(cx.reason)}</span></div>
      <div class="cls-meta">${esc(cx.domain)} · ${esc(cx.outcome)} · ${esc(cx.trajectory)} · ${esc(cx.intensity)}</div>
      <details class="exwrap"><summary>what was this conversation?</summary>${body}</details>
    </div>`;
  }

  const rest=LOOPS.slice(1);
  const queue = rest.length? `<div class="queue"><div class="seg">Still in line (${rest.length})</div>`+
    rest.map((l,i)=>`<div class="qrow"><span class="qn">${String(i+2).padStart(2,'0')}</span>
       <span class="qt">${esc(l.title)}</span><span class="qs">#${esc(l.convo_id)}</span></div>`).join('')+`</div>` : '';

  app.innerHTML=head+`
    <div class="card">
      <div class="pos">Loop ${DONE+1} of ${total} · #${esc(cur.convo_id)}</div>
      <div class="title">${esc(cur.title)}</div>
      <div class="meta">stickiness score ${Number(cur.score).toLocaleString()}</div>
      <div class="tags">${tags}</div>
      ${ctxHTML}
      <div class="acts">
        <button class="btn close${recClose}" onclick="decide('CLOSE')">✓ Close · resolved</button>
        <button class="btn archive${recArch}" onclick="decide('ARCHIVE')">↳ Archive · let go</button>
        <button class="btn skip" onclick="skip()">→ Skip</button>
      </div>
      <div class="kbd"><b>C</b> close · <b>A</b> archive · <b>S</b> skip · suggested move is outlined</div>
    </div>
    ${queue}`;
}

function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA') return;
  const k=e.key.toLowerCase();
  if(k==='c') decide('CLOSE'); else if(k==='a') decide('ARCHIVE'); else if(k==='s') skip();
});
load();
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        # Client may disconnect mid-response (timeout, closed pipe). On Windows
        # that surfaces as ConnectionAbortedError; swallow it so a dropped
        # browser tab doesn't dump a traceback. See code-as-furniture.md.
        data = body.encode("utf-8") if isinstance(body, str) else body
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/loops":
            p = open_loops_payload()
            p["atlas_open"] = atlas_open_count()
            self._json(200, p)
        elif path == "/api/context":
            qs = parse_qs(urlparse(self.path).query)
            cid = (qs.get("id", [""])[0]).strip()
            if not cid:
                self._json(400, {"error": "id required"})
            else:
                self._json(200, context_for(cid))
        elif path == "/api/refresh/status":
            self._json(200, dict(_refresh))
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}

        if path == "/api/decide":
            convo_id = str(body.get("convo_id", "")).strip()
            decision = str(body.get("decision", "")).strip().upper()
            if decision not in ("CLOSE", "ARCHIVE") or not convo_id:
                self._json(400, {"ok": False, "error": "convo_id + decision(CLOSE|ARCHIVE) required"})
                return
            try:
                cl.record_decision(convo_id, decision)  # idempotent: False if already decided
                out = open_loops_payload()
                out["ok"] = True
                out["atlas_open"] = atlas_open_count()
                self._json(200, out)
            except Exception as e:  # noqa: BLE001
                self._json(500, {"ok": False, "error": str(e)})

        elif path == "/api/refresh":
            if not _refresh["running"]:
                threading.Thread(target=run_refresh, daemon=True).start()
            self._json(200, {"started": True})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, *args):  # quiet console
        pass


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"LOOP CLEARER  ->  http://{HOST}:{PORT}")
    print(f"  open loops now: {len(cl.get_open_loops())}")
    print("  Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
