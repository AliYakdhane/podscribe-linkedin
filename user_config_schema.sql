-- User Configuration Table Schema
-- This table stores user preferences from the Streamlit UI

CREATE TABLE IF NOT EXISTS user_config (
    id TEXT PRIMARY KEY DEFAULT 'user_config',
    show_id TEXT,
    apple_episode_url TEXT,
    max_episodes_per_run INTEGER DEFAULT 1,
    openai_api_key TEXT, -- Only for local testing, not used in production
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE user_config ENABLE ROW LEVEL SECURITY;

-- Policy for service role access
CREATE POLICY "Allow all operations for service role" ON user_config
FOR ALL 
TO service_role
USING (true)
WITH CHECK (true);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_config_updated_at 
    BEFORE UPDATE ON user_config 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default configuration
INSERT INTO user_config (id, show_id, apple_episode_url, max_episodes_per_run)
VALUES ('user_config', '', '', 1)
ON CONFLICT (id) DO NOTHING;
