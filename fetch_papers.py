"""
Daily Paper Digest — Semantic Scholar API only, no AI API needed.
Strategy:
  - Multiple keyword searches across 3 themes (rotated by day)
  - Venue sweep on top of keyword results
  - Deduplicate against seen_papers.json
  - Rank: recent (last 12 months) + venue match, sorted by citation count
  - Pick top 5, push to ntfy.sh
"""

import os
import json
import datetime
import random
import time
import requests

S2_API_KEY = os.environ.get("S2_API_KEY", "")  # optional, raises rate limit
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_URL   = f"https://ntfy.sh/{NTFY_TOPIC}"
LOG_FILE   = "seen_papers.json"

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS    = "paperId,title,authors,year,citationCount,venue,externalIds,abstract,publicationDate"

# ── Venue allowlist ────────────────────────────────────────────────────────
VENUE_KEYWORDS = [
    "CHI", "UIST", "TEI", "Tangible",
    "Haptics", "Haptic", "World Haptics", "EuroHaptics",
    "ICRA", "IROS", "Science Robotics", "Soft Robotics",
    "ISMAR", "IEEE Transactions on Haptics",
    "Nature", "Advanced Materials",
    "Advanced Intelligent Systems", "Advanced Functional Materials",
    "npj Flexible Electronics", "Nature Machine Intelligence",
    "Nature Electronics", "Nature Communications",
]

# ── Keyword pools per theme ────────────────────────────────────────────────
THEME_QUERIES = {
    "devices": [
        "wearable haptic actuator",
        "pneumatic soft haptic device",
        "vibrotactile feedback wearable",
        "hydraulic soft actuator fingertip",
        "thermal haptic feedback wearable",
        "mid-air haptics ultrasound",
        "electrohydraulic soft actuator haptics",
        "soft robotic glove tactile",
    ],
    "materials": [
        "soft actuator smart material",
        "shape memory polymer soft robotics",
        "stretchable electronics tactile sensor",
        "liquid crystal elastomer actuator",
        "dielectric elastomer actuator haptic",
        "hydrogel soft robot actuator",
        "origami soft robot reconfigurable",
        "magnetic soft robot skin",
    ],
    "experience": [
        "haptic perception user study",
        "tactile feedback psychophysics",
        "affective haptics social touch",
        "multimodal haptic interaction",
        "haptic texture rendering",
        "embodiment wearable haptic",
        "haptic feedback virtual reality experience",
        "haptic design user centered",
    ],
}

# Day-of-week rotation
DAILY_MIX = [
    ["devices", "materials"],                    # Mon
    ["experience", "devices"],                   # Tue
    ["materials", "experience"],                 # Wed
    ["devices", "experience", "materials"],      # Thu — all themes
    ["experience", "materials"],                 # Fri
    ["devices", "materials"],                    # Sat
    ["experience", "devices"],                   # Sun
]

VENUE_SWEEP_QUERIES = [
    "soft haptic actuator CHI",
    "tactile feedback UIST",
    "wearable haptics IEEE Haptics",
    "soft robotics Nature",
    "haptic perception World Haptics",
    "smart material actuator Advanced Materials",
    "soft robot skin tactile Science Robotics",
]


# ── Helpers ────────────────────────────────────────────────────────────────

def load_seen() -> list:
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def save_seen(seen: list):
    if len(seen) > 400:
        seen = seen[-400:]
    with open(LOG_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def build_seen_set(seen: list) -> set:
    ids    = {p.get("paperId") for p in seen if p.get("paperId")}
    titles = {p["title"][:40].lower() for p in seen if p.get("title")}
    return ids | titles


def s2_search(query: str, limit: int = 50) -> list:
    headers = {"x-api-key": S2_API_KEY} if S2_API_KEY else {}
    for attempt in range(3):
        try:
            r = requests.get(
                S2_SEARCH,
                params={"query": query, "limit": limit, "fields": FIELDS},
                headers=headers,
                timeout=20,
            )
            if r.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s …")
                time.sleep(wait)
                continue
            r.raise_for_status()
            time.sleep(1.5)  # polite delay between requests
            return r.json().get("data", [])
        except Exception as e:
            print(f"  Search error ({query!r}): {e}")
            return []
    print(f"  Giving up on {query!r} after 3 attempts")
    return []


def is_recent(paper: dict, months: int = 36) -> bool:
    pub = paper.get("publicationDate") or ""
    if pub:
        try:
            d = datetime.date.fromisoformat(pub[:10])
            return d >= datetime.date.today() - datetime.timedelta(days=months * 30)
        except ValueError:
            pass
    year = paper.get("year")
    return bool(year and year >= datetime.date.today().year - 3)


def venue_match(paper: dict) -> bool:
    venue = (paper.get("venue") or "").upper()
    return any(kw.upper() in venue for kw in VENUE_KEYWORDS)


def is_duplicate(paper: dict, seen: set) -> bool:
    if paper.get("paperId") in seen:
        return True
    return (paper.get("title") or "")[:40].lower() in seen


def paper_url(paper: dict) -> str:
    doi = (paper.get("externalIds") or {}).get("DOI")
    if doi:
        return f"https://doi.org/{doi}"
    pid = paper.get("paperId")
    return f"https://www.semanticscholar.org/paper/{pid}" if pid else ""


# ── Fetch & select ─────────────────────────────────────────────────────────

def fetch_candidates(themes: list) -> list:
    candidates = []
    seen_pids  = set()

    def add(results):
        for p in results:
            pid = p.get("paperId")
            if pid and pid not in seen_pids:
                seen_pids.add(pid)
                candidates.append(p)

    # Keyword searches per theme (3 random queries per theme)
    for theme in themes:
        pool = THEME_QUERIES[theme]
        for q in random.sample(pool, min(3, len(pool))):
            print(f"  [{theme}] {q!r}")
            add(s2_search(q, limit=40))

    # Venue sweep (2 random queries)
    for q in random.sample(VENUE_SWEEP_QUERIES, 2):
        print(f"  [venue] {q!r}")
        add(s2_search(q, limit=30))

    return candidates


def select_papers(candidates: list, seen: set) -> list:
    fresh = [p for p in candidates if not is_duplicate(p, seen)]

    # Bucket: recent+venue > recent only > older+venue
    rv = sorted([p for p in fresh if is_recent(p) and venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)
    ro = sorted([p for p in fresh if is_recent(p) and not venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)
    ov = sorted([p for p in fresh if not is_recent(p) and venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)

    pool, seen_pool = [], set()
    for p in rv + ro + ov:
        pid = p.get("paperId")
        if pid not in seen_pool:
            seen_pool.add(pid)
            pool.append(p)

    return pool[:5]


# ── Format & push ──────────────────────────────────────────────────────────

def format_card(i: int, total: int, p: dict) -> tuple[str, str]:
    title   = p.get("title") or "Untitled"
    authors = p.get("authors") or []
    author_str = ", ".join(a["name"] for a in authors[:3]) or "Unknown authors"
    if len(authors) > 3:
        author_str += " et al."
    venue   = p.get("venue") or "Unknown venue"
    year    = p.get("year") or ""
    cites   = p.get("citationCount") or 0
    abstract = (p.get("abstract") or "No abstract.").strip()
    if len(abstract) > 280:
        abstract = abstract[:277].rstrip() + "..."
    url     = paper_url(p)
    body = (
        f"{author_str}\n"
        f"{venue}, {year}  [{cites} citations]\n\n"
        f"{abstract}\n\n"
        f"Link: {url}"
    )
    return f"{i}/{total} {title}", body


def push_ntfy(title: str, text: str, click_url: str):
    headers = {
        "Title":    title,
        "Priority": "default",
        "Tags":     "books",
        "Content-Type": "text/plain; charset=utf-8",
    }
    if click_url:
        headers["Click"] = click_url

    r = requests.post(
        NTFY_URL,
        data=text.encode("utf-8"),
        headers=headers,
        timeout=15,
    )
    r.raise_for_status()
    print(f"ntfy push OK — HTTP {r.status_code}")


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    today  = datetime.date.today()
    themes = DAILY_MIX[today.weekday()]
    print(f"Date: {today}  |  Themes: {themes}")

    seen    = load_seen()
    seen_s  = build_seen_set(seen)
    print(f"Seen-papers log: {len(seen)} entries")

    candidates = fetch_candidates(themes)
    print(f"Candidates: {len(candidates)}")

    papers = select_papers(candidates, seen_s)
    print(f"Selected: {len(papers)}")

    if not papers:
        print("No new papers found — skipping push.")
        return

    total = len(papers)
    for i, p in enumerate(papers, 1):
        url = paper_url(p)
        title, message = format_card(i, total, p)
        push_ntfy(title, message, url)
        time.sleep(0.5)

    for p in papers:
        seen.append({
            "paperId": p.get("paperId"),
            "title":   p.get("title", ""),
            "url":     paper_url(p),
            "date":    today.isoformat(),
        })
    save_seen(seen)
    print("Done.")


if __name__ == "__main__":
    main()
