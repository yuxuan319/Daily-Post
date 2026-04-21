"""
Daily Paper Digest — Semantic Scholar API only, no AI API needed.
Strategy:
  - Use a fixed set of field-coverage slots every day
  - Build broader queries from mechanism + haptic + context keywords
  - Deduplicate against seen_papers.json
  - Prefer one strong paper per slot for better daily diversity
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

# ── Field coverage slots ───────────────────────────────────────────────────
# Based on Qamar et al. (CHI 2018): stretchable, deployable,
# variable stiffness, and shape memory mechanisms. We add a dedicated
# metamaterial slot and keep haptics central in every query.
QUERY_SLOTS = [
    {
        "name": "stretchable",
        "haptic": ["haptic", "tactile", "vibrotactile", "thermal haptic"],
        "mechanism": ["elastomer", "stretchable electronics", "soft actuator", "pneumatic"],
        "context": ["wearable", "interface", "skin", "glove"],
    },
    {
        "name": "deployable",
        "haptic": ["haptic", "tactile", "shape-changing"],
        "mechanism": ["origami", "kirigami", "deployable structure", "inflatable"],
        "context": ["interface", "display", "wearable", "device"],
    },
    {
        "name": "variable_stiffness",
        "haptic": ["haptic", "tactile", "kinaesthetic"],
        "mechanism": ["variable stiffness", "layer jamming", "granular jamming", "stiffness changing"],
        "context": ["wearable", "interface", "gripper", "virtual reality"],
    },
    {
        "name": "shape_memory",
        "haptic": ["haptic", "tactile", "shape-changing"],
        "mechanism": ["shape memory alloy", "shape memory polymer", "SMA", "SMP"],
        "context": ["interface", "display", "wearable", "actuator"],
    },
    {
        "name": "metamaterial",
        "haptic": ["haptic", "tactile", "vibrotactile"],
        "mechanism": ["mechanical metamaterial", "auxetic", "multistable", "metamaterial"],
        "context": ["interface", "wearable", "soft robot", "vibration control"],
    },
]

VENUE_SWEEP_QUERIES = [
    "haptic interface CHI",
    "tactile feedback UIST",
    "wearable haptics IEEE Haptics",
    "haptic device Science Robotics",
    "mechanical metamaterial haptic Nature",
    "haptic perception World Haptics",
    "smart material haptic Advanced Materials",
    "soft robot tactile Nature Communications",
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


def build_slot_queries(slot: dict, count: int = 2) -> list[str]:
    seen_queries = set()
    queries = []
    max_attempts = count * 8

    for _ in range(max_attempts):
        parts = [
            random.choice(slot["haptic"]),
            random.choice(slot["mechanism"]),
            random.choice(slot["context"]),
        ]
        query = " ".join(dict.fromkeys(parts))
        if query not in seen_queries:
            seen_queries.add(query)
            queries.append(query)
        if len(queries) >= count:
            break

    return queries


# ── Fetch & select ─────────────────────────────────────────────────────────

def fetch_candidates() -> tuple[dict, list]:
    slot_candidates = {slot["name"]: [] for slot in QUERY_SLOTS}
    all_candidates = []
    seen_pids = set()

    def add(results, target: list):
        for p in results:
            pid = p.get("paperId")
            if pid and pid not in seen_pids:
                seen_pids.add(pid)
                if target is not all_candidates:
                    target.append(p)
                all_candidates.append(p)

    # Every day uses the same field map; diversity comes from one slot per paper.
    for slot in QUERY_SLOTS:
        for q in build_slot_queries(slot, count=2):
            print(f"  [{slot['name']}] {q!r}")
            add(s2_search(q, limit=40), slot_candidates[slot["name"]])

    # Venue sweep (2 random queries)
    for q in random.sample(VENUE_SWEEP_QUERIES, 2):
        print(f"  [venue] {q!r}")
        add(s2_search(q, limit=30), all_candidates)

    return slot_candidates, all_candidates


def rank_papers(candidates: list, seen: set, excluded: set | None = None) -> list:
    excluded = excluded or set()
    fresh = [
        p for p in candidates
        if not is_duplicate(p, seen) and p.get("paperId") not in excluded
    ]

    # Bucket: recent+venue > recent only > older+venue
    rv = sorted([p for p in fresh if is_recent(p) and venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)
    ro = sorted([p for p in fresh if is_recent(p) and not venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)
    ov = sorted([p for p in fresh if not is_recent(p) and venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)
    oo = sorted([p for p in fresh if not is_recent(p) and not venue_match(p)],
                key=lambda p: p.get("citationCount") or 0, reverse=True)

    pool, seen_pool = [], set()
    for p in rv + ro + ov + oo:
        pid = p.get("paperId")
        if pid not in seen_pool:
            seen_pool.add(pid)
            pool.append(p)

    return pool


def select_papers(slot_candidates: dict, all_candidates: list, seen: set) -> list:
    selected = []
    selected_ids = set()
    overflow = []

    for slot in QUERY_SLOTS:
        ranked = rank_papers(slot_candidates[slot["name"]], seen, selected_ids)
        if ranked:
            chosen = ranked[0]
            selected.append(chosen)
            if chosen.get("paperId"):
                selected_ids.add(chosen["paperId"])
            overflow.extend(ranked[1:])

    if len(selected) < 5:
        overflow.extend(rank_papers(all_candidates, seen, selected_ids))

    final = []
    final_ids = set()
    for p in selected + overflow:
        pid = p.get("paperId")
        key = pid or (p.get("title") or "")[:40].lower()
        if key in final_ids:
            continue
        final_ids.add(key)
        final.append(p)
        if len(final) >= 5:
            break

    return final


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


def sanitize_header(value: str) -> str:
    # HTTP headers must be latin-1 encodable and must not contain newlines.
    value = value.replace("\r", " ").replace("\n", " ")
    return value.encode("latin-1", "replace").decode("latin-1")


def push_ntfy(title: str, text: str, click_url: str):
    headers = {
        "Title":    sanitize_header(title),
        "Priority": "default",
        "Tags":     "books",
        "Content-Type": "text/plain; charset=utf-8",
    }
    if click_url:
        headers["Click"] = sanitize_header(click_url)
        headers["Actions"] = sanitize_header(f"view, Open DOI, {click_url}, clear=true")

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
    today = datetime.date.today()
    slot_names = [slot["name"] for slot in QUERY_SLOTS]
    print(f"Date: {today}  |  Slots: {slot_names}")

    seen    = load_seen()
    seen_s  = build_seen_set(seen)
    print(f"Seen-papers log: {len(seen)} entries")

    slot_candidates, all_candidates = fetch_candidates()
    print(f"Candidates: {len(all_candidates)}")

    papers = select_papers(slot_candidates, all_candidates, seen_s)
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
