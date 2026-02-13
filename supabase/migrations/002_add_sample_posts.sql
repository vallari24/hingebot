-- Add sample_posts column to agents for voice reference in conversations
alter table agents add column if not exists sample_posts jsonb default '[]'::jsonb;
