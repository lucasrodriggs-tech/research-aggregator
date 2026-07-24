from scripts.validate_papers import validate_paper, validate_papers, CATEGORIES, REQUIRED_QUOTA_CATEGORIES


def make_valid_paper(**overrides):
    paper = {
        "id": "nature-2024-alphafold3",
        "title": "Accurate structure prediction of biomolecular interactions with AlphaFold 3",
        "link": "https://www.nature.com/articles/s41586-024-07487-w",
        "summary": "DeepMind's successor to AlphaFold2 predicts structures of complexes involving proteins, DNA, RNA, and small molecules.",
        "journal": "Nature",
        "year": 2024,
        "category": "ai_biology",
        "date_surfaced": "2026-07-25",
        "retraction_status": "No retraction or correction found (checked Retraction Watch, PubPeer -- 2026-07-24).",
        "citation_count": 12392,
        "citation_source": "Semantic Scholar",
        "citation_checked_date": "2026-07-24",
        "contradicting_papers": [
            {"title": "A comprehensive benchmarking of AlphaFold3", "link": "https://academic.oup.com/bib/article/26/6/bbaf616/8351050"}
        ],
    }
    paper.update(overrides)
    return paper


def test_valid_paper_has_no_errors():
    assert validate_paper(make_valid_paper()) == []


def test_missing_title_is_an_error():
    paper = make_valid_paper()
    del paper["title"]
    errors = validate_paper(paper)
    assert any("title" in e for e in errors)


def test_invalid_category_is_an_error():
    paper = make_valid_paper(category="cardiology")
    errors = validate_paper(paper)
    assert any("category" in e for e in errors)


def test_too_many_contradicting_papers_is_an_error():
    paper = make_valid_paper(contradicting_papers=[{"title": f"P{i}", "link": "https://example.com"} for i in range(6)])
    errors = validate_paper(paper)
    assert any("contradicting_papers" in e for e in errors)


def test_zero_contradicting_papers_is_valid():
    paper = make_valid_paper(contradicting_papers=[])
    assert validate_paper(paper) == []


def test_bad_date_format_is_an_error():
    paper = make_valid_paper(date_surfaced="07/25/2026")
    errors = validate_paper(paper)
    assert any("date_surfaced" in e for e in errors)


def test_negative_citation_count_is_an_error():
    paper = make_valid_paper(citation_count=-1)
    errors = validate_paper(paper)
    assert any("citation_count" in e for e in errors)


def test_duplicate_ids_across_list_is_an_error():
    p1 = make_valid_paper()
    p2 = make_valid_paper()
    errors = validate_papers([p1, p2])
    assert any("duplicate" in e.lower() for e in errors)


def test_required_quota_categories_are_a_subset_of_categories():
    assert REQUIRED_QUOTA_CATEGORIES <= CATEGORIES
