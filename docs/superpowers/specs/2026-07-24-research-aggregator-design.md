# Research Paper Aggregator — Design

## Purpose

Lucas is an aspiring science content creator (background: co-authored opioid-neuroscience circuit work at TAMU; currently a researcher in George Eisenhoffer's zebrafish lab at MD Anderson doing quantitative confocal imaging/Imaris analysis on epithelial biology and ROS-driven tissue breakdown). He wants a low-effort way to surface a small, high-quality, daily-refreshed set of research papers to pull video topics from, without having to manually trawl journals himself.

## Subject areas tracked

Neuroscience; AI applied to neuroscience/biology/biomedical research; biomedical devices; regenerative medicine — cell therapy (allogeneic, autologous, xenogeneic); tissue engineering; biomaterials (especially hydrogels); gene therapy; groundbreaking clinical trials/novel treatments.

## Selection criteria (all four should hold for a paper to qualify)

1. Groundbreaking/headline research — original research, or a major review of a genuinely hot area.
2. Relatively recent — search year-descending starting at 2026, falling back to 2025, 2024, ... down to 2019 as needed per category. Prefer the newest possible pick, but don't force a weak/non-groundbreaking paper just to stay recent — drop to an older year if that's where the strongest paper is.
3. Well-cited — report an actual citation count, its source (e.g. Semantic Scholar, Google Scholar), and the date checked, since counts drift.
4. Well-defined methods section with good figures — this generally rules out using a press release or news article as the primary item for a slot, though such pieces may be referenced as context within a paper's write-up.

## Daily volume and category mix

- 10 new papers per day.
- At least 1 must come from each of: cell therapy, regenerative medicine (non-cell-therapy), clinical trial, neuroscience.
- The remaining 6 may come from any tracked subject area (including repeats of the required four).
- No paper already present in `data/papers.json` may be re-selected (dedupe against full history, not just recent days).

## Required fields per paper

- Title
- Link (direct URL, prefer the journal/publisher page or PubMed/PMC over paywalled aggregators when a free version exists)
- 2-4 sentence summary, written for a smart layperson audience (this feeds directly into video research, so it should stay technically honest rather than oversimplified)
- Journal/venue
- Year published
- Retraction/correction history — explicit statement of what was checked (Retraction Watch, PubPeer, journal site) and what was found, even if "none found." Never omit this field.
- Citation count, with source and the date it was checked
- 1-5 contradicting/conflicting papers, if any genuinely exist (a paper that disputes the finding, fails to replicate it, or argues the opposite conclusion), each with title + link. If none exist, say so explicitly — never fabricate one to fill the slot.

## Architecture

Three pieces, tied together by one GitHub repo (Lucas has an existing GitHub account):

1. **Data store — GitHub repo.** Holds `data/papers.json` (append-only history of every paper ever surfaced, one entry per paper with all required fields above, plus its category tag and the date it was surfaced) and `data/marks.json` (Lucas's used/not-interested flags, keyed by paper ID).
2. **Daily scheduled Claude agent.** Runs once a day (default: 6:00 AM local time — trivially reconfigurable at setup, exact hour not load-bearing to the design). On each run it:
   - Pulls the repo.
   - Performs the research pass per the criteria, quota, and year-descending rules above, deduping against `data/papers.json`.
   - Appends the day's 10 new entries to `data/papers.json` and commits.
   - Regenerates the static site HTML from the full dataset.
   - Republishes the Claude Artifact to the same URL (`Artifact` tool, same file path → same URL, so the link Lucas bookmarks never changes).
3. **Claude Artifact website.** The page Lucas actually visits.
   - **Layout:** magazine feed — single column, full-width cards, summary always visible, generous whitespace. This was chosen over a compact grid and a dense filterable list after a visual mockup comparison (see `.superpowers/brainstorm/` history in this repo for the compared options).
   - **Today view** (default): today's 10 cards. Click a card to expand full detail in place (retraction status, citation count + source/date, contradicting papers) — an accordion, not a separate page.
   - **Archive tab:** browse/search past days' picks.
   - **Category filter chips** above the feed (Neuro / Cell Therapy / Regen Med / Clinical Trial / etc.), since papers are already tagged by category for the quota system, so filtering is cheap to add. (Default choice — Lucas didn't get to confirm/reject this explicitly; easy to remove later if it clutters the "calm magazine" feel.)
   - **Mark buttons** (used / not interested) per card, writing directly to `data/marks.json` in the GitHub repo via a GitHub connector using the Artifact `mcp` capability — the page calls the connector with Lucas's own claude.ai-side credentials; no server-side code needed.

## Data flow

```
Scheduled agent (daily)
  → WebSearch/WebFetch research pass
  → validate against 4 criteria + quota/dedupe rules
  → append to data/papers.json, commit to GitHub
  → regenerate site HTML from full dataset
  → Artifact tool republishes to the same URL

Lucas's browser (any time, independent of the agent)
  → click "mark" on a card
  → GitHub connector (mcp capability) writes to data/marks.json
  → page reflects the mark on next load
```

## Known dependencies / open items before implementation can complete

- **Lucas must connect a GitHub connector in his claude.ai account.** The mark-writing feature cannot be built or tested until that connector exists and a real request/response pair has been observed through it — this is a hard requirement of how the Artifact `mcp` capability works (no guessing tool shapes).
- **Scheduled-agent write access to GitHub is unverified.** The likely approach is for the scheduled agent to use the same GitHub connector (rather than raw git credentials) to commit `data/papers.json` updates — to be confirmed when the scheduled task is actually built and run once manually.
- Declaring the `mcp` capability on the Artifact means the page cannot be shared publicly (a platform-level restriction) — acceptable here since Lucas is the only intended viewer.

## Testing / validation plan

- Run the scheduled agent's research logic once manually (not on the cron schedule) before trusting it to run unattended, and sanity-check the output against the required-fields checklist above.
- Verify the Artifact republish actually updates content at the existing (bookmarked) URL rather than minting a new one.
- Verify a mark round-trips end to end: click in the browser → commit lands in `data/marks.json` on GitHub → reload reflects the mark.
- Verify dedupe: run the research pass twice against the same date range and confirm no paper appears twice in `data/papers.json`.
