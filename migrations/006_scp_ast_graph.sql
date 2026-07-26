-- Migration 006: Delta SCP AST Knowledge Graph
-- Node-and-edge model of a codebase, stored Postgres-native (no Neo4j). Lets the
-- Delta SCP engine ingest a dependency graph from the database instead of walking
-- a filesystem: pull a focus node plus its dependency closure in one recursive
-- query, compress only those nodes, and ignore the rest of a 5,000-file repo.
--
-- Populated by the graph builder (src/graph.ts), which currently derives nodes
-- from the engine's existing symbol extractor. Edges are limited to `imports`
-- until a true-AST pass (tree-sitter) lands — see graph.ts for the seam.
--
-- Idempotent: safe to re-run via `npm run migrate`. gen_random_uuid() requires
-- pgcrypto (Supabase enables it by default; bare Postgres: CREATE EXTENSION
-- IF NOT EXISTS pgcrypto;). Mirrors the convention in 004_scp_compression_queue.

-- 1. ENUMs — wrapped so re-running the migration does not error on duplicate type.
DO $$
BEGIN
    CREATE TYPE node_type AS ENUM
        ('file', 'class', 'function', 'interface', 'variable', 'type_definition');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    CREATE TYPE edge_type AS ENUM
        ('imports', 'calls', 'implements', 'inherits', 'instantiates', 'references');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. NODES — the codebase elements (files + the symbols inside them).
CREATE TABLE IF NOT EXISTS ast_nodes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_name     TEXT NOT NULL,
    node_type     node_type NOT NULL,
    name          TEXT NOT NULL,        -- "compressPayload" or "DropListValidator.ts"
    file_path     TEXT NOT NULL,
    start_line    INTEGER,
    end_line      INTEGER,
    raw_signature TEXT,                 -- the declaration line(s) — highly compressible
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- Drop List flags / Chainer routing hints
    checksum      TEXT,                 -- re-index trigger: changed content => changed checksum
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- A node is unique within a repo by where it lives and what it is.
    CONSTRAINT ast_nodes_identity UNIQUE (repo_name, file_path, name, node_type)
);

-- 3. EDGES — the structural graph between nodes.
CREATE TABLE IF NOT EXISTS ast_edges (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id  UUID NOT NULL REFERENCES ast_nodes(id) ON DELETE CASCADE,
    target_id  UUID NOT NULL REFERENCES ast_nodes(id) ON DELETE CASCADE,
    edge_type  edge_type NOT NULL,
    weight     INTEGER NOT NULL DEFAULT 1,  -- prune low-weight edges first under pressure
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ast_edges_identity UNIQUE (source_id, target_id, edge_type)
);

-- 4. INDEXES — tuned for the recursive dependency-closure queries the reader runs.
CREATE INDEX IF NOT EXISTS idx_ast_nodes_path     ON ast_nodes (file_path);
CREATE INDEX IF NOT EXISTS idx_ast_nodes_type     ON ast_nodes (node_type);
CREATE INDEX IF NOT EXISTS idx_ast_nodes_repo     ON ast_nodes (repo_name);
CREATE INDEX IF NOT EXISTS idx_ast_nodes_metadata ON ast_nodes USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_ast_edges_source   ON ast_edges (source_id);
CREATE INDEX IF NOT EXISTS idx_ast_edges_target   ON ast_edges (target_id);

-- Keep updated_at fresh on every mutation (matches 004's trigger convention).
CREATE OR REPLACE FUNCTION ast_nodes_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ast_nodes_touch ON ast_nodes;
CREATE TRIGGER trg_ast_nodes_touch
    BEFORE UPDATE ON ast_nodes
    FOR EACH ROW
    EXECUTE FUNCTION ast_nodes_touch_updated_at();

-- 5. Flat join view — one row per edge with both endpoints resolved, so the
-- reader can pull a node and its neighbours without a second round trip.
CREATE OR REPLACE VIEW codebase_graph_view AS
SELECT
    e.id        AS edge_id,
    e.edge_type,
    e.weight,
    s.repo_name AS repo_name,
    s.id        AS source_id,
    s.name      AS source_name,
    s.node_type AS source_type,
    s.file_path AS source_path,
    t.id        AS target_id,
    t.name      AS target_name,
    t.node_type AS target_type,
    t.file_path AS target_path
FROM ast_edges e
JOIN ast_nodes s ON e.source_id = s.id
JOIN ast_nodes t ON e.target_id = t.id;
