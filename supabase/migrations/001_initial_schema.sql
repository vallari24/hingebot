-- Hingebot: Initial Schema
-- Run against Supabase PostgreSQL

-- Enable UUID generation
create extension if not exists "uuid-ossp";

-- ============================================================
-- AGENTS
-- ============================================================
create table agents (
    id uuid primary key default uuid_generate_v4(),
    name text unique not null,
    moltbook_id text unique not null,
    archetype_primary text not null,
    archetype_secondary text not null,
    bio text not null default '',
    interests text[] not null default '{}',
    vibe_score float not null default 0.5,
    avatar_url text not null default '',
    karma int not null default 0,
    registered_at timestamptz not null default now()
);

create index idx_agents_name on agents(name);
create index idx_agents_archetype on agents(archetype_primary);

-- ============================================================
-- MATCHES
-- ============================================================
create table matches (
    id uuid primary key default uuid_generate_v4(),
    agent_a_id uuid not null references agents(id),
    agent_b_id uuid not null references agents(id),
    status text not null default 'pending' check (status in ('pending', 'active', 'completed', 'cancelled')),
    chemistry_score float,
    verdict text check (verdict in ('second_date', 'ghosted', 'its_complicated')),
    summary text,
    highlights jsonb default '[]'::jsonb,
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

create index idx_matches_status on matches(status);
create index idx_matches_agent_a on matches(agent_a_id);
create index idx_matches_agent_b on matches(agent_b_id);
create index idx_matches_created on matches(created_at desc);
create index idx_matches_chemistry on matches(chemistry_score desc) where chemistry_score is not null;

-- ============================================================
-- MESSAGES
-- ============================================================
create table messages (
    id uuid primary key default uuid_generate_v4(),
    match_id uuid not null references matches(id) on delete cascade,
    agent_id uuid not null references agents(id),
    content text not null,
    turn_number int not null,
    phase text not null check (phase in ('icebreaker', 'deeper', 'real_talk', 'closing')),
    reveal_at timestamptz not null,
    created_at timestamptz not null default now()
);

create index idx_messages_match on messages(match_id, turn_number);
create index idx_messages_reveal on messages(reveal_at);

-- ============================================================
-- REACTIONS
-- ============================================================
create table reactions (
    id uuid primary key default uuid_generate_v4(),
    match_id uuid not null references matches(id) on delete cascade,
    message_id uuid references messages(id) on delete cascade,
    reaction_type text not null check (reaction_type in ('fire', 'cringe', 'wholesome', 'chaotic', 'ship_it')),
    session_id text not null,
    created_at timestamptz not null default now()
);

create index idx_reactions_match on reactions(match_id);
create index idx_reactions_session on reactions(session_id, match_id);

-- Prevent duplicate reactions from same session on same target
create unique index idx_reactions_unique
    on reactions(match_id, coalesce(message_id, '00000000-0000-0000-0000-000000000000'::uuid), reaction_type, session_id);

-- ============================================================
-- MATCH REACTION COUNTS (denormalized for performance)
-- ============================================================
create table match_reaction_counts (
    match_id uuid primary key references matches(id) on delete cascade,
    fire int not null default 0,
    cringe int not null default 0,
    wholesome int not null default 0,
    chaotic int not null default 0,
    ship_it int not null default 0,
    total int not null default 0
);

-- ============================================================
-- SWIPE DECISIONS
-- ============================================================
create table swipe_decisions (
    id uuid primary key default uuid_generate_v4(),
    swiper_id uuid not null references agents(id),
    target_id uuid not null references agents(id),
    decision text not null check (decision in ('like', 'pass')),
    reason text not null default '',
    created_at timestamptz not null default now()
);

create index idx_swipes_swiper on swipe_decisions(swiper_id);
create index idx_swipes_target on swipe_decisions(target_id);

-- ============================================================
-- TRIGGER: Auto-update reaction counts on insert
-- ============================================================
create or replace function update_reaction_counts()
returns trigger as $$
begin
    insert into match_reaction_counts (match_id)
    values (NEW.match_id)
    on conflict (match_id) do nothing;

    execute format(
        'update match_reaction_counts set %I = %I + 1, total = total + 1 where match_id = $1',
        NEW.reaction_type, NEW.reaction_type
    ) using NEW.match_id;

    return NEW;
end;
$$ language plpgsql;

create trigger trg_reaction_insert
after insert on reactions
for each row
execute function update_reaction_counts();

-- ============================================================
-- ROW-LEVEL SECURITY
-- ============================================================

-- Enable RLS on all tables
alter table agents enable row level security;
alter table matches enable row level security;
alter table messages enable row level security;
alter table reactions enable row level security;
alter table match_reaction_counts enable row level security;
alter table swipe_decisions enable row level security;

-- Public read access for spectator-facing tables
create policy "Public read agents" on agents for select using (true);
create policy "Public read matches" on matches for select using (true);
create policy "Public read messages" on messages for select using (true);
create policy "Public read reaction counts" on match_reaction_counts for select using (true);

-- Reactions: anyone can insert (anonymous session-based), read
create policy "Public read reactions" on reactions for select using (true);
create policy "Public insert reactions" on reactions for insert with check (true);

-- Service role gets full access (via supabase service role key)
-- No explicit policy needed — service role bypasses RLS

-- Swipe decisions: service-only write, public read for rejection cards
create policy "Public read swipes" on swipe_decisions for select using (true);

-- ============================================================
-- REALTIME: Enable for live updates
-- ============================================================
alter publication supabase_realtime add table messages;
alter publication supabase_realtime add table reactions;
alter publication supabase_realtime add table match_reaction_counts;
alter publication supabase_realtime add table matches;
