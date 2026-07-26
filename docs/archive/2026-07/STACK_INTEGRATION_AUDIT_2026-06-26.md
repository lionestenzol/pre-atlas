# Connect-First Integration Audit — Synthesis

## Goal

Make 6 tools compose into ONE pipeline: **perceive -> compile -> carry**.

- **perceive**: binre (static RE of binaries) + ST3GG analysis (detect hidden data)
- **compile**: delta-scp (symbolic map) + code-recon/groundwork (orient + plan)
- **carry**: sigil (content-addressed container) + ST3GG (steganographic transport)

STRUDEL is out of scope (music DSL domain). PNG-Substrate is promote-or-kill (stranded demo) — backlog note only.

---

## Verdict Table

| Tool | Headless? | Speaks shared envelope? | Content-addressed? | Seam role | Verdict |
|------|-----------|------------------------|--------------------|-----------|---------|
| atlas-map (keystone) | HTTP + MCP (no CLI front door) | YES (normalized {ok,code,...} across both doors) | NO | The hub / shell-out gateway | READY. CAN shell out to local CLIs. |
| binre | CLI + in-process; no server | NO (private StageResult) | YES (sha256 of binary) | perceive | Strong node, unversioned envelope. |
| sigil | CLI + in-process; no server | NO (bespoke receipts) | YES (SGL1 sha256, enforced) | carry + join-key source | Owns the seam's content-address. |
| delta-scp | CLI + demo-server HTTP :3012 | Own {ok,...} HTTP wrapper | NO (UUID identity) | compile | Strongest schema; needs no new hashing. |
| recon/groundwork skills | orient.mjs --json (Node) | NO (recon = prose) | NO (timestamp + git-diff) | compile / orient gate | Load-bearing node is UNTRACKED in git. |
| groundwork-cli / skill-pytools | gw console-script / py runners | gw: NO. skill-pytools: YES (Result) | NO | compile -> plan | Name collision; skill-pytools is seam-fit. |
| ST3GG | Typer CLI; analysis API | analysis: YES (AnalysisResult). carry: NO | NO (CRC32 only) | carry / perceive | No --json on carry path. |

---

## Keystone Resolution: CAN

**atlas-map /call CAN shell out to a LOCAL CLI.**

`POST /call` and MCP `atlas_call` both route through `gateway.call_capability`. For a capability whose overlay declares `kind: cli`, dispatch hits `_invoke_cli`, which runs `subprocess.run(argv, cwd=<surface dir>, capture_output=True, shell=False, timeout=20s)` and returns `{stdout, stderr}` in the normalized envelope.

Hardening (all verified): opt-in behind `DESCRIBE_GATEWAY_CLI=1` (fail-closed 501 when unset); argv-only with a `--` end-of-options sentinel; leading-dash arg rejection (no flag injection); `shutil.which` absolute-path exe resolution; arg count cap 32 / length cap 512. Evidence: `gateway.py:247-277` (_invoke_cli), `:138-160` (build_argv hardening), `:311-315` (dispatch), `mcp_server.py:318-342` (atlas_call). Live overlay confirmed on disk at `services/atlas-map-api/atlas.surface.json`.

**Consequence for the backlog**: the seam is an ASSEMBLY job, not a build. Each headless tool registers a `kind:cli` capability in its own `atlas.surface.json` overlay against the already-built, ACL-enforced gateway. There is no need to hand-roll a shell-out adapter — rank #1 branches accordingly (register overlays, not build the adapter).

One correction carried from the verified set: atlas-map has **NO** sha256/content-addressing of emitted artifacts (its only sha is an HMAC existence-proof for redacted capabilities). So the seam's content-address comes from **sigil**, not atlas-map.

---

## Per-Tool Scorecard

(See structured scorecard. Summary of the load-bearing facts.)

- **binre** — emits `out/<sha256>/report.json` (fixed 5 keys, UNVERSIONED); content-addressed by sha256-of-binary; three-state `{ok,skipped}` lets a consumer tell "no tool" from "tool broke"; no server, only `python -m binre.scripts.orchestrate` or in-process `analyze()`.
- **sigil** — SGL1 header `'<4sBBIQ32sI'` (54 bytes) carries sha256 of ORIGINAL bytes, enforced on unpack (ValueError on mismatch). This is the one sound, already-built content-address in the fleet — the correct receipt join key. `container_info()` is the clean in-process minting fn. Carry-path stdout JSON is asymmetric (pack carries sha256+dict_id+ratio; unpack carries sha256 only).
- **delta-scp** — versioned named schema `CompressedState` (PROTOCOL_VERSION='1'), deterministic; second shape `PrunedState`. DB-free CLI (`npm run compress`) and sync demo-server `/jobs :3012`. NOT content-addressed (UUID). 'flue' write-side drops content-hashed `.md` but has NO downstream watcher.
- **recon/groundwork skills** — code-recon LLM emit is 7-section PROSE; only machine-readable emit is `orient.mjs --json` (a cache-staleness verdict, not findings). `orient.mjs` is UNTRACKED in `~/.claude` git. `--regen` shells out to delta-scp's TS CLI.
- **groundwork-cli / skill-pytools** — `gw` emits markdown plan.md + system-index.json (no envelope). skill-pytools emits the uniform `Result` envelope with an honest `source` enum (`binary|python|service`). skill-pytools has ZERO automated tests. NAME COLLISION between the two groundworks with incompatible 'plan' contracts.
- **ST3GG** — 32-byte binary header, CRC32 integrity (NOT sha256). Cleanest structured seam is in-process `analysis_tools.TOOL_REGISTRY.execute() -> AnalysisResult`. cli.py carry path is Rich-only (NO --json). Python reaches image-LSB only (JPEG-lethal; F5/DCT are browser-JS only).

---

## Ranked Backlog

**#1 (M) — Shared receipt envelope on sigil SGL1 sha256 + register each tool as a kind:cli overlay on atlas-map /call.**
The connective seam. Because keystone=CAN, this assembles onto the existing gateway: one `atlas.surface.json` per surface declaring the headless invoke + `kind:cli`, flip `DESCRIBE_GATEWAY_CLI=1`, define `Receipt {seam_version, tool, sha256, produced_at, status, data, error}` wrapping each native output. Mint/verify the sha256 join key in-process with `sigil.container_info()`.
*Assemble-first*: REUSE the gateway `_invoke_cli` + overlay schema (no hand-rolled adapter); REUSE sigil SGL1 sha256 (no new hashing); validate the Receipt with pydantic (already in the Python fleet). Only genuine hand-roll is the thin Receipt dataclass — justified because cross-tool envelope normalization IS the seam's product value.

**#2 (S) — Add --json carry-path output to ST3GG cli.py + symmetrize sigil's unpack receipt.**
The carry stage cannot be driven headlessly-with-data today (ST3GG shell-out returns ANSI). Reuse ST3GG's existing `AnalysisResult.to_dict()` shape for the --json emit; route sigil's missing unpack fields through the existing `receipt()`/`container_info()`. No hand-roll.

**#2 (S) — Commit code-recon (orient.mjs) + the groundwork skill into ~/.claude git.**
Both skill dirs are UNTRACKED with zero history, yet `orient.mjs` is the single load-bearing orient node the compile stage routes through. code=furniture: the most-depended-on node is outside version control. Git hygiene action, no library.

**#4 (S) — Resolve the groundwork name collision before wiring either in.**
groundwork-cli (deterministic FS/git walk -> markdown plan) vs groundwork skill/skill-pytools (agentic delta-scp->code-recon->fest -> JSON Result + proof-gated fest plan). Rank #1 registers overlays by surface name; the collision could bind `/call` to the wrong, structurally incompatible 'plan'. The skill-pytools variant is seam-fit (shared Result envelope + chains the real tools); keep groundwork-cli as the distinct human-HTML surface. Reuse the existing Result envelope; no hand-roll.

**#5 (S) — Repoint skill-pytools orient regen at the in-repo pure-Python delta-scp builder.**
`orient.regenerate()` shells out to `npx tsx <DELTA_SCP_DIR>/src/cli.ts` even though `groundwork/delta_scp.py` already has a pure-Python `skeleton()` emitting the identical shape. Removes a hard external Node/TS dependency from the compile stage. Straight repoint of one call site.

**#6 (S) — Version binre's report.json + record the fleet content-address.**
binre report.json is UNVERSIONED (no drift signal); delta-scp/code-recon are timestamp+git-diff keyed. Stamp `seam_version` on report.json; treat sigil's sha256 / binre's sha256-of-binary as the canonical content-address. delta-scp/code-recon need NOT grow hashing — they consume the join key. One-line version constant; no parallel hashing layer.

**#7 (S) — PNG-Substrate: promote-or-kill (out of scope; note only).**
Stranded demo overlapping the carry stage with no verified seam capability and no live consumer. Either promote into the rank-#1 overlay/receipt scheme, or remove it (code=furniture: no broken/unused furniture). Disposition decision, not a seam dependency.

---

## Discarded (unverified)

Claims that did NOT survive 2+ angle verification, excluded from the scorecard and backlog body:

**Partial (load-bearing precision gaps — core true, detail busted):**
- atlas-map envelope: `cwd` is NOT forwarded into `_meta()` at any call site (docstring lies); the rest of the role-gated meta contract holds.
- binre "orchestrator never raises": true for the CLI wrapper only — `analyze()` DOES raise `FileNotFoundError` on bad input paths.
- sigil "NO version field": the `info` subcommand DOES emit `version:1` (the SGL1 wire-format version, not a schema-envelope version).
- delta-scp "CLI takes the same target as argv[0]": undersells the CLI's real flag grammar (--anchor/--symbol/--trace/--md/--flue have no HTTP equivalent).
- delta-scp "matches the project's {success,data,error} contract": FALSE at the key level — actual key is `ok`, payload is inlined, there is no `data` key.
- delta-scp flue "already wired to downstream": only the WRITE side exists; droplist has NO file-inbox watcher.
- recon-skills "orient.mjs is THE shared seam node": NOT supported — orient.mjs is code-recon-internal; groundwork resolves duplication by conditional-skip, not a shared node.
- recon-skills "two real caches prove end-to-end": only the STRUDEL cache is genuine; the orienttest cache is a synthetic stub.
- groundwork-cli "only fest + git log shell-outs": omits the OS-open calls (os.startfile/open/xdg-open) in `_open()`.
- groundwork-cli "doctor takes a positional repo path": FALSE (doctor uses `add_common(repo=False)`).
- skill-pytools "all three runners honor --json in either argv position": FALSE for `search_stack.py` (nargs='+' positional eats post-positional --json).
- skill-pytools "client degrades to ok=false service-down for BOTH services": FALSE for delta_scp (silently falls through to an offline Python walker; no start-hint).
- skill-pytools "verify/drift emit the Result envelope": they return bare dicts, not the typed Result dataclass; "~50 generic words" is actually 33.
- ST3GG "encode/decode run fully headless": partially noisy even with --quiet (success()/info() always print).

**Busted (claim directly contradicted):**
- recon-skills "groundwork emits NO machine-readable artifact / can only be invoked as LLM doctrine": FALSE — conflates the Claude skill with groundwork-cli, which is a pip-installed `gw` CLI emitting system-index.json + system-map.html + plan.md headlessly.

---

## Notes

- Stats from the verified set: 74 load-bearing claims, 56 verified, 17 partial, 1 busted.
- The seam's content-address is sigil's SGL1 sha256 (verified sound), NOT atlas-map (no content-addressing) — every other tool consumes it as the join key rather than minting its own.
