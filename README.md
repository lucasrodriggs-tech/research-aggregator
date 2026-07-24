# Research Digest

A daily-refreshed feed of groundbreaking biomedical/neuroscience research papers,
curated for video research. See `docs/superpowers/specs/2026-07-24-research-aggregator-design.md`
for the full design.

## Layout
- `data/papers.json` — full history of every paper ever surfaced (source of truth)
- `scripts/` — validation and site-build logic (Python, tested with pytest)
- `site/artifact_template.html` — the page design; `site/dist/index.html` is generated, not edited directly
- `agent/research_prompt.md` — the self-contained prompt the daily scheduled task runs

## Rebuilding the site locally

    python -m scripts.build_site

Writes `site/dist/index.html`, which then gets published via the Artifact tool.

## Running tests

    python -m pytest tests/ -v

## Live site

https://claude.ai/code/artifact/8f9f20cb-ee4c-4aa8-8ffe-e025d2771d97
