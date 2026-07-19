"""
Fightin' Words analysis for headline-tracker.

Implements Monroe, Colaresi & Quinn (2008): log-odds-ratio with an
informative Dirichlet prior, used to find words that are statistically
over-represented in one outlet's headlines vs. another's.

Usage:
    python fightin_words.py --db headlines.db --outlet1 guardian --outlet2 telegraph
    python fightin_words.py --db headlines.db --outlet1 bbc --outlet2 sky --content-type news
    python fightin_words.py --db headlines.db --outlet1 guardian --outlet2 telegraph \
        --content-type opinion --top 30

Notes:
- Compares two outlets at a time (run it pairwise for however many
  outlet combinations you want).
- Filter by content_type ('news', 'opinion', 'analysis') and/or section
  to keep comparisons apples-to-apples.
- Requires only the Python standard library (sqlite3, re, math, collections).
"""

import argparse
import math
import re
import sqlite3
from collections import Counter

# Minimal stopword list -- headlines are short, so we keep function words
# out but leave content words (including things like "benefits", "cruel")
# fully intact, since those are exactly what we're trying to surface.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was",
    "were", "will", "with", "this", "but", "or", "not", "have", "had",
    "his", "her", "their", "they", "we", "you", "i", "after", "over",
    "into", "than", "then", "how", "what", "who", "why", "amid", "amidst",
    "says", "say", "said", "new", "s",
}

TOKEN_RE = re.compile(r"[a-z']+")


def tokenize(headline: str):
    words = TOKEN_RE.findall(headline.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def resolve_outlet(conn, name):
    """Map a user-supplied outlet name to the exact value stored in the DB.

    Matching is case-insensitive, first by exact match then by prefix, so
    'guardian', 'bbc' and 'sky' resolve to 'Guardian', 'BBC News' and
    'Sky News'. Raises SystemExit on no match or an ambiguous prefix.
    """
    outlets = [r[0] for r in conn.execute("SELECT DISTINCT outlet FROM headlines")]
    lowered = name.lower()
    for o in outlets:
        if o.lower() == lowered:
            return o
    matches = [o for o in outlets if o.lower().startswith(lowered)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise SystemExit(f"Outlet '{name}' is ambiguous: matches {matches}")
    raise SystemExit(f"No outlet matching '{name}'. Available: {outlets}")


def fetch_headlines(conn, outlet, content_type=None, section=None):
    query = "SELECT headline FROM headlines WHERE outlet = ?"
    params = [outlet]
    if content_type:
        query += " AND content_type = ?"
        params.append(content_type)
    if section:
        query += " AND section = ?"
        params.append(section)
    rows = conn.execute(query, params).fetchall()
    return [r[0] for r in rows]


def fightin_words(counts1: Counter, counts2: Counter, prior_scale=0.01):
    """
    Log-odds-ratio with informative Dirichlet prior.

    prior_scale: prior pseudo-count per word is prior_scale * background
    frequency in the combined corpus (a weak, data-informed prior --
    standard choice per Monroe et al.).
    """
    vocab = set(counts1) | set(counts2)
    background = counts1 + counts2
    total_bg = sum(background.values())

    n1 = sum(counts1.values())
    n2 = sum(counts2.values())

    results = {}
    for word in vocab:
        a0 = prior_scale * total_bg  # total prior mass, informative version below
        y_wi = background[word]
        alpha_w = prior_scale * total_bg * (y_wi / total_bg) if total_bg else 0.0
        # Use a floor so rare words still get a small informative prior
        alpha_w = max(alpha_w, 1e-6)

        f1 = counts1[word] + alpha_w
        f2 = counts2[word] + alpha_w

        # Denominator per Monroe et al.: n_i + alpha_0 - (y_wi + alpha_w).
        log_odds_1 = math.log(f1 / (n1 + a0 - f1)) if (n1 + a0 - f1) > 0 else 0
        log_odds_2 = math.log(f2 / (n2 + a0 - f2)) if (n2 + a0 - f2) > 0 else 0

        delta = log_odds_1 - log_odds_2
        variance = (1.0 / f1) + (1.0 / f2)
        z = delta / math.sqrt(variance) if variance > 0 else 0.0

        results[word] = z

    return results


def main():
    parser = argparse.ArgumentParser(description="Fightin' words headline comparison")
    parser.add_argument("--db", default="headlines.db")
    parser.add_argument("--outlet1", required=True)
    parser.add_argument("--outlet2", required=True)
    parser.add_argument("--content-type", default=None,
                         help="Filter to 'news', 'opinion', or 'analysis' (default: all)")
    parser.add_argument("--section", default=None,
                         help="Filter to a specific section (default: all)")
    parser.add_argument("--top", type=int, default=25,
                         help="Number of top words to show per side")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)

    outlet1 = resolve_outlet(conn, args.outlet1)
    outlet2 = resolve_outlet(conn, args.outlet2)

    headlines1 = fetch_headlines(conn, outlet1, args.content_type, args.section)
    headlines2 = fetch_headlines(conn, outlet2, args.content_type, args.section)

    if not headlines1 or not headlines2:
        print(f"Warning: {outlet1} has {len(headlines1)} headlines, "
              f"{outlet2} has {len(headlines2)} headlines. "
              "Low volume will make results unreliable.")

    counts1 = Counter(w for h in headlines1 for w in tokenize(h))
    counts2 = Counter(w for h in headlines2 for w in tokenize(h))

    scores = fightin_words(counts1, counts2)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    print(f"\n=== {outlet1} ({len(headlines1)} headlines) "
          f"vs {outlet2} ({len(headlines2)} headlines) ===")
    if args.content_type:
        print(f"content_type = {args.content_type}")
    if args.section:
        print(f"section = {args.section}")

    print(f"\nTop {args.top} words skewing toward {outlet1} (z-score):")
    for word, z in ranked[:args.top]:
        if z > 1.96:  # roughly p < 0.05
            print(f"  {word:<20} z = {z:.2f}")

    print(f"\nTop {args.top} words skewing toward {outlet2} (z-score):")
    for word, z in ranked[-args.top:][::-1]:
        if z < -1.96:
            print(f"  {word:<20} z = {z:.2f}")

    conn.close()


if __name__ == "__main__":
    main()
