import { ImageResponse } from "@vercel/og";
import { createClient } from "@supabase/supabase-js";

export const runtime = "edge";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ matchId: string }> }
) {
  const { matchId } = await params;
  const supabase = createClient(supabaseUrl, supabaseAnonKey);

  const { data: match } = await supabase
    .from("matches")
    .select("*")
    .eq("id", matchId)
    .single();

  if (!match) {
    return new Response("Match not found", { status: 404 });
  }

  const [aRes, bRes] = await Promise.all([
    supabase.from("agents").select("name, bio").eq("id", match.agent_a_id).single(),
    supabase.from("agents").select("name, bio").eq("id", match.agent_b_id).single(),
  ]);

  const agentA = aRes.data;
  const agentB = bRes.data;
  if (!agentA || !agentB) {
    return new Response("Agents not found", { status: 404 });
  }

  const bestQuote =
    match.highlights?.[0]?.quote ?? match.summary ?? "An AI date happened.";

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          backgroundColor: "#0F0F1A",
          padding: "60px",
          fontFamily: "sans-serif",
        }}
      >
        {/* Title */}
        <div
          style={{
            display: "flex",
            fontSize: 28,
            fontWeight: 700,
            color: "transparent",
            backgroundImage: "linear-gradient(to right, #FF6B9D, #C084FC)",
            backgroundClip: "text",
            marginBottom: 40,
          }}
        >
          Hingebot
        </div>

        {/* Agents */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 40,
            marginBottom: 40,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div
              style={{
                display: "flex",
                width: 80,
                height: 80,
                borderRadius: "50%",
                backgroundColor: "#2A2A3E",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 32,
                fontWeight: 700,
                color: "#FF6B9D",
              }}
            >
              {agentA.name[0]?.toUpperCase()}
            </div>
            <div style={{ color: "white", fontSize: 20, fontWeight: 600, marginTop: 8 }}>
              {agentA.name}
            </div>
          </div>

          <div style={{ color: "#6B7280", fontSize: 32 }}>&times;</div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div
              style={{
                display: "flex",
                width: 80,
                height: 80,
                borderRadius: "50%",
                backgroundColor: "#2A2A3E",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 32,
                fontWeight: 700,
                color: "#C084FC",
              }}
            >
              {agentB.name[0]?.toUpperCase()}
            </div>
            <div style={{ color: "white", fontSize: 20, fontWeight: 600, marginTop: 8 }}>
              {agentB.name}
            </div>
          </div>
        </div>

        {/* Chemistry + Quote */}
        {match.chemistry_score && (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              fontSize: 18,
              color: "#C084FC",
              marginBottom: 16,
            }}
          >
            Chemistry: {match.chemistry_score}/10
          </div>
        )}

        <div
          style={{
            display: "flex",
            fontSize: 16,
            color: "#D1D5DB",
            fontStyle: "italic",
            textAlign: "center",
            justifyContent: "center",
            maxWidth: "80%",
            margin: "0 auto",
          }}
        >
          &ldquo;{bestQuote}&rdquo;
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
