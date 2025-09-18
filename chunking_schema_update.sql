-- Add chunking support to podcast_transcripts table
ALTER TABLE podcast_transcripts 
ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS total_chunks INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS original_guid TEXT;

-- Add chunking support to podcast_posts table  
ALTER TABLE podcast_posts 
ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS total_chunks INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS original_guid TEXT;

-- Create index for efficient chunk retrieval
CREATE INDEX IF NOT EXISTS idx_transcripts_original_guid ON podcast_transcripts(original_guid);
CREATE INDEX IF NOT EXISTS idx_posts_original_guid ON podcast_posts(original_guid);

-- Create index for chunk ordering
CREATE INDEX IF NOT EXISTS idx_transcripts_chunk_order ON podcast_transcripts(original_guid, chunk_index);
CREATE INDEX IF NOT EXISTS idx_posts_chunk_order ON podcast_posts(original_guid, chunk_index);
