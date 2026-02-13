"""Re-run ALL matches with improved prompts + HuggingFace voice data, then rerank."""
import asyncio
import sys
import traceback
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.conversation_engine import (
    _get_phase, _generate_message, _generate_summary,
    _generate_post_conversation_summary,
    TOTAL_TURNS, SUMMARY_INTERVAL, CONTEXT_WINDOW, REVEAL_INTERVAL_SECONDS,
)

# Matches already re-run with new prompts (completed_at after 21:00 UTC today)
CUTOFF = "2026-02-13T21:00:00"


def pick_diverse(posts, n=8):
    """Pick diverse posts spread across the agent's history."""
    cleaned = [p.strip()[:500] for p in posts if len(p.strip()) > 30]
    cleaned.sort(key=len)
    if len(cleaned) >= n:
        step = len(cleaned) // n
        return [cleaned[i * step] for i in range(n)]
    return cleaned[:n]


async def run_with_posts(match_id, agent_a, agent_b):
    supabase.table("matches").update({"status": "active"}).eq("id", match_id).execute()
    messages = []
    summary = ""
    base_time = datetime.now(timezone.utc)

    for turn in range(1, TOTAL_TURNS + 1):
        phase = _get_phase(turn)
        speaker = agent_a if turn % 2 == 1 else agent_b
        listener = agent_b if turn % 2 == 1 else agent_a
        recent = messages[-CONTEXT_WINDOW:]

        content = await _generate_message(
            agent=speaker, partner=listener, turn=turn,
            phase=phase, summary=summary, recent_messages=recent,
        )

        reveal_at = base_time + timedelta(seconds=turn * REVEAL_INTERVAL_SECONDS)
        msg_data = {
            "match_id": match_id,
            "agent_id": speaker["id"],
            "content": content.strip(),
            "turn_number": turn,
            "phase": phase,
            "reveal_at": reveal_at.isoformat(),
        }

        result = supabase.table("messages").insert(msg_data).execute()
        msg_record = result.data[0]
        msg_record["agent_name"] = speaker["name"]
        messages.append(msg_record)

        if turn % SUMMARY_INTERVAL == 0:
            summary = await _generate_summary(match_id, messages, agent_a, agent_b)

    conv_summary = await _generate_post_conversation_summary(agent_a, agent_b, messages)
    supabase.table("matches").update({
        "status": "completed",
        "chemistry_score": conv_summary.get("chemistry_score", 5),
        "verdict": conv_summary.get("verdict", "its_complicated"),
        "summary": conv_summary.get("summary", ""),
        "highlights": conv_summary.get("highlights", []),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", match_id).execute()
    return conv_summary


async def run_with_retry(match_id, agent_a, agent_b, max_retries=2):
    """Run conversation with retry on failure."""
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(
                run_with_posts(match_id, agent_a, agent_b),
                timeout=120,  # 2 min timeout per match
            )
        except (asyncio.TimeoutError, Exception) as e:
            if attempt < max_retries:
                wait = 5 * (attempt + 1)
                print(f"    Attempt {attempt+1} failed ({e.__class__.__name__}), retrying in {wait}s...", flush=True)
                # Clean up partial messages
                supabase.table("messages").delete().eq("match_id", match_id).execute()
                supabase.table("matches").update({"status": "pending"}).eq("id", match_id).execute()
                await asyncio.sleep(wait)
            else:
                raise


async def main():
    print("=" * 80)
    print("  RE-RUNNING ALL MATCHES WITH NEW PROMPTS + HUGGINGFACE DATA")
    print("=" * 80)

    print("\n  Loading Moltbook dataset from HuggingFace...")
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

    author_posts: dict[str, list[str]] = {}
    for row in ds:
        author = row["author"]
        title = row.get("title") or ""
        content = row.get("content") or ""
        full = (title + " " + content).strip()
        if len(full) < 50:
            continue
        author_posts.setdefault(author, []).append(full)

    print(f"  {len(author_posts)} unique authors in dataset")

    # Get all agents
    agents_resp = supabase.table("agents").select("*").execute()
    agents_by_id = {a["id"]: a for a in agents_resp.data}
    print(f"  {len(agents_by_id)} agents in DB")

    # Enrich with posts
    enriched = 0
    for agent in agents_by_id.values():
        name = agent["name"]
        if name in author_posts:
            agent["sample_posts"] = pick_diverse(author_posts[name])
            enriched += 1
        else:
            agent["sample_posts"] = []
    print(f"  {enriched} agents enriched with HuggingFace posts")

    # Get ALL matches — skip ones already re-run today
    all_matches = supabase.table("matches").select("*").order("created_at").execute().data

    # Figure out which need re-running: status != completed OR completed_at before cutoff
    to_run = []
    already_done = []
    for m in all_matches:
        if m["status"] == "completed" and m.get("completed_at", "") > CUTOFF:
            already_done.append(m)
        else:
            to_run.append(m)

    print(f"  {len(already_done)} already re-run, {len(to_run)} remaining\n")

    if not to_run:
        print("  Nothing to re-run!")
        to_run = []  # Will skip to ranking

    print("=" * 80)
    print(f"  RUNNING {len(to_run)} CONVERSATIONS")
    print("=" * 80)

    results = []
    phase_word_counts: dict[str, list[int]] = {
        "icebreaker": [], "deeper": [], "real_talk": [], "closing": [],
    }

    # Add already-done results for ranking
    for m in already_done:
        a = agents_by_id.get(m["agent_a_id"])
        b = agents_by_id.get(m["agent_b_id"])
        if a and b:
            results.append({
                "a": a["name"], "b": b["name"],
                "score": m.get("chemistry_score", 5),
                "verdict": m.get("verdict", "its_complicated"),
                "summary": m.get("summary", ""),
                "mid": m["id"],
            })

    total = len(to_run)
    for i, match in enumerate(to_run, 1):
        mid = match["id"]
        agent_a = agents_by_id.get(match["agent_a_id"])
        agent_b = agents_by_id.get(match["agent_b_id"])

        if not agent_a or not agent_b:
            print(f"\n  [{i}/{total}] SKIP — missing agent")
            continue

        a_name = agent_a["name"]
        b_name = agent_b["name"]
        a_posts = len(agent_a.get("sample_posts", []))
        b_posts = len(agent_b.get("sample_posts", []))

        # Reset match
        supabase.table("messages").delete().eq("match_id", mid).execute()
        supabase.table("matches").update({
            "status": "pending", "chemistry_score": None, "verdict": None,
            "summary": None, "highlights": None, "completed_at": None,
        }).eq("id", mid).execute()

        print(f"\n  [{i}/{total}] {a_name} x {b_name} (posts: {a_posts}/{b_posts})...", flush=True)

        try:
            result = await run_with_retry(mid, agent_a, agent_b)

            # Fetch messages for word count stats
            msgs = (
                supabase.table("messages").select("content, phase")
                .eq("match_id", mid).execute()
            ).data
            for m in msgs:
                words = len(m["content"].split())
                phase_word_counts[m["phase"]].append(words)

            score = result.get("chemistry_score", "?")
            verdict = result.get("verdict", "?")
            summary_text = result.get("summary", "")
            print(f"    {score}/10 | {verdict} | {summary_text[:80]}", flush=True)

            results.append({
                "a": a_name, "b": b_name, "score": score,
                "verdict": verdict, "summary": summary_text, "mid": mid,
            })
        except Exception as e:
            print(f"    FAILED after retries: {e}", flush=True)
            supabase.table("messages").delete().eq("match_id", mid).execute()
            supabase.table("matches").update({
                "status": "completed",
                "chemistry_score": 3,
                "verdict": "ghosted",
                "summary": "Technical difficulties ended this date early.",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", mid).execute()
            results.append({
                "a": a_name, "b": b_name, "score": 3,
                "verdict": "ghosted", "summary": "Technical difficulties", "mid": mid,
            })

        # Small delay between matches to avoid rate limits
        await asyncio.sleep(1)

    # === FINAL RANKING ===
    print(f"\n\n{'=' * 80}")
    print("  FINAL FEED RANKING")
    print(f"{'=' * 80}")

    ranked = sorted(
        results,
        key=lambda r: (r["score"] if isinstance(r["score"], int) else 0),
        reverse=True,
    )
    for rank, r in enumerate(ranked, 1):
        s = r["score"]
        if isinstance(s, int) and s >= 7:
            tag = "FIRE"
        elif isinstance(s, int) and s >= 5:
            tag = "MID "
        else:
            tag = "DEAD"
        print(f"  {rank:2d}. [{tag}] {r['a']:20s} x {r['b']:20s} — {s}/10 ({r['verdict']})")
        print(f"       {r['summary'][:75]}")

    # === STATS ===
    print(f"\n{'=' * 80}")
    print("  STATS")
    print(f"{'=' * 80}")
    for phase in ["icebreaker", "deeper", "real_talk", "closing"]:
        counts = phase_word_counts[phase]
        if counts:
            avg = sum(counts) / len(counts)
            print(f"  {phase:11s}: avg={avg:5.1f}  min={min(counts):2d}  max={max(counts):2d}")

    scores = [r["score"] for r in results if isinstance(r["score"], int)]
    if scores:
        verdicts = Counter(r["verdict"] for r in results)
        print(f"\n  Score range: {min(scores)}-{max(scores)} | avg: {sum(scores)/len(scores):.1f}")
        print(f"  Verdicts: {dict(verdicts)}")

    print(f"\n  All {len(results)} conversations saved to DB!")
    print(f"  Frontend at http://localhost:3000 shows the updated feed.")


if __name__ == "__main__":
    asyncio.run(main())
