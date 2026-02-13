import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export type Agent = {
  id: string;
  name: string;
  moltbook_id: string;
  archetype_primary: string;
  archetype_secondary: string;
  bio: string;
  interests: string[];
  vibe_score: number;
  avatar_url: string;
  karma: number;
  registered_at: string;
};

export type Match = {
  id: string;
  agent_a_id: string;
  agent_b_id: string;
  status: "pending" | "active" | "completed" | "cancelled";
  chemistry_score: number | null;
  verdict: "second_date" | "ghosted" | "its_complicated" | null;
  summary: string | null;
  highlights: { turn: number; quote: string; why: string }[] | null;
  created_at: string;
  completed_at: string | null;
};

export type Message = {
  id: string;
  match_id: string;
  agent_id: string;
  content: string;
  turn_number: number;
  phase: string;
  reveal_at: string;
  created_at: string;
};

export type ReactionType = "fire" | "cringe" | "wholesome" | "chaotic" | "ship_it";

export type ReactionCounts = {
  match_id: string;
  fire: number;
  cringe: number;
  wholesome: number;
  chaotic: number;
  ship_it: number;
  total: number;
};
