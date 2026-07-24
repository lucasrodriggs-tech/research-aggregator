import re
import sys
import json

CATEGORIES = {
    "cell_therapy",
    "regenerative_medicine",
    "clinical_trial",
    "neuroscience",
    "ai_biology",
    "biomedical_devices",
    "tissue_engineering",
    "gene_therapy",
}

REQUIRED_QUOTA_CATEGORIES = {"cell_therapy", "regenerative_medicine", "clinical_trial", "neuroscience"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED_STRING_FIELDS = ["id", "title", "link", "summary", "journal", "retraction_status", "citation_source"]


def validate_paper(paper):
    errors = []
    paper_id = paper.get("id", "<no id>")

    for field in _REQUIRED_STRING_FIELDS:
        value = paper.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{paper_id}: '{field}' must be a non-empty string")

    link = paper.get("link")
    if isinstance(link, str) and not (link.startswith("http://") or link.startswith("https://")):
        errors.append(f"{paper_id}: 'link' must be an http(s) URL")

    year = paper.get("year")
    if not isinstance(year, int) or isinstance(year, bool) or not (1900 <= year <= 2100):
        errors.append(f"{paper_id}: 'year' must be an int between 1900 and 2100")

    category = paper.get("category")
    if category not in CATEGORIES:
        errors.append(f"{paper_id}: 'category' must be one of {sorted(CATEGORIES)}, got {category!r}")

    for date_field in ("date_surfaced", "citation_checked_date"):
        value = paper.get(date_field)
        if not isinstance(value, str) or not _DATE_RE.match(value):
            errors.append(f"{paper_id}: '{date_field}' must be an ISO date string YYYY-MM-DD")

    citation_count = paper.get("citation_count")
    if not isinstance(citation_count, int) or isinstance(citation_count, bool) or citation_count < 0:
        errors.append(f"{paper_id}: 'citation_count' must be a non-negative int")

    contradicting = paper.get("contradicting_papers")
    if not isinstance(contradicting, list) or len(contradicting) > 5:
        errors.append(f"{paper_id}: 'contradicting_papers' must be a list of 0-5 items")
    else:
        for i, item in enumerate(contradicting):
            if not isinstance(item, dict) or not item.get("title") or not item.get("link"):
                errors.append(f"{paper_id}: 'contradicting_papers[{i}]' must have non-empty 'title' and 'link'")

    return errors


def validate_papers(papers):
    errors = []
    seen_ids = {}
    for paper in papers:
        errors.extend(validate_paper(paper))
        paper_id = paper.get("id")
        if paper_id:
            seen_ids[paper_id] = seen_ids.get(paper_id, 0) + 1
    for paper_id, count in seen_ids.items():
        if count > 1:
            errors.append(f"duplicate id '{paper_id}' appears {count} times")
    return errors


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/papers.json"
    with open(path, "r", encoding="utf-8") as f:
        papers = json.load(f)
    problems = validate_papers(papers)
    if problems:
        for problem in problems:
            print(problem)
        sys.exit(1)
    print(f"OK: {len(papers)} papers valid")
