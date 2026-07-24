# papers.json field reference

Each entry in `data/papers.json` is an object with these fields:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique slug, e.g. `nature-2024-alphafold3`. Must be unique across the whole file. |
| `title` | string | Paper title. |
| `link` | string | Direct URL, `http(s)://` — prefer publisher/PubMed/PMC over paywalled aggregators. |
| `summary` | string | 2-4 sentences, smart-layperson audience. |
| `journal` | string | Journal/venue name. |
| `year` | int | Year published. |
| `category` | string | One of: `cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`, `ai_biology`, `biomedical_devices`, `tissue_engineering`, `gene_therapy`. |
| `date_surfaced` | string | ISO date `YYYY-MM-DD` — the day this paper appeared in the digest. |
| `retraction_status` | string | Explicit statement of what was checked and found, even if "none found." Never omit. |
| `citation_count` | int | Non-negative. |
| `citation_source` | string | e.g. "Semantic Scholar". |
| `citation_checked_date` | string | ISO date `YYYY-MM-DD`. |
| `contradicting_papers` | list | 0-5 items, each `{"title": str, "link": str}`. Empty list if none genuinely exist — never fabricate one. |

Quota categories (at least 1 each required per day): `cell_therapy`, `regenerative_medicine`, `clinical_trial`, `neuroscience`.
