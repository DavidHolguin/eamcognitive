-- EAM Cognitive OS - Database Migrations
-- Run these migrations in order to set up the required tables

-- ============================================================================
-- MIGRATION 001: Enable pgvector extension
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- MIGRATION 002: Create brain_log table
-- ============================================================================
CREATE TABLE IF NOT EXISTS brain_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_type TEXT NOT NULL CHECK (step_type IN ('thinking', 'action', 'observation', 'decision', 'error')),
    content TEXT NOT NULL,
    agent TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_brain_log_run_id ON brain_log(run_id);
CREATE INDEX idx_brain_log_timestamp ON brain_log(timestamp);

-- Enable RLS
ALTER TABLE brain_log ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can read all brain logs (public for debugging)
CREATE POLICY "Users can read all brain logs" ON brain_log
    FOR SELECT USING (true);

-- RLS Policy: Only service role can insert/update
CREATE POLICY "Service role can manage brain logs" ON brain_log
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- MIGRATION 003: Create memories table with vector support
-- ============================================================================
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- OpenAI ada-002 embedding size
    memory_type TEXT NOT NULL CHECK (memory_type IN ('episodic', 'semantic', 'procedural', 'working')),
    importance FLOAT DEFAULT 0.5 CHECK (importance >= 0 AND importance <= 1),
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_memories_agent_id ON memories(agent_id);
CREATE INDEX idx_memories_memory_type ON memories(memory_type);
CREATE INDEX idx_memories_importance ON memories(importance DESC);

-- Vector similarity index (for fast similarity search)
CREATE INDEX idx_memories_embedding ON memories 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Enable RLS
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can read all memories
CREATE POLICY "Users can read all memories" ON memories
    FOR SELECT USING (true);

-- RLS Policy: Service role can manage memories
CREATE POLICY "Service role can manage memories" ON memories
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- MIGRATION 004: Create hitl_requests table
-- ============================================================================
CREATE TABLE IF NOT EXISTS hitl_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,
    requested_by UUID REFERENCES agents(id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    proposed_action JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired')),
    reviewed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    review_notes TEXT,
    reviewed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_hitl_requests_run_id ON hitl_requests(run_id);
CREATE INDEX idx_hitl_requests_status ON hitl_requests(status);
CREATE INDEX idx_hitl_requests_expires_at ON hitl_requests(expires_at);

-- Enable RLS
ALTER TABLE hitl_requests ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Authenticated users can view HITL requests
CREATE POLICY "Authenticated users can view HITL requests" ON hitl_requests
    FOR SELECT USING (auth.role() = 'authenticated');

-- RLS Policy: Service role can manage HITL requests
CREATE POLICY "Service role can manage HITL requests" ON hitl_requests
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- MIGRATION 005: Create graph_checkpoints table
-- ============================================================================
CREATE TABLE IF NOT EXISTS graph_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    parent_checkpoint_id UUID REFERENCES graph_checkpoints(id) ON DELETE CASCADE,
    channel_values JSONB NOT NULL DEFAULT '{}',
    channel_versions JSONB NOT NULL DEFAULT '{}',
    versions_seen JSONB NOT NULL DEFAULT '{}',
    pending_sends JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_graph_checkpoints_thread ON graph_checkpoints(thread_id, checkpoint_ns);
CREATE INDEX idx_graph_checkpoints_parent ON graph_checkpoints(parent_checkpoint_id);

-- Enable RLS
ALTER TABLE graph_checkpoints ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Service role only
CREATE POLICY "Service role can manage checkpoints" ON graph_checkpoints
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- MIGRATION 006: Create function for vector similarity search
-- ============================================================================
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_agent_id UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    memory_type TEXT,
    importance FLOAT,
    similarity FLOAT,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.content,
        m.memory_type,
        m.importance,
        1 - (m.embedding <=> query_embedding) AS similarity,
        m.metadata
    FROM memories m
    WHERE 
        (filter_agent_id IS NULL OR m.agent_id = filter_agent_id)
        AND 1 - (m.embedding <=> query_embedding) > match_threshold
    ORDER BY m.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- MIGRATION 007: Add trigger for automatic updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_memories_modtime
    BEFORE UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_hitl_requests_modtime
    BEFORE UPDATE ON hitl_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- ============================================================================
-- MIGRATION 008: Add agent model_config column if not exists
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'agents' AND column_name = 'model_config'
    ) THEN
        ALTER TABLE agents ADD COLUMN model_config JSONB DEFAULT '{
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2000
        }';
    END IF;
END $$;
