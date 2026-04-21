---
name: daily-paper-discovery
description: >
  Find and curate 5 recent papers tailored to Yuxuan's SOFT-TOUCH PhD research in haptics and soft robotics.
  Use this skill whenever the user asks to find papers, get a daily reading list, discover new research, stay updated on their field,
  or any variation of "what should I read today", "find me papers", "show me recent work in haptics", etc.
  Also trigger this skill proactively if the user mentions feeling behind on literature or wanting to broaden their research horizon.
  The skill covers three interlocking themes: (1) soft robotics & smart materials, (2) haptic devices & actuators, (3) haptic perception & user experience.
  Sources include arXiv, ACM (CHI, UIST, TEI), IEEE Xplore, and Nature/Science family journals.
---

# Daily Paper Discovery

Curate 5 high-quality recent papers for Yuxuan's daily research reading. The goal is a mix of staying sharp on core topics and broadening perspective — prioritize papers that are novel, well-cited or from prestigious venues, and intellectually stimulating.

## Researcher Profile

**Yuxuan** is an early-stage PhD student working on **SOFT-TOUCH** — Soft Technologies for Optimizing User-Centric Haptics. Research sits at the intersection of:

- **Soft robotics & smart materials** — soft actuators, pneumatic systems, shape-memory materials, stretchable electronics, fabrication methods
- **Haptic devices & actuators** — wearable haptics, grounded haptic interfaces, thermal/vibrotactile/kinesthetic feedback, mid-air haptics
- **Haptic experience & perception** — psychophysics of touch, affective haptics, multimodal interaction, user studies, embodiment

**Adjacent fields worth watching:** HRI, rehabilitation robotics, flexible electronics, neuroscience of touch, AR/VR interaction.

## Venue Priority List

| Tier | Venues |
|------|--------|
| HCI/Haptics | CHI, UIST, TEI, IEEE Haptics Symposium, World Haptics, ISMAR |
| Robotics | ICRA, IROS, Science Robotics, IEEE T-RO, Soft Robotics journal |
| Broad impact | Nature, Science, Nature Machine Intelligence, Nature Electronics, Advanced Materials |
| Preprints | arXiv (cs.RO, cs.HC, eess.SY, cond-mat.mtrl-sci) |

## Seen-Papers Log

The seen-papers log is stored in the file `/home/user/Daily-Post/.claude/seen-papers.json`.

**Before searching**, load it with the Read tool:
- Read the file at `/home/user/Daily-Post/.claude/seen-papers.json`
- If the file does not exist or is empty, treat `seenPapers` as an empty array `[]`
- The format is a JSON array of `{ "title": "...", "doi_or_url": "...", "date": "YYYY-MM-DD" }`

**After selecting** the 5 papers, append them and save with the Write tool:
- Add each selected paper as `{ "title": "...", "doi_or_url": "...", "date": "<today>" }`
- Write the full updated array back to `/home/user/Daily-Post/.claude/seen-papers.json`
- If the array exceeds 500 entries, trim to the most recent 400 before saving
- Do this silently — no need to mention it to Yuxuan

Use the seen log to filter out any candidate papers before finalising the 5. Match on URL/DOI or on title substring (case-insensitive, first 40 chars is enough). The log is append-only — never delete entries.

---

## Workflow

### Step 1 — Rotate your search angle

Each day, pick a **different entry point** across the three themes. Use today's date to vary emphasis — don't always lead with devices. Suggested rotation:

| Day feel | Lead theme | Supporting themes |
|----------|-----------|-------------------|
| Device-heavy | Haptic actuators & fabrication | Smart materials |
| Perception-heavy | Haptic UX & psychophysics | Affective haptics |
| Materials-heavy | Soft robotics & smart materials | Sensing skins |
| Venue sweep | CHI / UIST / TEI latest | IEEE Haptics / World Haptics |
| Wild card | Adjacent field (neuro, rehab, flexible electronics) | Any |

Also rotate **query structure**: sometimes search by venue, sometimes by method, sometimes by application domain. Example patterns:

- `"soft actuator" haptic feedback 2025 CHI OR UIST OR TEI`
- `tactile perception psychophysics wearable 2025 IEEE`
- `stretchable electronics skin sensor Nature OR Science 2025`
- `pneumatic soft robot haptic skin arxiv 2025`
- `affective touch social haptics user study 2025`
- `liquid crystal elastomer actuator tactile 2025`
- `mid-air haptics ultrasound rendering 2025`
- `haptic texture rendering neural 2025`

Run **4–6 searches** using the WebSearch tool, then fetch full abstracts where possible using the WebFetch tool on arXiv abstract pages or ACM/IEEE pages.

### Step 2 — Select 5

Filter out any paper whose URL/DOI or title (first 40 chars, case-insensitive) matches an entry in the seen-papers log. Then pick the 5 most compelling remaining papers using these criteria:

- **Novelty**: Does it introduce a new method, material, device, or finding?
- **Relevance**: Does it connect to at least one of Yuxuan's three themes?
- **Venue quality**: Prefer top-tier venues; for arXiv, prefer recent high-engagement preprints
- **Diversity**: Try to touch more than one theme across the 5 picks, but follow what's genuinely exciting — don't force balance
- **Horizon-broadening**: At least 1 paper should come from an adjacent field or push beyond the obvious

### Step 3 — Output

Present each paper as a structured card using this exact format:

---

**[N]. [Full Paper Title]**
*[Authors (first 3, et al. if more)] — [Venue, Year]*

**What it's about:** 2–3 sentence plain-language summary of the core contribution.

**Why it's relevant:** 1–2 sentences connecting it specifically to SOFT-TOUCH or Yuxuan's research themes. Be concrete — mention which theme(s) it touches and what insight it offers.

**Link:** [URL or DOI]

---

After all 5 cards, add a one-line **Today's throughline** — a sentence capturing any emergent theme or interesting tension across the 5 picks.

### Step 4 — Save to log

Append today's 5 papers to the seen-papers log at `/home/user/Daily-Post/.claude/seen-papers.json` using the Write tool (see Seen-Papers Log section above).

## Tone & Style

- Write for a technically literate PhD student, not a layperson
- Be concise in summaries — no padding
- "Why it's relevant" should feel like a smart colleague's take, not a generic endorsement
- If a paper is a stretch from core haptics, say so and explain why it's still worth reading

## Notes

- Do not repeat papers across sessions — always check the seen-papers log first
- If search results are thin on a theme, widen the query before giving up
- Prefer papers with accessible abstracts or open-access PDFs
- arXiv preprint IDs should be linked as `https://arxiv.org/abs/[ID]`
