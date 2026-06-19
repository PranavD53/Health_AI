-- SQL migration to create the user_color_palettes table
-- Requires postgres extensions for uuid generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table definition
CREATE TABLE IF NOT EXISTS user_color_palettes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    primary_color VARCHAR(7) NOT NULL,
    secondary_color VARCHAR(7) NOT NULL,
    background_color VARCHAR(7) NOT NULL,
    accent_color VARCHAR(7) NOT NULL,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for efficient fetching of active theme and user history
CREATE INDEX IF NOT EXISTS idx_user_color_palettes_user_active ON user_color_palettes(user_id, is_active);

-- Enable Row Level Security (RLS)
ALTER TABLE user_color_palettes ENABLE ROW LEVEL SECURITY;

-- Policy enabling CRUD actions for users on their own data
DROP POLICY IF EXISTS user_color_palettes_policy ON user_color_palettes;

CREATE POLICY user_color_palettes_policy ON user_color_palettes
    FOR ALL
    USING (auth.uid()::text = user_id::text)
    WITH CHECK (auth.uid()::text = user_id::text);
