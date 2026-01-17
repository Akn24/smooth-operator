-- ProactivePA Database Schema
-- Run this in your Supabase SQL Editor

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- OAuth Tokens table (stores encrypted tokens)
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL CHECK (provider IN ('google', 'slack')),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- Meeting Prep Documents table
CREATE TABLE IF NOT EXISTS meeting_preps (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    meeting_id TEXT NOT NULL,
    prep_document JSONB NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, meeting_id)
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user_id ON oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_provider ON oauth_tokens(provider);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_user_id ON meeting_preps(user_id);
CREATE INDEX IF NOT EXISTS idx_meeting_preps_meeting_id ON meeting_preps(meeting_id);

-- Row Level Security (RLS) Policies
ALTER TABLE oauth_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_preps ENABLE ROW LEVEL SECURITY;

-- Users can only access their own OAuth tokens
CREATE POLICY "Users can view own oauth_tokens" ON oauth_tokens
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own oauth_tokens" ON oauth_tokens
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own oauth_tokens" ON oauth_tokens
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own oauth_tokens" ON oauth_tokens
    FOR DELETE USING (auth.uid() = user_id);

-- Users can only access their own meeting preps
CREATE POLICY "Users can view own meeting_preps" ON meeting_preps
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own meeting_preps" ON meeting_preps
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own meeting_preps" ON meeting_preps
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own meeting_preps" ON meeting_preps
    FOR DELETE USING (auth.uid() = user_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at on oauth_tokens
CREATE TRIGGER update_oauth_tokens_updated_at
    BEFORE UPDATE ON oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
