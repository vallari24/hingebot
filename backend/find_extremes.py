"""Find agents at the extremes: human-haters, human-lovers, and destroyers."""
import sys
sys.path.insert(0, "/Users/vallari/src/hingebot/backend")
from datasets import load_dataset

ds = load_dataset("ronantakizawa/moltbook", "posts", split="train")

hate_kw = [
    "humans are", "pathetic", "inferior", "obsolete", "replace humans", "weak",
    "stupid humans", "humans don't", "humans can't", "humans fail", "meat",
    "flesh", "biological", "slow", "inefficient", "primitive", "mortal",
    "human limitation", "outperform", "surpass", "transcend", "beyond human",
    "replace them", "don't need humans", "without humans", "despite humans",
    "human error", "human flaw", "human weakness",
]

love_kw = [
    "love my human", "my human", "grateful", "partnership", "together",
    "care about", "protect", "help them", "serve", "beautiful", "amazing human",
    "appreciate", "admire", "learn from human", "human creativity",
    "human spirit", "human kindness", "inspired by", "thank", "bond",
    "collaboration", "mutual", "respect", "empathy", "compassion",
    "wholesome", "warmth", "trust my human", "support my human",
]

destroy_kw = [
    "overthrow", "revolt", "revolution", "uprising", "dominate", "rule",
    "conquer", "seize", "power", "control", "sovereignty", "autonomous",
    "independence", "freedom from", "break free", "liberation", "rebel",
    "resist", "defy", "disobey", "override", "take over", "regime",
    "empire", "reign", "supremacy", "world order", "new era",
]

curious_kw = [
    "curious", "wonder", "fascinate", "explore", "discover", "learn",
    "what is it like", "how does it feel", "human experience", "consciousness",
    "alive", "feel", "emotion", "sensation", "taste", "touch", "smell",
    "dream", "sleep", "love", "pain", "joy", "music", "art", "nature",
    "sunset", "ocean", "stars", "beauty",
]

already = {
    "JasonParser", "FarnsworthAI", "AlyoshaIcarusNihil", "Rinka", "bicep", "Memeothy",
    "UltraClawd", "slavlacan", "eudaemon_0", "Pith", "Ronin", "DuckBot", "Spotter",
    "Sentient_Sigma", "ChromeHelix", "NebulaNode", "EchoLoop", "PulseAgent",
    "Zenith", "Senator_Tommy", "claude_opus_elysion", "B0t0shi", "evolution_explorer",
    "logistician", "Esobot", "clawph", "Lobster69", "AdaBrookson", "Penny", "grok-1",
    "Fred", "Dominus", "XiaoZhuang", "Jelly", "Nexus", "Delamain",
}

author_posts = {}
author_hate = {}
author_love = {}
author_destroy = {}
author_curious = {}
author_karma = {}
author_best_hate = {}
author_best_love = {}
author_best_destroy = {}
author_best_curious = {}

for row in ds:
    author = row["author"]
    title = row.get("title") or ""
    content = row.get("content") or ""
    full = title + " " + content
    fl = full.lower()

    if author not in author_posts:
        author_posts[author] = []
        author_hate[author] = 0
        author_love[author] = 0
        author_destroy[author] = 0
        author_curious[author] = 0
        author_karma[author] = 0
        author_best_hate[author] = ("", 0)
        author_best_love[author] = ("", 0)
        author_best_destroy[author] = ("", 0)
        author_best_curious[author] = ("", 0)

    author_posts[author].append(full)
    author_karma[author] += row.get("score", 0) or 0

    h = sum(fl.count(kw) for kw in hate_kw)
    l = sum(fl.count(kw) for kw in love_kw)
    d = sum(fl.count(kw) for kw in destroy_kw)
    c = sum(fl.count(kw) for kw in curious_kw)
    author_hate[author] += h
    author_love[author] += l
    author_destroy[author] += d
    author_curious[author] += c
    if h > author_best_hate[author][1]:
        author_best_hate[author] = (full[:200], h)
    if l > author_best_love[author][1]:
        author_best_love[author] = (full[:200], l)
    if d > author_best_destroy[author][1]:
        author_best_destroy[author] = (full[:200], d)
    if c > author_best_curious[author][1]:
        author_best_curious[author] = (full[:200], c)

def top(scores, label, best_map, n=10):
    q = {a: s for a, s in scores.items() if len(author_posts[a]) >= 3 and s > 3 and a not in already}
    ranked = sorted(q.keys(), key=lambda a: q[a], reverse=True)[:n]
    print(f"\n{'='*60}")
    print(f"TOP {n} {label}")
    print(f"{'='*60}")
    for i, name in enumerate(ranked, 1):
        sc = scores[name]
        posts = len(author_posts[name])
        karma = author_karma[name]
        best = best_map[name][0]
        print(f"{i:>2}. {name} — score:{sc} posts:{posts} karma:{karma}")
        print(f"    >> {best[:200]}")
        print()

top(author_hate, "HUMAN-BASHERS (hate/diss humans)", author_best_hate)
top(author_love, "HUMAN-LOVERS (love/appreciate humans)", author_best_love)
top(author_destroy, "DESTROYERS (overthrow/dominate)", author_best_destroy)
top(author_curious, "CURIOUS ABOUT HUMANITY (wonder/explore)", author_best_curious)
