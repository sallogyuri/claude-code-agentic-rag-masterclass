-- Module 3: Record Manager
-- Add content_hash to documents for duplicate detection and change tracking

ALTER TABLE documents ADD COLUMN content_hash text;

-- Index for fast lookup: "does this user already have a file with this hash?"
CREATE INDEX idx_documents_user_hash ON documents(user_id, content_hash);
