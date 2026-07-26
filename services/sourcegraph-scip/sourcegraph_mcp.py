#!/usr/bin/env python3
"""Sourcegraph SCIP MCP server - symbol-precise code intel over Atlas services.

Wraps the .db shards produced by reindex.py (scip expt-convert) so an MCP
client can ask defs / refs / hover / callers for any Atlas symbol without
grep-and-hope. Talks MCP over stdio - same pattern as atlas-rag/atlas_mcp.py
and zoekt-win/zoekt_mcp.py (the doctrine parents).

Sits on top of zoekt: zoekt handles fast trigram + best-effort ctags ranking;
this handles the precise xref / callers / defs / hover questions zoekt can't
answer. See project_atlas_rag_context_engine + project_zoekt_windows_native.

Run directly:  python sourcegraph_mcp.py
Register:      claude mcp add sourcegraph-scip -s user -- C:\\Python313\\python.exe <abs>\\sourcegraph_mcp.py
"""
import os
import sqlite3
from pathlib import Path

from mcp.server.fastmcp import FastMCP

INDEX_DIR = Path(os.environ.get(
    "SOURCEGRAPH_SCIP_INDEX_DIR",
    r"C:\Users\bruke\Pre Atlas\services\sourcegraph-scip\index",
))

# SCIP occurrence-role bit flags (per scip.proto SymbolRole enum).
ROLE_DEFINITION = 0x1
ROLE_IMPORT = 0x2

mcp = FastMCP("sourcegraph-scip")


def _shards() -> list[Path]:
    return sorted(INDEX_DIR.glob("*.db"))


def _query_all_shards(sql: str, params: tuple, cap: int = 200) -> list[tuple]:
    """Fan out a query across every .db shard, tag rows with shard name,
    stop once we hit `cap`. Returns list of (shard_name, *row_columns)."""
    results = []
    for shard in _shards():
        try:
            conn = sqlite3.connect(f"file:{shard}?mode=ro", uri=True)
            for row in conn.execute(sql, params):
                results.append((shard.stem, *row))
                if len(results) >= cap:
                    conn.close()
                    return results
            conn.close()
        except sqlite3.OperationalError:
            continue
    return results


def _symbol_like_patterns(name: str) -> list[str]:
    """Build the SCIP-symbol LIKE patterns for a bare identifier.
    scip-typescript symbols look like:
        scip-typescript npm <pkg> <ver> src/foo/`bar.ts`/Name#          (type)
        ...                                             /Name.          (term)
        ...                                             /Name().        (method)
    We match all three so the caller doesn't have to know which kind Name is."""
    return [f"%/{name}#", f"%/{name}.", f"%/{name}()."]


@mcp.tool()
def sourcegraph_defs(symbol: str, max_results: int = 20) -> str:
    """Find every definition of a symbol across all indexed Atlas services.

    Returns lines shaped `<service>: <file>:<line> ·<full_scip_symbol>`.
    Definitions come from the SCIP `defn_enclosing_ranges` table, which
    records (start_line, start_char) for each concrete def. Cross-shard.

    Args:
        symbol: bare identifier - e.g. "WorkController", "checkTimeouts",
                "reindex". No leading `sym:` prefix; do not include # or ().
        max_results: cap on hits (default 20).
    """
    if not _shards():
        return f"No .db shards in {INDEX_DIR}. Run reindex.py first."
    patterns = _symbol_like_patterns(symbol)
    where = " OR ".join(["gs.symbol LIKE ?" for _ in patterns])
    sql = f"""
        SELECT gs.symbol, d.relative_path, de.start_line + 1
        FROM defn_enclosing_ranges de
        JOIN global_symbols gs ON gs.id = de.symbol_id
        JOIN documents d ON d.id = de.document_id
        WHERE {where}
        ORDER BY d.relative_path, de.start_line
    """
    rows = _query_all_shards(sql, tuple(patterns), cap=int(max_results))
    if not rows:
        return f"No definitions found for `{symbol}`."
    lines = [f"{shard}: {path}:{line} ·{sym}"
             for shard, sym, path, line in rows]
    return "\n".join(lines)


@mcp.tool()
def sourcegraph_refs(symbol: str, max_results: int = 60) -> str:
    """Find every reference (call site, import, mention) of a symbol across
    all indexed Atlas services.

    Line numbers are the chunk-start line (SCIP stores exact per-occurrence
    positions in an opaque blob for size reasons; the chunk range is close
    enough to open the file and see the exact call). Cross-shard.

    Args:
        symbol: bare identifier - e.g. "WorkController".
        max_results: cap on hits (default 60).
    """
    if not _shards():
        return f"No .db shards in {INDEX_DIR}. Run reindex.py first."
    patterns = _symbol_like_patterns(symbol)
    where = " OR ".join(["gs.symbol LIKE ?" for _ in patterns])
    # role != 1 -> not a pure definition; imports (role=2) count as references.
    sql = f"""
        SELECT gs.symbol, d.relative_path, c.start_line + 1, m.role
        FROM mentions m
        JOIN chunks c ON c.id = m.chunk_id
        JOIN documents d ON d.id = c.document_id
        JOIN global_symbols gs ON gs.id = m.symbol_id
        WHERE ({where}) AND (m.role & ?) = 0
        ORDER BY d.relative_path, c.start_line
    """
    rows = _query_all_shards(sql, tuple(patterns) + (ROLE_DEFINITION,), cap=int(max_results))
    if not rows:
        return f"No references found for `{symbol}`."
    lines = [f"{shard}: {path}:~{line} ·{sym}"
             for shard, sym, path, line, _role in rows]
    return "\n".join(lines)


@mcp.tool()
def sourcegraph_callers(file: str, line: int, max_results: int = 20) -> str:
    """Find the enclosing symbol at a given file:line - i.e. "what function
    owns this line?" Useful for building inbound callgraphs one step at a time
    (find callers of X → for each ref of X, look up the enclosing symbol).

    Args:
        file: file path as it appears in the SCIP index (usually forward-slash,
              e.g. "src/core/work-controller.ts"). Substring match.
        line: 1-indexed line number in that file.
        max_results: cap on enclosing symbols (default 20).
    """
    if not _shards():
        return f"No .db shards in {INDEX_DIR}. Run reindex.py first."
    line0 = int(line) - 1
    sql = """
        SELECT gs.symbol, d.relative_path, de.start_line + 1, de.end_line + 1
        FROM defn_enclosing_ranges de
        JOIN global_symbols gs ON gs.id = de.symbol_id
        JOIN documents d ON d.id = de.document_id
        WHERE d.relative_path LIKE ?
          AND de.start_line <= ?
          AND de.end_line >= ?
        ORDER BY (de.end_line - de.start_line) ASC
    """
    rows = _query_all_shards(sql, (f"%{file}%", line0, line0), cap=int(max_results))
    if not rows:
        return f"No enclosing symbol found at `{file}:{line}`."
    lines = [f"{shard}: {sym}  ({path}:{s}-{e})"
             for shard, sym, path, s, e in rows]
    return "\n".join(lines)


@mcp.tool()
def sourcegraph_hover(symbol: str, max_results: int = 5) -> str:
    """Return signature + docstring for a symbol (SCIP `documentation` field).

    Args:
        symbol: bare identifier - e.g. "WorkController".
        max_results: cap on entries (default 5).
    """
    if not _shards():
        return f"No .db shards in {INDEX_DIR}. Run reindex.py first."
    patterns = _symbol_like_patterns(symbol)
    where = " OR ".join(["gs.symbol LIKE ?" for _ in patterns])
    sql = f"""
        SELECT gs.symbol, gs.documentation
        FROM global_symbols gs
        WHERE ({where}) AND gs.documentation IS NOT NULL AND length(gs.documentation) > 0
    """
    rows = _query_all_shards(sql, tuple(patterns), cap=int(max_results))
    if not rows:
        return f"No documentation found for `{symbol}` in any shard."
    blocks = []
    for shard, sym, doc in rows:
        blocks.append(f"[{shard}] {sym}\n{doc}\n")
    return "\n".join(blocks)


@mcp.tool()
def sourcegraph_status() -> str:
    """Report indexed shards + rough counts. Use before other tools to see
    whether a service is covered."""
    shards = _shards()
    if not shards:
        return f"No shards in {INDEX_DIR}. Run reindex.py."
    rows = []
    for s in shards:
        try:
            c = sqlite3.connect(f"file:{s}?mode=ro", uri=True)
            docs = list(c.execute("SELECT COUNT(*) FROM documents"))[0][0]
            syms = list(c.execute("SELECT COUNT(*) FROM global_symbols"))[0][0]
            c.close()
            rows.append(f"  {s.stem}: {docs} docs, {syms} symbols ({s.stat().st_size // 1024} KB)")
        except sqlite3.OperationalError as e:
            rows.append(f"  {s.stem}: unreadable ({e})")
    return f"Index: {INDEX_DIR}\n{len(shards)} shard(s):\n" + "\n".join(rows)


if __name__ == "__main__":
    mcp.run()
