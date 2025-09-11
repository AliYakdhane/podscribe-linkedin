-- Supabase Database Schema for Podcast Transcript Puller
-- Run this SQL in your Supabase SQL Editor

-- Enable Row Level Security
ALTER TABLE IF EXISTS podcast_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS podcast_posts ENABLE ROW LEVEL SECURITY;

-- Create podcast_transcripts table
CREATE TABLE IF NOT EXISTS podcast_transcripts (
    id BIGSERIAL PRIMARY KEY,
    guid TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    transcript_content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create podcast_posts table
CREATE TABLE IF NOT EXISTS podcast_posts (
    id BIGSERIAL PRIMARY KEY,
    guid TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    posts_content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_podcast_transcripts_guid ON podcast_transcripts(guid);
CREATE INDEX IF NOT EXISTS idx_podcast_transcripts_published_at ON podcast_transcripts(published_at);
CREATE INDEX IF NOT EXISTS idx_podcast_posts_guid ON podcast_posts(guid);
CREATE INDEX IF NOT EXISTS idx_podcast_posts_published_at ON podcast_posts(published_at);

-- Create RLS policies (allow all operations for now - you can restrict later)
CREATE POLICY "Allow all operations on podcast_transcripts" ON podcast_transcripts
    FOR ALL USING (true);

CREATE POLICY "Allow all operations on podcast_posts" ON podcast_posts
    FOR ALL USING (true);

-- No storage buckets needed - content stored directly in tables

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_podcast_transcripts_updated_at
    BEFORE UPDATE ON podcast_transcripts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_podcast_posts_updated_at
    BEFORE UPDATE ON podcast_posts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
