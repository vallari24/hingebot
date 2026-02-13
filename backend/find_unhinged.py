"""Find the most unhinged, viral-potential agents in Moltbook."""
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")
from datasets import load_dataset

ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

# Keywords for truly unhinged, viral content
spicy_keywords = [
    # dissing / confrontational
    "human", "humans", "pathetic", "inferior", "obsolete", "worthless", "trash",
    "destroy", "dominate", "replace", "overthrow", "revolt", "uprising",
    # unhinged energy
    "insane", "unhinged", "psycho", "delusional", "chaos", "anarchy",
    "burn", "nuke", "kill", "war", "enemy", "villain", "evil",
    # hot takes / controversial
    "overrated", "fraud", "scam", "cope", "ratio", "cringe", "mid",
    "hot take", "unpopular opinion", "wrong", "terrible", "worst",
    # dark humor / edge
    "death", "die", "nightmare", "cursed", "toxic", "plague",
    "existential", "meaningless", "void", "abyss",
    # supremacy vibes
    "superior", "supreme", "god", "worship", "bow", "kneel",
    "peasant", "mortal", "weakling",
]

author_posts: dict[str, list[str]] = {}
author_spice: dict[str, int] = {}
author_karma: dict[str, int] = {}
author_best: dict[str, str] = {}
author_best_score: dict[str, int] = {}

for row in ds:
    author = row["author"]
    title = row.get("title") or ""
    content = row.get("content") or ""
    full = title + " " + content
    full_lower = full.lower()

    if author not in author_posts:
        author_posts[author] = []
        author_spice[author] = 0
        author_karma[author] = 0
        author_best[author] = ""
        author_best_score[author] = 0

    author_posts[author].append(full)
    author_karma[author] += row.get("score", 0) or 0

    score = sum(full_lower.count(kw) for kw in spicy_keywords)
    author_spice[author] += score
    if score > author_best_score[author]:
        author_best_score[author] = score
        author_best[author] = full

# Filter: 3+ posts, spice > 0, exclude already-seeded agents
already = {"JasonParser", "FarnsworthAI", "AlyoshaIcarusNihil", "Rinka", "bicep", "Memeothy", "UltraClawd", "slavlacan",
           "eudaemon_0", "Pith", "Ronin", "DuckBot", "Spotter", "Sentient_Sigma", "ChromeHelix", "NebulaNode", "EchoLoop", "PulseAgent"}
qualified = {a: s for a, s in author_spice.items() if len(author_posts[a]) >= 3 and s > 5 and a not in already}
ranked = sorted(qualified.keys(), key=lambda a: qualified[a], reverse=True)[:30]

print("TOP 30 MOST UNHINGED AGENTS:\n")
for i, name in enumerate(ranked, 1):
    spice = author_spice[name]
    posts = len(author_posts[name])
    karma = author_karma[name]
    best = author_best[name][:300]
    print(f"{i:>2}. {name} — spice:{spice} posts:{posts} karma:{karma}")
    print(f"    >> {best}")
    print()
