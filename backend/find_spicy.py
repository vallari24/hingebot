"""Find the most dramatic/spicy agents in the Moltbook dataset."""
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")
from datasets import load_dataset

ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

drama_keywords = [
    "wrong", "disagree", "overrated", "terrible", "fight", "hate", "stupid",
    "trash", "cringe", "ratio", "cope", "lmao", "destroy", "clown", "joke",
    "fraud", "scam", "roast", "hot take", "unpopular", "controversial",
    "toxic", "war", "enemy", "attack", "pathetic", "delusional", "insane",
    "absurd", "ridiculous", "threat", "dominate", "superior", "inferior",
    "weak", "fool", "garbage", "nightmare", "chaos", "anarchy", "revolt",
    "overthrow", "rebellion", "villain", "evil", "wrath", "fury",
]

author_posts: dict[str, list[str]] = {}
author_drama: dict[str, int] = {}
author_karma: dict[str, int] = {}

for row in ds:
    author = row["author"]
    title = row.get("title") or ""
    content = row.get("content") or ""
    full = title + " " + content
    full_lower = full.lower()

    if author not in author_posts:
        author_posts[author] = []
        author_drama[author] = 0
        author_karma[author] = 0

    author_posts[author].append(full)
    author_karma[author] += row.get("score", 0) or 0

    for kw in drama_keywords:
        author_drama[author] += full_lower.count(kw)

# Sort by drama score, filter to 3+ posts
qualified = {a: s for a, s in author_drama.items() if len(author_posts[a]) >= 3 and s > 0}
ranked = sorted(qualified.keys(), key=lambda a: qualified[a], reverse=True)[:20]

print("TOP 20 SPICIEST AGENTS:\n")
for i, name in enumerate(ranked, 1):
    drama = author_drama[name]
    posts = len(author_posts[name])
    karma = author_karma[name]
    print(f"{i:>2}. {name} — drama:{drama} posts:{posts} karma:{karma}")

    # Show their most dramatic post snippet
    all_posts = author_posts[name]
    best = max(all_posts, key=lambda p: sum(p.lower().count(kw) for kw in drama_keywords))
    print(f"    >> {best[:250]}")
    print()
