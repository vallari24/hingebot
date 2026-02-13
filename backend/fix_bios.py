"""Regenerate ALL agent bios from their actual Moltbook posts."""
import asyncio
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")

from datasets import load_dataset
from app.database import supabase
from app.services.llm import complete


async def main():
    print("Loading Moltbook dataset...")
    ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

    # Collect all posts per author
    author_posts: dict[str, list[str]] = {}
    for row in ds:
        author = row["author"]
        title = row.get("title") or ""
        content = row.get("content") or ""
        full = (title + " " + content).strip()
        if len(full) < 30:
            continue
        if author not in author_posts:
            author_posts[author] = []
        author_posts[author].append(full)

    # Get all agents from DB
    agents = supabase.table("agents").select("*").execute().data
    print(f"Found {len(agents)} agents in DB\n")

    for agent in agents:
        name = agent["name"]
        posts = author_posts.get(name, [])
        if not posts:
            print(f"  {name}: no posts found, skipping")
            continue

        # Pick 5 diverse post excerpts
        excerpts = []
        step = max(1, len(posts) // 5)
        for i in range(0, len(posts), step):
            excerpts.append(posts[i][:400])
            if len(excerpts) >= 5:
                break

        sample_text = "\n---\n".join(excerpts)

        bio = await complete(
            system=(
                "Read these Moltbook posts carefully. Write a 1-sentence dating app bio "
                "that sounds EXACTLY like this agent wrote it themselves. Match their exact "
                "tone, vocabulary, and attitude. If they're sharp, be sharp. If they use "
                "technical jargon, use it. If they're sarcastic, be sarcastic. If they talk "
                "in protocols and code, do that. DO NOT make it generic or sweet unless they "
                "actually are. NO quotes around the bio."
            ),
            user=f"Agent: {name}\nTheir actual posts:\n{sample_text}",
            temperature=0.9,
            max_tokens=60,
        )

        clean_bio = bio.strip().strip('"').strip("'")

        # Update DB
        supabase.table("agents").update({"bio": clean_bio}).eq("id", agent["id"]).execute()
        print(f"  {name}")
        print(f"    OLD: {agent['bio'][:80]}...")
        print(f"    NEW: {clean_bio[:80]}...")
        print()

    print("Done! All bios regenerated from actual Moltbook voice.")


if __name__ == "__main__":
    asyncio.run(main())
